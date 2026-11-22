"""Captura experimental para una instantánea provisional, sin modelos ni AWS."""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from prisma.domain.catalogo_ipc import CatalogoReferencia


class _Tablas(HTMLParser):
    """Conserva celdas vacías y captura tablas anidadas por separado."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila = []
        self.tablas = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self.pila.append({"filas": [], "fila": None, "celda": None})
        elif self.pila and tag == "tr":
            self.pila[-1]["fila"] = []
        elif self.pila and tag in ("td", "th") and self.pila[-1]["fila"] is not None:
            self.pila[-1]["celda"] = []

    def handle_data(self, data):
        if self.pila and self.pila[-1]["celda"] is not None:
            self.pila[-1]["celda"].append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if not self.pila:
            return
        tabla = self.pila[-1]
        if tag in ("td", "th") and tabla["celda"] is not None:
            tabla["fila"].append(" ".join("".join(tabla["celda"]).split()))
            tabla["celda"] = None
        elif tag == "tr" and tabla["fila"] is not None:
            tabla["filas"].append(tabla["fila"])
            tabla["fila"] = None
        elif tag == "table":
            self.tablas.append(self.pila.pop()["filas"])


def _fecha_documento(texto: str) -> date:
    # Las fechas de la cabecera del boletín se expresan, p. ej., "17 Nov 2026".
    meses = {"ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4,
             "may": 5, "jun": 6, "jul": 7, "ago": 8, "aug": 8, "sep": 9,
             "set": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12}
    limpio = html.unescape(re.sub(r"<[^>]+>", " ", texto))
    fechas = set()
    for dia, mes, anio in re.findall(r"\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b", limpio):
        if mes.lower() in meses:
            try:
                fechas.add(date(int(anio), meses[mes.lower()], int(dia)))
            except ValueError:
                pass
    if len(fechas) != 1:
        raise ValueError("No se pudo identificar una fecha inequívoca en el boletín.")
    return fechas.pop()


def _numero(texto: str) -> float:
    valor = float(texto.replace(",", "").replace("$", "").strip())
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError("Precio no positivo o no finito.")
    return valor


def extraer(raw: bytes, fecha: date, catalogo: CatalogoReferencia, url_fuente: str) -> dict:
    """Extrae filas por pareja exacta y bloquea discrepancias; no comprueba vigencia IPC."""
    componentes = catalogo.en_corte(fecha)
    if not raw:
        raise ValueError("Boletín vacío.")
    texto = raw.decode("utf-8-sig", errors="strict")
    if _fecha_documento(texto) != fecha:
        raise ValueError("La fecha del documento no coincide con el corte solicitado.")
    parser = _Tablas()
    parser.feed(texto)
    observaciones = defaultdict(list)
    tablas_validas = 0
    for filas in parser.tablas:
        for i, fila in enumerate(filas):
            # Este encabezado distingue cotizaciones de tablas de paquetes.
            encabezado = [x.casefold() for x in fila]
            if encabezado[:5] != ["emisora", "serie", "último", "anterior", "ppp"]:
                continue
            tablas_validas += 1
            for valores in filas[i + 1:]:
                if len(valores) < 2 or not valores[0] or not valores[1]:
                    continue
                clave = (valores[0].strip().upper(), valores[1].strip().upper())
                try:
                    if len(valores) < len(encabezado):
                        raise ValueError("Fila incompleta.")
                    precios = tuple(_numero(v) for v in valores[2:5])
                    observaciones[clave].append(precios)
                except (ValueError, IndexError):
                    observaciones[clave].append(None)
            break
    if not tablas_validas:
        raise ValueError("No se encontró ninguna tabla de cotizaciones con encabezado reconocido.")

    sha = hashlib.sha256(raw).hexdigest()
    registros = []
    for c in componentes:
        encontradas = observaciones.get((c.emisora, c.serie), [])
        validas = {x for x in encontradas if x is not None}
        if not encontradas:
            estado, precio = "NO_ENCONTRADO_EN_TABLAS", None
        elif None in encontradas or not validas:
            estado, precio = "FILA_INVALIDA_REQUIERE_REVISION", None
        elif len(validas) != 1:
            estado, precio = "CONFLICTO_ENTRE_FILAS", None
        else:
            estado, precio = "PPP_OBSERVADO_MAPEO_PROVISIONAL", next(iter(validas))
        ultimo, anterior, ppp = precio if precio else (None, None, None)
        registros.append({
            "fecha": fecha.isoformat(), "emisora_propuesta": c.emisora, "serie_propuesta": c.serie,
            "origen_catalogo": c.origen, "alias_blackrock": c.blackrock,
            "estado_composicion": c.estado_composicion, "estado_mapeo": c.estado_mapeo,
            "estado_captura": estado, "ppp_bmv_mxn": ppp, "ultimo_bmv_mxn": ultimo,
            "anterior_bmv_mxn": anterior, "apariciones": len(encontradas),
            "url_fuente": url_fuente, "sha256_boletin": sha, "version_catalogo": catalogo.version,
        })
    return {
        "estado": "CAPTURA_EXPERIMENTAL", "fecha": fecha.isoformat(),
        "fecha_documento": fecha.isoformat(), "version_catalogo": catalogo.version,
        "estado_catalogo": "PROVISIONAL_NO_OFICIAL", "url_fuente": url_fuente,
        "sha256_boletin": sha, "tablas_reconocidas": tablas_validas,
        "resumen": dict(Counter(r["estado_captura"] for r in registros)),
        "filas": registros,
    }


def guardar(resultado: dict, raw: bytes, destino: Path) -> None:
    """Exige directorio nuevo; no sobrescribe resultados ni toca S3."""
    if hashlib.sha256(raw).hexdigest() != resultado.get("sha256_boletin"):
        raise ValueError("El boletín no coincide con el hash del resultado.")
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=False)
    manifiesto = {k: v for k, v in resultado.items() if k != "filas"}
    manifiesto["timestamp_ejecucion_utc"] = datetime.now(timezone.utc).isoformat()
    (destino / "boletin.html").write_bytes(raw)
    (destino / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
    with (destino / "precios_provisionales.csv").open("x", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(resultado["filas"][0]))
        escritor.writeheader()
        escritor.writerows(resultado["filas"])
