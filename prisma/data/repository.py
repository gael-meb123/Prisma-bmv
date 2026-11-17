"""
Prisma BMV - Repositorios de datos intercambiables.

Las vistas consumen siempre el mismo contrato (`RepositorioDatos`) sin saber si los datos
vienen de CSV locales, directamente de S3 o de Amazon Athena. La fuente se elige con
PRISMA_DATA_SOURCE = local | s3 | athena.

Normalizaciones que se aplican al leer (en un solo lugar):
* Solo las 15 emisoras de la lista oficial (se descartan capturas fuera de lista).
* El estado de hueco se unifica a NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA.
* Tipos numéricos explícitos; los huecos quedan como NaN, nunca como 0.
"""

from __future__ import annotations

import io
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd

from prisma.domain import bmv_core as core
from prisma.settings import Settings

COLUMNAS_NUM_PRECIOS = ("ppp_bmv_mxn", "ultimo_bmv_mxn", "anterior_bmv_mxn", "variacion_ppp_vs_anterior_pct")
COLUMNAS_NUM_G2 = (
    "probabilidad_subida", "ppp_base_t", "ret_10", "ret_10_rel_panel", "volatilidad_20",
    "media_ret_10_panel_corte", "retorno_parcial_pct", "ppp_parcial_reciente", "ppp_t5_observado",
    "target_y_observado", "acierto_direccional_t5", "brier_observado_t5", "prediccion_clase",
    "sesiones_transcurridas", "c_regularizacion", "tau_zona_neutral",
)
COLUMNAS_NUM_G1 = ("ppp_base_mxn", "prob_subida_h5", "prob_subida_pct", "prediccion_clase",
                   "ppp_t5_mxn", "retorno_real_h5_pct", "y_real_h5", "acierto", "brier_individual")

KEY_SERIE = "silver/serie_unificada_reciente.csv"
KEY_G2 = "gold/senales_g2/registro_senales_prospectivas_panel_g2.csv"
KEY_G1 = "gold/senales_g1/registro_senales_prospectivas_walmex.csv"
KEY_MODELOS = "gold/modelos/registro_modelos_g2_oficial.json"


