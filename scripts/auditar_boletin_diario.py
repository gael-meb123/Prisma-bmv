"""Contrasta un Silver diario con su HTML Bronze; no modifica ni valida señales."""
import argparse
import collections
import csv
import hashlib
import io
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from prisma.data.captura_ampliada import _Tablas, _fecha_documento


def numero(valor):
    try:
        n = Decimal(str(valor).strip().replace(",", "").replace("$", ""))
        return n if n.is_finite() and n > 0 else None
    except InvalidOperation:
        return None


def auditar(raw, filas, fecha):
    corte = date.fromisoformat(fecha)
    if corte.isoformat() != fecha or not raw or not filas:
        raise ValueError("Corte, boletín o Silver inválido.")
    if any(r.get("fecha") != fecha for r in filas):
        raise ValueError("Silver contiene fechas distintas.")
    texto = raw.decode("utf-8-sig")
    if _fecha_documento(texto) != corte:
        raise ValueError("La fecha del boletín no coincide.")
    parser = _Tablas()
    parser.feed(texto)
    observaciones = collections.defaultdict(list)
    tablas = 0
    for tabla in parser.tablas:
        for i, fila in enumerate(tabla):
            if [x.casefold() for x in fila[:5]] != ["emisora", "serie", "último", "anterior", "ppp"]:
                continue
            tablas += 1
            for celdas in tabla[i + 1:]:
                if len(celdas) < 5:
                    continue
                par = (celdas[0].strip().upper(), celdas[1].strip().upper())
                if all(par):
                    observaciones[par].append(numero(celdas[4]))
            break
    if not tablas:
        raise ValueError("No hay tablas de cotizaciones reconocibles.")
    sha = hashlib.sha256(raw).hexdigest()
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{corte:%Y%m%d}.html"
    vistos = set()
    detalles = []
    for fila in filas:
        par = (fila.get("emisora", "").strip().upper(), fila.get("serie", "").strip().upper())
        if not all(par) or par in vistos:
            raise ValueError("Clave de Silver ausente o duplicada.")
        vistos.add(par)
        estado = fila.get("estado_captura", "")
        if estado != "PPP_PUBLICADO_VERIFICADO":
            detalles.append({"emisora": par[0], "serie": par[1], "resultado": "NO_EVALUADO_NO_VERIFICADO"})
            continue
        matches = observaciones.get(par, [])
        valores = set(matches)
        if fila.get("sha256_boletin") != sha:
            resultado = "HASH_DIFERENTE"
        elif fila.get("url_fuente") != url:
            resultado = "URL_DIFERENTE"
        elif not matches:
            resultado = "SIN_FILA_EN_TABLAS"
        elif None in valores or len(valores) != 1:
            resultado = "FILA_AMBIGUA_O_INVALIDA"
        elif numero(fila.get("ppp_bmv_mxn")) != next(iter(valores)):
            resultado = "PPP_DIFERENTE"
        else:
            resultado = "COINCIDE_PPP_Y_HASH"
        detalles.append({"emisora": par[0], "serie": par[1], "resultado": resultado})
    return {"fecha": fecha, "sha256_bronze": sha, "tablas_reconocidas": tablas,
            "resumen": dict(collections.Counter(x["resultado"] for x in detalles)), "filas": detalles,
            "limitacion": "Solo comprueba consistencia con el HTML conservado; no acredita autenticidad, derechos, ventanas ni modelos."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bronze", type=Path, required=True)
    p.add_argument("--silver", type=Path, required=True)
    p.add_argument("--fecha", required=True)
    args = p.parse_args()
    raw_silver = args.silver.read_bytes()
    filas = list(csv.DictReader(io.StringIO(raw_silver.decode("utf-8-sig"), newline="")))
    resultado = auditar(args.bronze.read_bytes(), filas, args.fecha)
    resultado["sha256_silver"] = hashlib.sha256(raw_silver).hexdigest()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
