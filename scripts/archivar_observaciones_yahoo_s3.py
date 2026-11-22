"""Archiva observaciones secundarias Yahoo Finance (.MX) en S3 sin tocar Silver ni PPP BMV.

Guarda la respuesta JSON cruda de Yahoo Finance bajo ``observaciones/yahoo/<SIMBOLO>/<YYYY-MM-DD>.json``
de forma inmutable (``IfNoneMatch='*'``) solo tras validar el cierre con ``interpretar_cierre``.
Nunca escribe en ``silver/``, nunca etiqueta como ``ppp_bmv_mxn`` y nunca habilita inferencia.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prisma.data.evidencias_s3 import (
    BUCKET_PRODUCTIVO,
    escribir_inmutable,
    escribir_json_inmutable,
    timestamp_slug,
)
from prisma.data.ipc35_almacen import SIMBOLOS_YAHOO_IPC35
from prisma.data.yahoo_secundario import interpretar_cierre

USER_AGENT = "Mozilla/5.0 (compatible; PrismaBMV-YahooObservaciones/1.0)"


def descargar_chart_yahoo(simbolo: str, rango: str = "10d", timeout: int = 15) -> bytes:
    simbolo_url = urllib.parse.quote(simbolo, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo_url}?interval=1d&range={rango}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(2_000_001)
    if not raw or len(raw) > 2_000_000:
        raise ValueError(f"Respuesta Yahoo fuera de rango para {simbolo}")
    return raw


def archivar_observaciones_s3(
    s3,
    bucket: str,
    fechas: list[str],
    *,
    emisoras: list[str] | None = None,
    descargador=descargar_chart_yahoo,
    rango: str = "10d",
    guardar_reporte: bool = True,
) -> dict:
    seleccion = emisoras or list(SIMBOLOS_YAHOO_IPC35.keys())
    archivadas = []
    omitidas = []
    errores = []

    for emisora in seleccion:
        simbolo = SIMBOLOS_YAHOO_IPC35.get(emisora)
        if not simbolo:
            errores.append({"emisora": emisora, "error": "Emisora sin símbolo Yahoo verificado"})
            continue
        try:
            raw = descargador(simbolo, rango=rango)
        except Exception as exc:
            errores.append({"emisora": emisora, "simbolo": simbolo, "error": f"Descarga fallida: {exc}"})
            continue

        for fecha in fechas:
            try:
                obs = interpretar_cierre(raw, simbolo, fecha)
            except ValueError as exc:
                omitidas.append({"emisora": emisora, "simbolo": simbolo, "fecha": fecha, "motivo": str(exc)})
                continue
            key = f"observaciones/yahoo/{simbolo}/{fecha}.json"
            if key.startswith("silver/") or key.startswith("gold/"):
                raise ValueError("Separación estricta violada: Yahoo no puede escribir en silver/ o gold/.")
            res = escribir_inmutable(s3, bucket, key, raw, "application/json; charset=utf-8")
            archivadas.append({
                "emisora": emisora,
                "simbolo": simbolo,
                "fecha": fecha,
                "valor_cierre_mxn": obs["valor"],
                "estado_s3": res["estado"],
                "key": key,
                "sha256_respuesta": obs["sha256_respuesta"],
                "fuente": obs["fuente"],
                "tipo": obs["tipo"],
            })

    reporte = {
        "version": 1,
        "generado_en_utc": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "fechas_solicitadas": fechas,
        "total_simbolos_consultados": len(seleccion),
        "total_archivadas": len(archivadas),
        "total_omitidas": len(omitidas),
        "total_errores": len(errores),
        "separacion_estricta": "Solo observaciones/yahoo/<SIMBOLO>/<YYYY-MM-DD>.json; nunca silver/ ni PPP BMV.",
        "archivadas": archivadas,
        "omitidas": omitidas,
        "errores": errores,
    }
    if guardar_reporte:
        clave = f"evidencias/auditorias/archivo_yahoo_{timestamp_slug()}.json"
        reporte["reporte_s3"] = escribir_json_inmutable(s3, bucket, clave, reporte)
    return reporte


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--fechas", nargs="+", required=True, help="Fechas ISO YYYY-MM-DD a archivar")
    p.add_argument("--rango", default="10d", help="Parámetro range de Yahoo chart (ej. 10d, 1mo)")
    p.add_argument("--emisoras", nargs="*", default=None, help="Subconjunto opcional de emisoras")
    p.add_argument("--sin-reporte", action="store_true")
    args = p.parse_args()

    import boto3
    s3 = boto3.client("s3", region_name=args.region)
    rep = archivar_observaciones_s3(
        s3,
        args.bucket,
        args.fechas,
        emisoras=args.emisoras,
        rango=args.rango,
        guardar_reporte=not args.sin_reporte,
    )
    print(json.dumps({
        "fechas_solicitadas": rep["fechas_solicitadas"],
        "total_simbolos_consultados": rep["total_simbolos_consultados"],
        "total_archivadas": rep["total_archivadas"],
        "total_omitidas": rep["total_omitidas"],
        "total_errores": rep["total_errores"],
        "reporte_s3": rep.get("reporte_s3"),
    }, ensure_ascii=False, indent=2))
    if rep["total_archivadas"] == 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
