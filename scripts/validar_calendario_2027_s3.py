"""Valida una evidencia oficial de calendario BMV 2027 almacenada en S3.

No modifica ``prisma/domain/calendario_bmv.py`` ni habilita 2027 automáticamente:
comprueba huella SHA-256, fechas canónicas y frontera dic-2026/ene-2027 antes de aprobar.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prisma.data.evidencias_s3 import (
    BUCKET_PRODUCTIVO,
    escribir_json_inmutable,
    leer_json,
    sha256_bytes,
    timestamp_slug,
    validar_sha256,
)
from prisma.domain.calendario_bmv import FERIADOS_BMV

PREFIJO_CAL_2027 = "evidencias/calendario_bmv/2027/"


def validar_propuesta_2027(s3, bucket: str, propuesta: dict | None) -> dict:
    errores = []
    if not isinstance(propuesta, dict):
        return {
            "anio": 2027,
            "valido_para_promocion": False,
            "errores": ["Falta evidencias/calendario_bmv/2027/estado.json en S3."],
            "habilita_operacion": False,
        }
    if propuesta.get("anio") != 2027:
        errores.append("El documento no corresponde al año 2027.")
    if propuesta.get("estado") != "FUENTE_OFICIAL_CARGADA":
        errores.append(f"Calendario 2027 aún no tiene fuente oficial cargada (estado={propuesta.get('estado')!r}).")

    ev_key = propuesta.get("evidencia_s3_key")
    sha = propuesta.get("sha256_evidencia")
    if not isinstance(ev_key, str) or not ev_key.startswith(PREFIJO_CAL_2027) or ev_key.endswith("estado.json"):
        errores.append("evidencia_s3_key debe apuntar al archivo original oficial bajo evidencias/calendario_bmv/2027/.")
    elif not validar_sha256(sha):
        errores.append("sha256_evidencia ausente o inválido.")
    else:
        try:
            raw = s3.get_object(Bucket=bucket, Key=ev_key)["Body"].read(5_000_001)
            if sha256_bytes(raw) != sha:
                errores.append("SHA-256 del documento oficial en S3 no coincide con sha256_evidencia.")
        except Exception as exc:
            errores.append(f"No se pudo leer el documento oficial en S3 ({ev_key}): {exc}")

    feriados_raw = propuesta.get("feriados")
    feriados_validados = []
    if not isinstance(feriados_raw, list) or not feriados_raw:
        errores.append("Lista de feriados 2027 ausente o vacía.")
    else:
        vistos = set()
        for f in feriados_raw:
            if not isinstance(f, str):
                errores.append(f"Feriado no textual: {f!r}")
                continue
            try:
                d = date.fromisoformat(f)
            except ValueError:
                errores.append(f"Fecha inválida: {f!r}")
                continue
            if d.isoformat() != f or d.year != 2027:
                errores.append(f"Fecha fuera de 2027 o no canónica: {f!r}")
                continue
            if f in vistos:
                errores.append(f"Feriado duplicado: {f}")
                continue
            vistos.add(f)
            feriados_validados.append(f)

    simulacion_frontera = None
    if not errores:
        combinado = {2026: FERIADOS_BMV[2026], 2027: frozenset(feriados_validados)}
        actual = date(2027, 1, 15)
        while actual.weekday() >= 5 or actual.isoformat() in combinado[2027]:
            actual -= timedelta(days=1)
        ventana = []
        cursor = actual
        while len(ventana) < 21:
            if cursor.weekday() < 5 and cursor.isoformat() not in combinado[cursor.year]:
                ventana.append(cursor.isoformat())
            cursor -= timedelta(days=1)
        ventana.reverse()
        simulacion_frontera = {
            "corte_prueba": actual.isoformat(),
            "inicio_ventana_21": ventana[0],
            "fin_ventana_21": ventana[-1],
            "sesiones_2026": sum(1 for x in ventana if x.startswith("2026-")),
            "sesiones_2027": sum(1 for x in ventana if x.startswith("2027-")),
        }

    return {
        "version": 1,
        "generado_en_utc": datetime.now(timezone.utc).isoformat(),
        "anio": 2027,
        "valido_para_promocion": not errores,
        "total_feriados_2027": len(feriados_validados),
        "simulacion_frontera_2026_2027": simulacion_frontera,
        "errores": errores,
        "habilita_operacion": False,
        "nota": "Validar evidencia no modifica automáticamente calendario_bmv.py ni reempaqueta Lambdas.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--guardar-s3", action="store_true")
    args = p.parse_args()

    import boto3
    s3 = boto3.client("s3", region_name=args.region)
    propuesta = leer_json(s3, args.bucket, PREFIJO_CAL_2027 + "estado.json", opcional=True)
    reporte = validar_propuesta_2027(s3, args.bucket, propuesta)
    if args.guardar_s3:
        clave = f"evidencias/auditorias/validacion_calendario_2027_{timestamp_slug()}.json"
        reporte["reporte_s3"] = escribir_json_inmutable(s3, args.bucket, clave, reporte)
    print(json.dumps(reporte, ensure_ascii=False, indent=2))
    if not reporte["valido_para_promocion"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
