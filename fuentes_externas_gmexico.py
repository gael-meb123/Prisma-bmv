"""Descarga reproducible de FIX Banxico y cobre diario BCCh, sin imputacion."""

from datetime import date
import hashlib
from html import unescape
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urljoin
from urllib.request import build_opener, HTTPCookieProcessor, Request

import numpy as np
import pandas as pd

from metodologia_ppp import ROOT, timestamp_utc

DIRECTORIO = ROOT / "experimento_gmexico_macro"
BANXICO = "https://www.banxico.org.mx/tipcamb/tipCamIHAction.do"
BANXICO_NOTAS = "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?sector=6&accion=consultarCuadro&idCuadro=CF102&locale=es"
BCCH_INDICE = "https://si3.bcentral.cl/indicadoressiete/secure/IndicadoresDiarios.aspx"


class TablasHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.tables, self.hidden = [], [], {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("type", "").lower() == "hidden":
            self.hidden[a["name"]] = a.get("value", "")
        if tag == "table":
            self.stack.append({"rows": [], "row": None, "cell": None})
        if self.stack:
            f = self.stack[-1]
            if tag == "tr":
                f["row"] = []
            if tag in ("td", "th"):
                f["cell"] = []

    def handle_data(self, text):
        if self.stack and self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"].append(text)

    def handle_endtag(self, tag):
        if not self.stack:
            return
        f = self.stack[-1]
        if tag in ("td", "th") and f["cell"] is not None:
            if f["row"] is not None:
                f["row"].append(" ".join("".join(f["cell"]).split()))
            f["cell"] = None
        elif tag == "tr" and f["row"] is not None:
            f["rows"].append(f["row"])
            f["row"] = None
        elif tag == "table":
            self.tables.append(self.stack.pop()["rows"])


def tablas(raw):
    parser = TablasHTML()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return parser


def numero(text, decimal_coma=False):
    if text in ("", "N/E", "N/D", "ND", "-", "n.d."):
        return np.nan
    clean = text.replace(".", "").replace(",", ".") if decimal_coma else text.replace(",", "")
    value = float(clean)
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"Valor externo no positivo o no finito: {text}")
    return value


