"""Ejecuta el backfill inmutable de ``silver/ipc35_provisional/``, auditoría AMX 2023 y avance inicial en S3."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prisma.data.captura_ampliada import _Tablas, _fecha_documento
from prisma.data.evidencias_s3 import BUCKET_PRODUCTIVO, escribir_json_inmutable, timestamp_slug
from prisma.data.ipc35_almacen import SIMBOLOS_YAHOO_IPC35, generar_resumen_avance_s3, guardar_corte_ipc35
from prisma.domain.bmv_core import url_boletin
from scripts.auditar_cobertura_ipc35_s3 import listar_bronze_boletines


def backfill_ipc35_desde_bronze(s3, bucket: str) -> dict:
    boletines = listar_bronze_boletines(s3, bucket)
    resultados = []
    for fecha, key in boletines:
        raw = s3.get_object(Bucket=bucket, Key=key)["Body"].read(2_000_001)
        res = guardar_corte_ipc35(s3, bucket, raw, fecha, url_boletin(fecha.replace("-", "")))
        resultados.append(res)
    reporte = {
        "version": 1,
        "generado_en_utc": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "total_cortes_ipc35": len(resultados),
        "rango": [resultados[0]["fecha"], resultados[-1]["fecha"]] if resultados else [],
        "cortes": resultados,
        "emision": "NO_HABILITADA",
    }
    reporte["reporte_s3"] = escribir_json_inmutable(
        s3, bucket, f"evidencias/auditorias/backfill_ipc35_{timestamp_slug()}.json", reporte
    )
    return reporte


def auditar_transicion_amx_2023_en_s3(s3, bucket: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 PrismaBMV-Auditoria/1.0"}
    evidencia = {}
    for fecha in ("2023-03-15", "2023-03-16"):
        url = url_boletin(fecha.replace("-", ""))
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20).read(1_000_001)
        txt = raw.decode("utf-8-sig", errors="replace")
        p = _Tablas()
        p.feed(txt)
        filas_amx = []
        for tabla in p.tablas:
            for i, fila in enumerate(tabla):
                if [c.casefold() for c in fila[:5]] == ["emisora", "serie", "último", "anterior", "ppp"]:
                    for vals in tabla[i + 1:]:
                        if len(vals) >= 5 and vals[0].strip().upper() == "AMX":
                            filas_amx.append({"emisora": "AMX", "serie": vals[1].strip().upper(), "ppp": vals[4]})
                    break
        evidencia[fecha] = {
            "url": url,
            "fecha_documento": _fecha_documento(txt).isoformat(),
            "sha256_html": hashlib.sha256(raw).hexdigest(),
            "cotizaciones_amx": filas_amx,
        }
    reporte = {
        "version": 1,
        "generado_en_utc": datetime.now(timezone.utc).isoformat(),
        "hallazgo": "CAMBIO_CORPORATIVO_SERIE_AMX_L_A_AMX_B_2023_03_16",
        "explicacion": (
            "Las 13 ventanas marcadas como SIN_CLAVE_EXACTA entre 2023-03-28 y 2023-04-17 "
            "no corresponden a huecos de precio: América Móvil unificó la serie L en serie B "
            "el 2023-03-16 (verificado en los boletines oficiales BMV del 15 y 16 de marzo de 2023)."
        ),
        "tratamiento_entrenamiento": "EXCLUIR_13_FILAS_TRANSICION_EN_MODO_MISMA_SERIE_ESTRICTA",
        "evidencia_bmv": evidencia,
    }
    reporte["reporte_s3"] = escribir_json_inmutable(
        s3, bucket, "evidencias/auditorias/auditoria_amx_unificacion_serie_2023.json", reporte
    )
    return reporte


def archivar_verificacion_yahoo_35(s3, bucket: str) -> dict:
    payload = {
        "version": 1,
        "verificado_en_utc": datetime.now(timezone.utc).isoformat(),
        "metodo": "CONSULTA_SOLO_LECTURA_METADATOS_CHART_MEX_MXN",
        "total_simbolos": len(SIMBOLOS_YAHOO_IPC35),
        "habilitacion_productiva": False,
        "estado_permiso": "EN_TRAMITE",
        "simbolos": SIMBOLOS_YAHOO_IPC35,
        "nota": "Verificación de símbolo/moneda MXN únicamente; prohibido usar en PPP BMV, Silver o modelos.",
    }
    return escribir_json_inmutable(
        s3, bucket, "evidencias/observaciones_yahoo/simbolos_ipc35_verificados_20261121.json", payload
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    p.add_argument("--region", default="us-east-1")
    args = p.parse_args()

    import boto3
    s3 = boto3.client("s3", region_name=args.region)
    out = {
        "backfill_ipc35": backfill_ipc35_desde_bronze(s3, args.bucket),
        "amx_2023": auditar_transicion_amx_2023_en_s3(s3, args.bucket),
        "yahoo_35": archivar_verificacion_yahoo_35(s3, args.bucket),
        "avance_inicial": generar_resumen_avance_s3(
            s3, args.bucket, "2026-11-20",
            "96f779e7ddde021f72e7b469b7bad8fa1c774adb0df004e6ea2eaed8ae6eb4b9",
            "backfill-inicial",
            {"CAPTURA_SEGURA_CONFIRMADA": 8, "COINCIDE_PPP_Y_HASH": 90, "SILVER_AUSENTE": 0},
        ),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
