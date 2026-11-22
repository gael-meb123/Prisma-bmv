"""Compuerta previa a habilitar observaciones secundarias Yahoo Finance en producción.

Devuelve código de salida 0 únicamente cuando ``evidencias/observaciones_yahoo/estado_permiso.json``
registra permiso APROBADO y existen observaciones válidas archivadas bajo ``observaciones/yahoo/``.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prisma.data.evidencias_s3 import (
    BUCKET_PRODUCTIVO,
    escribir_json_inmutable,
    leer_json,
    timestamp_slug,
    verificar_permiso_yahoo,
)
from prisma.data.yahoo_secundario import interpretar_cierre


def evaluar_habilitacion_yahoo(s3, bucket: str) -> dict:
    permiso = leer_json(s3, bucket, "evidencias/observaciones_yahoo/estado_permiso.json", opcional=True)
    ok_permiso, errores = verificar_permiso_yahoo(permiso)

    page = s3.list_objects_v2(Bucket=bucket, Prefix="observaciones/yahoo/", MaxKeys=50)
    claves = [x["Key"] for x in page.get("Contents", []) if x["Key"].endswith(".json")]
    validas = []
    invalidas = []
    for key in claves:
        partes = key.split("/")
        if len(partes) != 4:
            invalidas.append({"key": key, "error": "Ruta inesperada"})
            continue
        simbolo = partes[2]
        fecha = partes[3].removesuffix(".json")
        try:
            raw = s3.get_object(Bucket=bucket, Key=key)["Body"].read(2_000_001)
            dato = interpretar_cierre(raw, simbolo, fecha)
            validas.append({"key": key, "simbolo": simbolo, "fecha": fecha, "sha256": dato["sha256_respuesta"]})
        except Exception as exc:
            invalidas.append({"key": key, "error": str(exc)})

    if not validas:
        errores.append("No hay observaciones secundarias válidas archivadas bajo observaciones/yahoo/.")
    if invalidas:
        errores.append(f"Se detectaron {len(invalidas)} observaciones inválidas bajo observaciones/yahoo/.")

    listo = ok_permiso and bool(validas) and not invalidas
    return {
        "version": 1,
        "generado_en_utc": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "estado_permiso": permiso.get("estado") if isinstance(permiso, dict) else "AUSENTE",
        "listo_para_activar_produccion": listo,
        "observaciones_validas": len(validas),
        "observaciones_invalidas": invalidas,
        "errores": errores,
        "flags_requeridos_al_aprobar": {
            "cloudformation_api": "YahooObservacionesHabilitadas=true",
            "frontend_build": "VITE_YAHOO_OBSERVACIONES=true",
        },
        "separacion_estricta": "Observación secundaria nunca alimenta PPP BMV, Silver ni modelos.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--guardar-s3", action="store_true")
    args = p.parse_args()

    import boto3
    s3 = boto3.client("s3", region_name=args.region)
    reporte = evaluar_habilitacion_yahoo(s3, args.bucket)
    if args.guardar_s3:
        clave = f"evidencias/auditorias/habilitacion_yahoo_{timestamp_slug()}.json"
        reporte["reporte_s3"] = escribir_json_inmutable(s3, args.bucket, clave, reporte)
    print(json.dumps(reporte, ensure_ascii=False, indent=2))
    if not reporte["listo_para_activar_produccion"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
