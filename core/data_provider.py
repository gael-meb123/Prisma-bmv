"""
Prisma BMV - Proveedor de Datos de Mercado, Señales Cuantitativas e Integridad
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

FILE_MONITOREO = ROOT / "monitoreo_ppp_multiemisora_en_vivo.csv"
FILE_SENALES_WALMEX = ROOT / "registro_senales_prospectivas_walmex.csv"
FILE_SENALES_PANEL = ROOT / "registro_senales_prospectivas_panel_g2.csv"
FILE_SERIE_WALMEX = ROOT / "serie_ppp_walmex_prospectiva.csv"


def cargar_monitoreo_en_vivo() -> pd.DataFrame:
    if not FILE_MONITOREO.exists():
        return pd.DataFrame()
    df = pd.read_csv(FILE_MONITOREO)
    df["ppp_bmv_mxn"] = pd.to_numeric(df["ppp_bmv_mxn"], errors="coerce")
    df["variacion_ppp_vs_anterior_pct"] = pd.to_numeric(
        df["variacion_ppp_vs_anterior_pct"], errors="coerce"
    )
    return df


def cargar_senales_walmex() -> pd.DataFrame:
    if not FILE_SENALES_WALMEX.exists():
        return pd.DataFrame()
    df = pd.read_csv(FILE_SENALES_WALMEX)
    df["prob_subida_pct"] = pd.to_numeric(df["prob_subida_pct"], errors="coerce")
    df["ppp_base_mxn"] = pd.to_numeric(df["ppp_base_mxn"], errors="coerce")
    return df


def cargar_senales_panel_g2() -> pd.DataFrame:
    if not FILE_SENALES_PANEL.exists():
        return pd.DataFrame()
    df = pd.read_csv(FILE_SENALES_PANEL)
    df["probabilidad_subida"] = pd.to_numeric(df["probabilidad_subida"], errors="coerce")
    df["ppp_base_t"] = pd.to_numeric(df["ppp_base_t"], errors="coerce")
    df["ret_10_rel_panel"] = pd.to_numeric(df["ret_10_rel_panel"], errors="coerce")
    df["retorno_parcial_pct"] = pd.to_numeric(df["retorno_parcial_pct"], errors="coerce")
    df["ppp_parcial_reciente"] = pd.to_numeric(df["ppp_parcial_reciente"], errors="coerce")
    return df


def cargar_serie_walmex() -> pd.DataFrame:
    if not FILE_SERIE_WALMEX.exists():
        return pd.DataFrame()
    df = pd.read_csv(FILE_SERIE_WALMEX)
    df["ppp_oficial_bmv"] = pd.to_numeric(df["ppp_oficial_bmv"], errors="coerce")
    return df


def obtener_fechas_mercado() -> list[str]:
    df = cargar_monitoreo_en_vivo()
    if df.empty or "fecha" not in df.columns:
        return ["2026-10-30", "2026-10-29", "2026-10-28"]
    fechas = sorted(df["fecha"].dropna().unique().tolist(), reverse=True)
    return fechas


def obtener_kpis_mercado(fecha: str | None = None) -> dict[str, Any]:
    df = cargar_monitoreo_en_vivo()
    if df.empty:
        return {}

    if fecha is None:
        fecha = df["fecha"].max()

    sub = df[df["fecha"] == fecha]
    verificadas = sub[sub["estado_captura"] == "PPP_PUBLICADO_VERIFICADO"]
    ausentes = sub[sub["estado_captura"] == "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA"]

    alzas = verificadas[verificadas["variacion_ppp_vs_anterior_pct"] > 0]
    bajas = verificadas[verificadas["variacion_ppp_vs_anterior_pct"] < 0]

    top_alza = verificadas.sort_values("variacion_ppp_vs_anterior_pct", ascending=False).head(1)
    top_baja = verificadas.sort_values("variacion_ppp_vs_anterior_pct", ascending=True).head(1)

    sha = sub["sha256_boletin"].iloc[0] if "sha256_boletin" in sub.columns and not sub.empty else "N/A"
    url = sub["url_fuente"].iloc[0] if "url_fuente" in sub.columns and not sub.empty else "https://www.bmv.com.mx"

    return {
        "fecha": fecha,
        "total_emisoras": len(sub),
        "total_verificadas": len(verificadas),
        "total_ausentes": len(ausentes),
        "conteo_alzas": len(alzas),
        "conteo_bajas": len(bajas),
        "top_alza_ticker": top_alza["emisora"].iloc[0] if not top_alza.empty else "N/D",
        "top_alza_pct": top_alza["variacion_ppp_vs_anterior_pct"].iloc[0] if not top_alza.empty else 0.0,
        "top_baja_ticker": top_baja["emisora"].iloc[0] if not top_baja.empty else "N/D",
        "top_baja_pct": top_baja["variacion_ppp_vs_anterior_pct"].iloc[0] if not top_baja.empty else 0.0,
        "sha256_boletin": sha,
        "url_fuente": url,
    }