def normalizar_precios(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    oficiales = {t for t, *_ in core.EMISORAS_15}
    df = df[df["emisora"].isin(oficiales)]
    if "en_lista_oficial" in df.columns:
        # Filas sin la columna (series históricas) pertenecen a la lista oficial por construcción.
        fuera = df["en_lista_oficial"].map(lambda v: str(v).strip().lower() in ("false", "0", "0.0"))
        df = df[~fuera]
    df["fecha"] = df["fecha"].astype(str).str[:10]
    df["estado_captura"] = core.normalizar_estado_captura(df["estado_captura"].astype(str))
    for c in COLUMNAS_NUM_PRECIOS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # Sector y anillo vienen del catálogo; la serie se conserva tal como la publicó la BMV
    # (p. ej. AMX L antes de la unificación de series) y solo se completa si falta.
    df["sector_economico"] = df["emisora"].map(lambda e: core.META_EMISORA[e]["sector"])
    df["anillo_madurez"] = df["emisora"].map(lambda e: core.META_EMISORA[e]["anillo"])
    serie_cat = df["emisora"].map(lambda e: core.META_EMISORA[e]["serie"])
    df["serie"] = df["serie"].where(df["serie"].notna(), serie_cat) if "serie" in df else serie_cat
    return df.drop_duplicates(["fecha", "emisora"], keep="last").sort_values(["fecha", "emisora"]).reset_index(drop=True)


def normalizar_g2(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    for c in COLUMNAS_NUM_G2:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "acierto_parcial_en_curso" in df.columns:
        df["acierto_parcial_en_curso"] = df["acierto_parcial_en_curso"].map(core._a_bool)
    return df


def normalizar_g1(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    if "prob_subida_pct" in df.columns:
        df["prob_subida_pct"] = df["prob_subida_pct"].astype(str).str.rstrip("%")
    for c in COLUMNAS_NUM_G1:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["valida"] = ~df.get("estado_validez", pd.Series("VALIDA", index=df.index)).astype(str).str.startswith("ANULADA")
    return df


class RepositorioDatos(ABC):
    nombre_fuente = "desconocida"

    @abstractmethod
    def _precios_crudos(self) -> pd.DataFrame: ...

    @abstractmethod
    def _g2_crudo(self) -> pd.DataFrame: ...

    @abstractmethod
    def _g1_crudo(self) -> pd.DataFrame: ...

    @abstractmethod
    def modelos_g2(self) -> dict[str, Any]: ...

    def precios(self) -> pd.DataFrame:
        return normalizar_precios(self._precios_crudos())

    def senales_g2(self) -> pd.DataFrame:
        return normalizar_g2(self._g2_crudo())

    def senales_g1(self) -> pd.DataFrame:
        return normalizar_g1(self._g1_crudo())


class RepositorioLocal(RepositorioDatos):
    nombre_fuente = "Archivos locales (instantánea del lakehouse)"

    def __init__(self, directorio: Path, archivo_modelos: Path | None = None):
        self.dir = Path(directorio)
        self.archivo_modelos = Path(archivo_modelos) if archivo_modelos else self.dir / "modelos" / "registro_modelos_g2_oficial.json"

    def _csv(self, nombre: str) -> pd.DataFrame:
        ruta = self.dir / nombre
        return pd.read_csv(ruta) if ruta.exists() else pd.DataFrame()

    def _precios_crudos(self) -> pd.DataFrame:
        partes = [self._csv("serie_unificada_reciente.csv"), self._csv("monitoreo_ppp_multiemisora_en_vivo.csv")]
        partes = [p for p in partes if not p.empty]
        return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()

    def _g2_crudo(self) -> pd.DataFrame:
        return self._csv("registro_senales_prospectivas_panel_g2.csv")

    def _g1_crudo(self) -> pd.DataFrame:
        return self._csv("registro_senales_prospectivas_walmex.csv")

    def modelos_g2(self) -> dict[str, Any]:
        ruta = self.archivo_modelos
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}

    def bronze_local(self, fecha_yyyymmdd: str) -> tuple[bytes | None, str | None]:
        base = self.dir / "bronze" / fecha_yyyymmdd[:4] / fecha_yyyymmdd[4:6] / f"boletin_{fecha_yyyymmdd}"
        html = base.with_suffix(".html")
        sha = base.with_suffix(".sha256")
        return (html.read_bytes() if html.exists() else None,
                sha.read_text().strip() if sha.exists() else None)


class RepositorioS3(RepositorioDatos):
    nombre_fuente = "Amazon S3 (capas Silver y Gold)"

    def __init__(self, bucket: str, region: str):
        import boto3

        if not bucket:
            raise ValueError("Configure PRISMA_S3_BUCKET para usar la fuente S3.")
        self.bucket = bucket
        self._s3 = boto3.client("s3", region_name=region)

    def _leer(self, key: str) -> bytes | None:
        try:
            return self._s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self._s3.exceptions.NoSuchKey:
            return None

    def _csv(self, key: str) -> pd.DataFrame:
        cuerpo = self._leer(key)
        return pd.read_csv(io.BytesIO(cuerpo), encoding="utf-8-sig") if cuerpo else pd.DataFrame()

    def _precios_crudos(self) -> pd.DataFrame:
        return self._csv(KEY_SERIE)

    def _g2_crudo(self) -> pd.DataFrame:
        return self._csv(KEY_G2)

    def _g1_crudo(self) -> pd.DataFrame:
        return self._csv(KEY_G1)

    def modelos_g2(self) -> dict[str, Any]:
        cuerpo = self._leer(KEY_MODELOS)
        return json.loads(cuerpo) if cuerpo else {}

    def bronze(self, fecha_yyyymmdd: str) -> tuple[bytes | None, str | None]:
        base = f"bronze/{fecha_yyyymmdd[:4]}/{fecha_yyyymmdd[4:6]}/boletin_{fecha_yyyymmdd}"
        html, sha = self._leer(f"{base}.html"), self._leer(f"{base}.sha256")
        return html, (sha.decode().strip() if sha else None)


class RepositorioAthena(RepositorioS3):
    """Silver y Gold vía SQL en Athena; el registro de modelos y Bronze se leen de S3."""

    nombre_fuente = "Amazon Athena (SQL sobre el lakehouse)"

    def __init__(self, settings: Settings):
        from prisma.data.athena import ClienteAthena

        super().__init__(settings.s3_bucket, settings.aws_region)
        self._athena = ClienteAthena(
            settings.athena_database, settings.athena_workgroup, settings.salida_athena,
            settings.aws_region, settings.athena_timeout_s,
        )

    @property
    def cliente_athena(self):
        return self._athena

    def _precios_crudos(self) -> pd.DataFrame:
        sql = (
            "SELECT * FROM bmv_silver_ppp "
            "WHERE anio >= year(current_date) - 1 "
            "AND fecha >= date_format(date_add('day', -120, current_date), '%Y-%m-%d')"
        )
        return self._athena.ejecutar(sql).datos

    def _g2_crudo(self) -> pd.DataFrame:
        return self._athena.ejecutar("SELECT * FROM bmv_gold_senales_g2").datos

    def _g1_crudo(self) -> pd.DataFrame:
        return self._athena.ejecutar("SELECT * FROM bmv_gold_senales_g1").datos


def crear_repositorio(settings: Settings) -> RepositorioDatos:
    if settings.fuente_datos == "s3":
        return RepositorioS3(settings.s3_bucket, settings.aws_region)
    if settings.fuente_datos == "athena":
        return RepositorioAthena(settings)
    return RepositorioLocal(settings.dir_datos)
