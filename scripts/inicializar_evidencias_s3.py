"""Inicializa el prefijo inmutable ``evidencias/`` en S3 sin crear carpetas locales."""
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
    declaracion_gobernanza,
    escribir_json_inmutable,
    estado_calendario_2027,
    estado_permiso_yahoo,
)
from prisma.domain.catalogo_ipc import (
    cargar_catalogo_versionado,
    catalogo_naftrac_20261117,
    convertir_provisional_a_versionado,
)


def inicializar_en_s3(s3, bucket: str, fecha_iso: str | None = None) -> dict:
    ahora = fecha_iso or datetime.now(timezone.utc).isoformat()
    catalogo_v = convertir_provisional_a_versionado(catalogo_naftrac_20261117())
    # Valida estructura antes de escribir en S3.
    cargar_catalogo_versionado(catalogo_v)
    return {
        "bucket": bucket,
        "gobernanza": escribir_json_inmutable(
            s3, bucket, "evidencias/gobernanza/declaracion_fuentes.json", declaracion_gobernanza(ahora)
        ),
        "yahoo_permiso": escribir_json_inmutable(
            s3, bucket, "evidencias/observaciones_yahoo/estado_permiso.json", estado_permiso_yahoo(ahora)
        ),
        "calendario_2027": escribir_json_inmutable(
            s3, bucket, "evidencias/calendario_bmv/2027/estado.json", estado_calendario_2027(ahora)
        ),
        "catalogo_ipc_provisional": escribir_json_inmutable(
            s3, bucket, "evidencias/catalogo_ipc/provisional/naftrac_2026-11-17_v1.json", catalogo_v
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    p.add_argument("--region", default="us-east-1")
    args = p.parse_args()

    import boto3
    s3 = boto3.client("s3", region_name=args.region)
    print(json.dumps(inicializar_en_s3(s3, args.bucket), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
