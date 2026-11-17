"""
Prisma BMV - Configuración centralizada (12-factor: todo por variables de entorno).

No importa Streamlit: así los servicios y las pruebas pueden usarla sin servidor.
`app.py` copia los valores de `st.secrets` al entorno antes de leer esta configuración.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _bool(nombre: str, defecto: bool) -> bool:
    v = os.environ.get(nombre)
    return defecto if v is None else v.strip().lower() in ("1", "true", "si", "sí", "yes")


@dataclass(frozen=True)
class Settings:
    entorno: str = "development"
    fuente_datos: str = "local"  # local | s3 | athena
    dir_datos: Path = RAIZ / "datos"
    dir_estado: Path = RAIZ / ".estado"
    llave_maestra: str = ""
    pbkdf2_iteraciones: int = 600_000
    sembrar_demo: bool = True

    aws_region: str = "us-east-1"
    s3_bucket: str = ""
    athena_database: str = "prisma_bmv"
    athena_workgroup: str = "primary"
    athena_output: str = ""
    athena_timeout_s: int = 45
    athena_max_filas: int = 5_000

    anthropic_api_key: str = field(default="", repr=False)
    prismi_modelo: str = "claude-sonnet-5-5"
    prismi_cuota_explorer_diaria: int = 5

    @property
    def es_produccion(self) -> bool:
        return self.entorno == "production"

    @property
    def salida_athena(self) -> str:
        return self.athena_output or (f"s3://{self.s3_bucket}/athena-results/" if self.s3_bucket else "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    entorno = os.environ.get("PRISMA_ENV", "development").strip().lower()
    return Settings(
        entorno=entorno,
        fuente_datos=os.environ.get("PRISMA_DATA_SOURCE", "local").strip().lower(),
        dir_datos=Path(os.environ.get("PRISMA_DATA_DIR", RAIZ / "datos")),
        dir_estado=Path(os.environ.get("PRISMA_STATE_DIR", RAIZ / ".estado")),
        llave_maestra=os.environ.get("PRISMA_MASTER_KEY", "").strip(),
        pbkdf2_iteraciones=int(os.environ.get("PRISMA_PBKDF2_ITER", "600000")),
        sembrar_demo=_bool("PRISMA_SEED_DEMO", entorno != "production"),
        aws_region=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")),
        s3_bucket=os.environ.get("PRISMA_S3_BUCKET", "").strip(),
        athena_database=os.environ.get("PRISMA_ATHENA_DATABASE", "prisma_bmv"),
        athena_workgroup=os.environ.get("PRISMA_ATHENA_WORKGROUP", "primary"),
        athena_output=os.environ.get("PRISMA_ATHENA_OUTPUT", "").strip(),
        athena_timeout_s=int(os.environ.get("PRISMA_ATHENA_TIMEOUT_S", "45")),
        athena_max_filas=int(os.environ.get("PRISMA_ATHENA_MAX_FILAS", "5000")),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        prismi_modelo=os.environ.get("PRISMI_MODEL", "claude-sonnet-5-5").strip(),
        prismi_cuota_explorer_diaria=int(os.environ.get("PRISMI_EXPLORER_DAILY_QUOTA", "5")),
    )
