"""Contrato comun de variables, sesiones, etiquetas y trazabilidad PPP (v2)."""

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
VERSION_METODOLOGIA = "PPP_EVALUACION_V2"
VERSION_FEATURES = "PPP_V2_MEDIA20"
FEATURE_NAMES = [
    "ret_1", "ret_5", "ret_10", "ret_20", "volatilidad_5",
    "volatilidad_20", "distancia_media_5", "distancia_media_20",
]
CORTE_TRAIN = "2025-04-29"
CORTE_TEST = "2026-10-27"
# Fuente: https://www.bmv.com.mx/es/grupo-bmv/calendario-de-dias-festivos
FERIADOS_BMV_2026 = {
    "2026-01-01", "2026-02-02", "2026-03-16", "2026-04-02", "2026-04-03",
    "2026-05-01", "2026-09-16", "2026-11-02", "2026-11-16", "2026-12-12", "2026-12-25",
}


def localizar_insumo(nombre):
    candidatos = [ROOT.parent / "Parcial 3" / nombre, Path.home() / "Downloads" / nombre]
    return next((p for p in candidatos if p.exists()), candidatos[0])


@lru_cache(maxsize=1)
def rejilla_historica():
    df = pd.read_csv(ROOT / "serie_ppp_historica_15_emisoras_bmv.csv", usecols=["fecha", "posicion_sesion"])
    grid = df.drop_duplicates().sort_values("posicion_sesion")
    if grid.fecha.duplicated().any() or grid.posicion_sesion.duplicated().any():
        raise ValueError("Rejilla historica ambigua")
    return tuple(grid.fecha.astype(str))


def is_bmv_business_day(d_obj):
    if d_obj.year == 2026:
        return d_obj.weekday() < 5 and d_obj.isoformat() not in FERIADOS_BMV_2026
    grid = rejilla_historica()
    iso = d_obj.isoformat()
    if grid[0] <= iso <= grid[-1]:
        return iso in _fechas_historicas()
    raise ValueError(f"Calendario BMV no verificado para {iso}; se requiere calendario oficial")


@lru_cache(maxsize=1)
def _fechas_historicas():
    return frozenset(rejilla_historica())


def sesiones_entre(inicio, fin):
    curr, end = date.fromisoformat(str(inicio)), date.fromisoformat(str(fin))
    sesiones = []
    while curr <= end:
        if is_bmv_business_day(curr):
            sesiones.append(curr.isoformat())
        curr += timedelta(days=1)
    return sesiones


def add_bmv_sessions(start_date_str, n_sessions=5):
    if not isinstance(n_sessions, int) or n_sessions < 0:
        raise ValueError("n_sessions debe ser entero no negativo")
    curr = date.fromisoformat(start_date_str)
    if not is_bmv_business_day(curr):
        raise ValueError(f"La fecha base {start_date_str} no es sesion BMV")
    added = 0
    while added < n_sessions:
        curr += timedelta(days=1)
        if is_bmv_business_day(curr):
            added += 1
    return curr.isoformat()


def calendario_objetivo(fecha_senal, fecha_objetivo):
    sesiones_entre(fecha_senal, fecha_objetivo)  # Rechaza periodos sin calendario verificado.
    return "OFICIAL_2026" if fecha_senal[:4] == fecha_objetivo[:4] == "2026" else "REJILLA_HISTORICA_9C_9G"


def calcular_features_ppp(ventana):
    p = np.asarray(ventana, dtype=float)
    if p.shape != (21,) or not np.all(np.isfinite(p) & (p > 0)):
        raise ValueError("Se requieren 21 PPP finitos y positivos, sin imputacion")
    rets = p[1:] / p[:-1] - 1.0
    return np.array([
        p[-1] / p[-2] - 1.0, p[-1] / p[-6] - 1.0,
        p[-1] / p[-11] - 1.0, p[-1] / p[0] - 1.0,
        np.std(rets[-5:], ddof=1), np.std(rets, ddof=1),
        p[-1] / np.mean(p[-5:]) - 1.0, p[-1] / np.mean(p[-20:]) - 1.0,
    ], dtype=float)


def validar_ventana_fechas(fechas, fecha_corte):
    fechas = list(map(str, fechas))
    if len(fechas) != 21 or fechas[-1] != fecha_corte:
        raise ValueError("La ventana debe terminar exactamente en la fecha solicitada y contener 21 sesiones")
    if fechas != sesiones_entre(fechas[0], fecha_corte):
        raise ValueError("Hueco o fecha no bursatil en la ventana de 21 sesiones")


def mascara_etiquetas_conocidas(df, fecha_corte, objetivo="fecha_objetivo_h5", fecha="fecha"):
    """Contrato diario: el precio objetivo debe estar observado al cierre del corte."""
    targets = pd.to_datetime(df[objetivo], errors="coerce")
    origins = pd.to_datetime(df[fecha], errors="coerce")
    corte = pd.Timestamp(fecha_corte)
    return targets.notna() & origins.notna() & (targets > origins) & (targets <= corte) & (origins <= corte)


def seleccionar_train_test(df):
    tr = df.periodo_oficial.eq("TRAIN") & df.target_disponible.eq(True)
    te = df.periodo_oficial.eq("TEST") & df.target_disponible.eq(True)
    tr &= mascara_etiquetas_conocidas(df, CORTE_TRAIN)
    te &= mascara_etiquetas_conocidas(df, CORTE_TEST)
    return df.loc[tr].copy(), df.loc[te].copy()


def agregar_trazabilidad(df):
    """Agrega metadatos sin inventar timestamps ni cambiar predicciones originales."""
    df = df.copy()
    for col in ["fecha_corte_datos", "fecha_emision_real", "estado_trazabilidad_emision", "version_features", "version_metodologia"]:
        if col not in df:
            df[col] = pd.Series(index=df.index, dtype=object)
        else:
            # Un CSV con toda la columna vacia se relee como float64.
            df[col] = df[col].astype(object)
    df["fecha_corte_datos"] = df["fecha_corte_datos"].fillna(df["fecha_senal"])
    if "timestamp_emision_utc" not in df:
        df["timestamp_emision_utc"] = "NO_DOCUMENTADO"
    for idx, row in df.iterrows():
        ts = pd.to_datetime(row["timestamp_emision_utc"], errors="coerce", utc=True)
        if pd.isna(ts):
            df.loc[idx, "estado_trazabilidad_emision"] = "TIMESTAMP_ORIGINAL_NO_DOCUMENTADO"
        else:
            df.loc[idx, "fecha_emision_real"] = ts.tz_convert("America/Mexico_City").date().isoformat()
            df.loc[idx, "estado_trazabilidad_emision"] = "TIMESTAMP_DOCUMENTADO"
        if pd.isna(row["version_features"]):
            versiones = {"GMEXICO": "PPP_LEGADO_MEDIA21", "WALMEX": "PPP_LEGADO_WALMEX_MEDIA20"}
            df.loc[idx, "version_features"] = versiones.get(row["emisora"], "LEGADO_DEFINICION_NO_DOCUMENTADA")
        if pd.isna(row["version_metodologia"]):
            df.loc[idx, "version_metodologia"] = "LEGADO_PRE_CORRECCION_V2"
    return df


def timestamp_utc():
    return datetime.now(timezone.utc).isoformat()