class ArchivoFuentes:
    def __init__(self, directorio=DIRECTORIO):
        self.dir = Path(directorio) / "fuentes"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.dir / "manifiesto.json"
        self.records = json.loads(self.manifest_path.read_text(encoding="utf-8")) if self.manifest_path.exists() else {}
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def descargar(self, url, data=None):
        payload = urlencode(data).encode() if data is not None else None
        key = hashlib.sha256(url.encode() + b"\n" + (payload or b"")).hexdigest()
        if key in self.records:
            record = self.records[key]
            raw = (self.dir / record["archivo"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != record["sha256"]:
                raise ValueError("El cache externo no coincide con su SHA256")
            return raw, record
        req = Request(url, data=payload, headers={"User-Agent": "Mozilla/5.0 PrismaBMV-Research/1.0"})
        with self.opener.open(req, timeout=60) as response:
            raw = response.read()
            final_url = response.geturl()
        digest = hashlib.sha256(raw).hexdigest()
        filename = digest + ".html"
        (self.dir / filename).write_bytes(raw)
        record = {"url": url, "url_resuelta": final_url, "metodo": "POST" if payload else "GET", "sha256": digest, "archivo": filename, "timestamp_descarga_utc": timestamp_utc()}
        self.records[key] = record
        self.manifest_path.write_text(json.dumps(self.records, indent=2, ensure_ascii=False), encoding="utf-8")
        return raw, record


def parsear_fix(raw):
    parsed = tablas(raw)
    # La pagina presenta columnas verticales en tablas anidadas: fecha, FIX, DOF, pagos.
    candidates = []
    for table in parsed.tables:
        cells = [row[0] for row in table if len(row) == 1]
        dates = [v for v in cells if re.fullmatch(r"\d{2}/\d{2}/\d{4}", v)]
        if len(dates) > 10 and len(dates) == len(cells):
            candidates.append(("fecha", cells))
        elif len(cells) > 10 and all(re.fullmatch(r"[\d.,]+|N/E|N/D", v) for v in cells):
            candidates.append(("valor", cells))
    if not candidates or candidates[0][0] != "fecha" or len(candidates) < 2:
        raise ValueError("Estructura Banxico inesperada: no se identifica Fecha seguida de FIX")
    dates, values = candidates[0][1], candidates[1][1]
    headers = [r for t in parsed.tables for r in t if len(r) == 4 and r[0] == "Fecha"]
    if len(dates) != len(values) or not headers or "Determinaci" not in headers[0][1] or "DOF" not in headers[0][2]:
        raise ValueError("Longitudes o encabezado FIX inconsistentes")
    return pd.DataFrame({"fecha": pd.to_datetime(dates, format="%d/%m/%Y").strftime("%Y-%m-%d"), "usd_mxn_fix": [numero(v) for v in values]}).sort_values("fecha")


def parsear_cobre(raw, year):
    html = raw.decode("utf-8", errors="replace")
    if not re.search(r'id="lblAnioValor">\s*' + str(year) + r"\s*</label>", html):
        raise ValueError(f"La respuesta del cobre no confirma el anio solicitado {year}")
    tables = tablas(raw).tables
    candidates = [t for t in tables if sum(len(r) == 13 and r[0].isdigit() for r in t) == 31]
    if len(candidates) != 1:
        raise ValueError("No se identifica una unica matriz diaria de 12 meses del cobre")
    rows = []
    for row in candidates[0]:
        if len(row) != 13 or not row[0].isdigit():
            continue
        day = int(row[0])
        for month, text in enumerate(row[1:], 1):
            try:
                fecha = date(year, month, day).isoformat()
            except ValueError:
                if text:
                    raise ValueError("Cotizacion en una fecha inexistente")
                continue
            rows.append({"fecha": fecha, "cobre_usd_libra": numero(text, decimal_coma=True)})
    return pd.DataFrame(rows).sort_values("fecha")


def descargar_series(inicio="2016-10-01", fin="2026-10-28", directorio=DIRECTORIO):
    store = ArchivoFuentes(directorio)
    raw, meta = store.descargar(BANXICO, {"idioma": "sp", "fechaInicial": pd.Timestamp(inicio).strftime("%d/%m/%Y"), "fechaFinal": pd.Timestamp(fin).strftime("%d/%m/%Y"), "salida": "HTML"})
    fx = parsear_fix(raw)
    fx["sha256_fuente"] = meta["sha256"]
    store.descargar(BANXICO_NOTAS)
    raw, _ = store.descargar(BCCH_INDICE)
    html = raw.decode("utf-8", errors="replace")
    links = re.findall(r'href="([^"]*Serie.aspx\?gcode=LIBRA_COBRE[^"]*)"', html)
    if not links:
        raise ValueError("BCCh no ofrece enlace a LIBRA_COBRE")
    url = urljoin(BCCH_INDICE, unescape(links[0]))
    raw, initial_meta = store.descargar(url)
    initial = raw
    copper = []
    for year in range(pd.Timestamp(inicio).year, pd.Timestamp(fin).year + 1):
        data = tablas(initial).hidden
        data.update({"__EVENTTARGET": "DrDwnFechas", "__EVENTARGUMENT": "", "DrDwnFechas": str(year)})
        if re.search(r'id="lblAnioValor">\s*' + str(year) + r"\s*</label>", initial.decode("utf-8", errors="replace")):
            raw, meta = initial, initial_meta
        else:
            raw, meta = store.descargar(url, data)
        annual = parsear_cobre(raw, year)
        annual["sha256_fuente"] = meta["sha256"]
        copper.append(annual)
        print(f"Cobre BCCh {year}: {annual.cobre_usd_libra.notna().sum()} observaciones publicadas")
    cu = pd.concat(copper, ignore_index=True)
    for frame, name in [(fx, "usd_mxn_fix"), (cu, "cobre_usd_libra")]:
        frame.drop(frame[~frame.fecha.between(inicio, fin)].index, inplace=True)
        if frame.fecha.duplicated().any():
            raise ValueError(f"Fechas duplicadas en {name}")
        frame.to_csv(Path(directorio) / f"{name}_oficial.csv", index=False, encoding="utf-8-sig")
    return fx, cu
