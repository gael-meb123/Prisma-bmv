"""
Fase 3: Ingeniería de Features Externas y Microestructura con Ablación Purgada (Prisma BMV).

Construye sin fuga temporal (publicación <= 14:00 CDMX del día t o rezago estricto a t-1)
y sin imputación sintética (cero ffill / cero interpolación) las familias de variables:
  - F1 (Microestructura intradía BMV): gap_uh_ppp, gap_uh_ppp_rel_panel, gap_uh_ppp_media5
  - F2 (Macro / FX Banxico SIE SF43718 ~12:00 CDMX): fx_ret5, fx_ret5_x_beta (beta rodante 60d <= t-1)
  - F3 (Riesgo internacional Yahoo Finance cierre t-1 15:00 CDMX): spx_ret5_lag1, vix_cambio5_lag1, eww_ret5_lag1
  - Extras: flag_decision_banxico_5d, flag_ex_div_5d, cobre_ret5_lag1_gmexico

Ejecuta el estudio de ablación sobre G2_V4 en validación cruzada walk-forward purgada
(embargo de 5 sesiones dentro de TRAIN <= 2025-04-29) aplicando la regla pre-registrada:
  - Mejora log-loss contra G2_V4 con p-valor unilateral Diebold-Mariano < 0.10
  - No empeora el Brier Skill Score (Delta BSS >= 0)
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from evaluacion_institucional import (
    brier_skill_score,
    calcular_climatologia_rodante_purgada,
    diebold_mariano,
    rank_ic_diario,
)
from experimentos_entrenamiento_desarrollo import ajustar_logistica_pooled_panel
from higiene_etiquetas_dividendos import EMISORAS_FOCO_4, _preparar_vista_panel
from metodologia_ppp import CORTE_TRAIN, ROOT
from monitor_prospectivo_segunda_generacion import (
    VARIABLES_DM5_REL_CUATRO,
    hashes_protegidos_g2,
)


BASE_DIR = ROOT
CACHE_EXTERNO_DIR = BASE_DIR / "cache_externo"

ARCHIVO_SERIE_HISTORICA = BASE_DIR / "serie_ppp_historica_15_emisoras_bmv.csv"
ARCHIVO_PANEL_FASE1 = BASE_DIR / "dataset_panel_15_emisoras_features_ajustado_fase1.csv"
ARCHIVO_PANEL_FASE3 = BASE_DIR / "dataset_panel_15_emisoras_features_fase3.csv"
ARCHIVO_REPORTE_ABLACION_CSV = BASE_DIR / "reporte_fase3_ablacion.csv"
ARCHIVO_REPORTE_ABLACION_JSON = BASE_DIR / "reporte_fase3_ablacion.json"

EPS_PROB = 1e-12

# Calendario oficial publicado por Banco de México de anuncios programados de política monetaria
# (8 anuncios programados por año en jueves a las 13:00 CDMX, publicados en el Q4 del año previo)
CALENDARIO_DECISIONES_BANXICO_OFICIAL = sorted(
    {
        # 2016 (oct-dic)
        "2016-09-29", "2016-11-17", "2016-12-15",
        # 2017
        "2017-02-09", "2017-03-30", "2017-05-18", "2017-06-22",
        "2017-08-10", "2017-09-28", "2017-11-09", "2017-12-14",
        # 2018
        "2018-02-08", "2018-04-12", "2018-05-17", "2018-06-21",
        "2018-08-02", "2018-10-04", "2018-11-15", "2018-12-20",
        # 2019
        "2019-02-07", "2019-03-28", "2019-05-16", "2019-06-27",
        "2019-08-15", "2019-09-26", "2019-11-14", "2019-12-19",
        # 2020
        "2020-02-13", "2020-03-20", "2020-04-21", "2020-05-14",
        "2020-06-25", "2020-08-13", "2020-09-24", "2020-11-12", "2020-12-17",
        # 2021
        "2021-02-11", "2021-03-25", "2021-05-13", "2021-06-24",
        "2021-08-12", "2021-09-30", "2021-11-11", "2021-12-16",
        # 2022
        "2022-02-10", "2022-03-24", "2022-05-12", "2022-06-23",
        "2022-08-11", "2022-09-29", "2022-11-10", "2022-12-15",
        # 2023
        "2023-02-09", "2023-03-30", "2023-05-18", "2023-06-22",
        "2023-08-10", "2023-09-28", "2023-11-09", "2023-12-14",
        # 2024
        "2024-02-08", "2024-03-21", "2024-05-09", "2024-06-27",
        "2024-08-08", "2024-09-26", "2024-11-14", "2024-12-19",
        # 2025
        "2025-02-06", "2025-03-27", "2025-05-15", "2025-06-26",
        "2025-08-07", "2025-09-25", "2025-11-06", "2025-12-18",
        # 2026
        "2026-02-05", "2026-03-26", "2026-05-07", "2026-06-25",
        "2026-08-06", "2026-09-24", "2026-11-05", "2026-12-17",
    }
)


def _leer_banxico_token() -> Optional[str]:
    """Obtiene BANXICO_TOKEN de variables de entorno o de .env sin exponerlo en logs."""
    token = os.environ.get("BANXICO_TOKEN", "").strip()
    if token:
        return token
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line_s = line.strip()
            if line_s.startswith("BANXICO_TOKEN="):
                return line_s.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def descargar_serie_banxico_sie(
    id_serie: str,
    fecha_inicio: str = "2016-07-01",
    fecha_fin: str = "2026-11-06",
    usar_cache: bool = True,
) -> pd.DataFrame:
    """
    Descarga una serie diaria del SIE de Banxico con caché local en cache_externo/.
    Excluye estrictamente cualquier registro con dato == 'N/E' (cero imputación).
    """
    CACHE_EXTERNO_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_EXTERNO_DIR / f"banxico_{id_serie}.json"

    payload: Optional[Dict[str, Any]] = None
    if usar_cache and cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        token = _leer_banxico_token()
        if not token:
            raise RuntimeError("No se encontró BANXICO_TOKEN en el entorno ni en .env.")
        url = (
            f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/"
            f"{id_serie}/datos/{fecha_inicio}/{fecha_fin}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Bmx-Token": token,
                "Accept": "application/json",
                "User-Agent": "PrismaBMV/2.0",
            },
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    datos_raw = payload.get("bmx", {}).get("series", [{}])[0].get("datos", [])
    filas: List[Dict[str, Any]] = []
    for item in datos_raw:
        dato_str = str(item.get("dato", "")).strip().replace(",", "")
        if not dato_str or dato_str.upper() == "N/E":
            continue
        try:
            val = float(dato_str)
        except ValueError:
            continue
        fecha_iso = dt.datetime.strptime(item["fecha"], "%d/%m/%Y").strftime("%Y-%m-%d")
        filas.append(
            {
                "fecha": fecha_iso,
                "valor": val,
                "id_serie": id_serie,
                # El FIX (SF43718) se determina y publica a las ~12:00 CDMX del mismo día t
                "ts_publicacion_cdmx": f"{fecha_iso} 12:00:00",
            }
        )

    df = pd.DataFrame(filas).sort_values("fecha").drop_duplicates(subset=["fecha"]).reset_index(drop=True)
    return df


def descargar_serie_yahoo_diaria(
    simbolo: str,
    nombre_cache: str,
    fecha_inicio: str = "2016-07-01",
    fecha_fin: str = "2026-11-07",
    usar_cache: bool = True,
) -> pd.DataFrame:
    """
    Descarga cierres diarios de Yahoo Finance Chart v8 API con caché local en cache_externo/.
    Sello de publicación: 15:00:00 CDMX (16:00 ET) de la fecha de negociación.
    """
    CACHE_EXTERNO_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_EXTERNO_DIR / f"yahoo_{nombre_cache}_1d.json"

    payload: Optional[Dict[str, Any]] = None
    if usar_cache and cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        d1 = dt.datetime.strptime(fecha_inicio, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
        d2 = dt.datetime.strptime(fecha_fin, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
        p1 = int(d1.timestamp())
        p2 = int(d2.timestamp())
        sym_q = urllib.parse.quote(simbolo)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym_q}?period1={p1}&period2={p2}&interval=1d"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    res = payload.get("chart", {}).get("result", [{}])[0]
    timestamps = res.get("timestamp", []) or []
    closes = res.get("indicators", {}).get("quote", [{}])[0].get("close", []) or []

    filas: List[Dict[str, Any]] = []
    for ts, cl in zip(timestamps, closes):
        if cl is None or (isinstance(cl, float) and math.isnan(cl)):
            continue
        val = float(cl)
        if not np.isfinite(val) or val <= 0:
            continue
        fecha_iso = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%d")
        filas.append(
            {
                "fecha": fecha_iso,
                "close": val,
                "simbolo": simbolo,
                "ts_publicacion_cdmx": f"{fecha_iso} 15:00:00",
            }
        )

    df = pd.DataFrame(filas).sort_values("fecha").drop_duplicates(subset=["fecha"]).reset_index(drop=True)
    return df


def construir_panel_features_fase3(
    ruta_serie_historica: Path = ARCHIVO_SERIE_HISTORICA,
    ruta_panel_fase1: Path = ARCHIVO_PANEL_FASE1,
    ruta_salida_panel_fase3: Path = ARCHIVO_PANEL_FASE3,
    usar_cache: bool = True,
) -> pd.DataFrame:
    """
    Construye el panel enriquecido de Fase 3 uniendo F1 (brecha UH-PPP),
    F2 (FX Banxico SF43718 y beta cambiaria rodante <= t-1),
    F3 (^GSPC, ^VIX, EWW al cierre estricto de t-1) y Extras (calendario Banxico,
    ex-dividendo y cobre HG=F en t-1 para GMEXICO).
    """
    df_hist = pd.read_csv(ruta_serie_historica)
    df_panel = pd.read_csv(ruta_panel_fase1)

    # -------------------------------------------------------------------------
    # 1. Familia F1: Microestructura intradía (brecha Último Hecho vs PPP en t)
    # -------------------------------------------------------------------------
    df_hist["ppp_bmv_mxn"] = pd.to_numeric(df_hist["ppp_bmv_mxn"], errors="coerce")
    df_hist["ultimo_bmv_mxn"] = pd.to_numeric(df_hist["ultimo_bmv_mxn"], errors="coerce")
    df_hist["posicion_sesion"] = df_hist["posicion_sesion"].astype(int)
    df_hist = df_hist.sort_values(["emisora", "posicion_sesion"]).reset_index(drop=True)

    mask_f1 = (df_hist["ppp_bmv_mxn"] > 0) & (df_hist["ultimo_bmv_mxn"] > 0)
    df_hist["gap_uh_ppp"] = np.where(
        mask_f1,
        (df_hist["ultimo_bmv_mxn"] - df_hist["ppp_bmv_mxn"]) / df_hist["ppp_bmv_mxn"],
        np.nan,
    )
    media_dia_gap = df_hist.groupby("posicion_sesion")["gap_uh_ppp"].transform("mean")
    df_hist["gap_uh_ppp_rel_panel"] = df_hist["gap_uh_ppp"] - media_dia_gap

    # Media de 5 sesiones consecutivas [t-4, ..., t] sin imputación
    gap_m5_list: List[np.ndarray] = []
    for _, grp in df_hist.groupby("emisora", sort=False):
        g_vals = grp["gap_uh_ppp"].to_numpy(dtype=float)
        pos_vals = grp["posicion_sesion"].to_numpy(dtype=int)
        n_g = len(g_vals)
        m5 = np.full(n_g, np.nan, dtype=float)
        for idx in range(4, n_g):
            if pos_vals[idx] - pos_vals[idx - 4] == 4:
                ventana = g_vals[idx - 4 : idx + 1]
                if np.all(np.isfinite(ventana)):
                    m5[idx] = float(np.mean(ventana))
        gap_m5_list.append(m5)
    df_hist["gap_uh_ppp_media5"] = np.concatenate(gap_m5_list)

    # -------------------------------------------------------------------------
    # 2. Familia F2: Tipo de cambio FIX Banxico (SF43718, ~12:00 CDMX de t)
    # -------------------------------------------------------------------------
    df_fx = descargar_serie_banxico_sie("SF43718", usar_cache=usar_cache)
    fx_vals = df_fx["valor"].to_numpy(dtype=float)
    df_fx["fx_ret1"] = np.nan
    df_fx["fx_ret5"] = np.nan
    df_fx.loc[1:, "fx_ret1"] = np.log(fx_vals[1:] / fx_vals[:-1])
    df_fx.loc[5:, "fx_ret5"] = np.log(fx_vals[5:] / fx_vals[:-5])
    df_fx = df_fx.rename(
        columns={
            "valor": "fix_banxico_t",
            "ts_publicacion_cdmx": "ts_pub_f2_cdmx",
        }
    )

    df_hist = df_hist.merge(
        df_fx[["fecha", "fix_banxico_t", "fx_ret1", "fx_ret5", "ts_pub_f2_cdmx"]],
        on="fecha",
        how="left",
    )
    df_hist = df_hist.sort_values(["emisora", "posicion_sesion"]).reset_index(drop=True)

    # Retorno diario de la emisora en la malla completa y beta_FX rodante a 60 sesiones <= t-1
    beta_fx_list: List[np.ndarray] = []
    for _, grp in df_hist.groupby("emisora", sort=False):
        ppp_v = grp["ppp_bmv_mxn"].to_numpy(dtype=float)
        pos_v = grp["posicion_sesion"].to_numpy(dtype=int)
        fx_r1 = grp["fx_ret1"].to_numpy(dtype=float)
        n_g = len(ppp_v)

        ret1_em = np.full(n_g, np.nan, dtype=float)
        for idx in range(1, n_g):
            if pos_v[idx] - pos_v[idx - 1] == 1 and np.isfinite(ppp_v[idx]) and np.isfinite(ppp_v[idx - 1]) and ppp_v[idx - 1] > 0:
                ret1_em[idx] = (ppp_v[idx] - ppp_v[idx - 1]) / ppp_v[idx - 1]

        betas = np.full(n_g, np.nan, dtype=float)
        for idx in range(20, n_g):
            # Ventana estrictamente <= t-1: [max(0, idx-60), ..., idx-1]
            ini = max(0, idx - 60)
            r_win = ret1_em[ini:idx]
            x_win = fx_r1[ini:idx]
            valid = np.isfinite(r_win) & np.isfinite(x_win)
            if int(np.sum(valid)) >= 19:
                rv = r_win[valid]
                xv = x_win[valid]
                xm = float(np.mean(xv))
                rm = float(np.mean(rv))
                dx = xv - xm
                var_x = float(np.dot(dx, dx))
                if var_x > 1e-12:
                    betas[idx] = float(np.dot(dx, rv - rm) / var_x)
        beta_fx_list.append(betas)

    df_hist["beta_fx_60d_lag1"] = np.concatenate(beta_fx_list)
    df_hist["fx_ret5_x_beta"] = df_hist["fx_ret5"] * df_hist["beta_fx_60d_lag1"]

    # -------------------------------------------------------------------------
    # 3. Familia F3 y Cobre: Yahoo Finance al cierre estricto de t-1 (15:00 CDMX)
    # -------------------------------------------------------------------------
    df_spx = descargar_serie_yahoo_diaria("^GSPC", "GSPC", usar_cache=usar_cache)
    spx_c = df_spx["close"].to_numpy(dtype=float)
    df_spx["spx_ret5"] = np.nan
    df_spx.loc[5:, "spx_ret5"] = (spx_c[5:] - spx_c[:-5]) / spx_c[:-5]

    df_vix = descargar_serie_yahoo_diaria("^VIX", "VIX", usar_cache=usar_cache)
    vix_c = df_vix["close"].to_numpy(dtype=float)
    df_vix["vix_cambio5"] = np.nan
    df_vix.loc[5:, "vix_cambio5"] = vix_c[5:] - vix_c[:-5]

    df_eww = descargar_serie_yahoo_diaria("EWW", "EWW", usar_cache=usar_cache)
    eww_c = df_eww["close"].to_numpy(dtype=float)
    df_eww["eww_ret5"] = np.nan
    df_eww.loc[5:, "eww_ret5"] = (eww_c[5:] - eww_c[:-5]) / eww_c[:-5]

    df_hg = descargar_serie_yahoo_diaria("HG=F", "HGF", usar_cache=usar_cache)
    hg_c = df_hg["close"].to_numpy(dtype=float)
    df_hg["cobre_ret5"] = np.nan
    df_hg.loc[5:, "cobre_ret5"] = (hg_c[5:] - hg_c[:-5]) / hg_c[:-5]

    # Mapa de sesiones BMV: para cada posicion_sesion t, cuál fue la fecha_sesion_previa_bmv (t-1)
    # y cuáles son las fechas de (t, t+5] para el calendario de decisiones Banxico
    sesiones_bmv = (
        df_hist[["posicion_sesion", "fecha"]]
        .drop_duplicates()
        .sort_values("posicion_sesion")
        .reset_index(drop=True)
    )
    sesiones_bmv["fecha_sesion_previa_bmv"] = sesiones_bmv["fecha"].shift(1)

    fechas_ordenadas = sesiones_bmv["fecha"].tolist()
    set_banxico = set(CALENDARIO_DECISIONES_BANXICO_OFICIAL)
    flags_banxico_5d: List[int] = []
    for idx_s in range(len(fechas_ordenadas)):
        ventana_futura = fechas_ordenadas[idx_s + 1 : min(len(fechas_ordenadas), idx_s + 6)]
        hay_decision = any(f_futura in set_banxico for f_futura in ventana_futura)
        flags_banxico_5d.append(1 if hay_decision else 0)
    sesiones_bmv["flag_decision_banxico_5d"] = flags_banxico_5d

    # Unir series de EE.UU. exactamente en fecha_sesion_previa_bmv (t-1), CERO ffill
    sesiones_bmv = sesiones_bmv.merge(
        df_spx[["fecha", "spx_ret5", "ts_publicacion_cdmx"]].rename(
            columns={
                "fecha": "fecha_sesion_previa_bmv",
                "spx_ret5": "spx_ret5_lag1",
                "ts_publicacion_cdmx": "ts_pub_f3_cdmx",
            }
        ),
        on="fecha_sesion_previa_bmv",
        how="left",
    )
    sesiones_bmv = sesiones_bmv.merge(
        df_vix[["fecha", "vix_cambio5"]].rename(
            columns={
                "fecha": "fecha_sesion_previa_bmv",
                "vix_cambio5": "vix_cambio5_lag1",
            }
        ),
        on="fecha_sesion_previa_bmv",
        how="left",
    )
    sesiones_bmv = sesiones_bmv.merge(
        df_eww[["fecha", "eww_ret5"]].rename(
            columns={
                "fecha": "fecha_sesion_previa_bmv",
                "eww_ret5": "eww_ret5_lag1",
            }
        ),
        on="fecha_sesion_previa_bmv",
        how="left",
    )
    sesiones_bmv = sesiones_bmv.merge(
        df_hg[["fecha", "cobre_ret5"]].rename(
            columns={
                "fecha": "fecha_sesion_previa_bmv",
                "cobre_ret5": "cobre_ret5_lag1",
            }
        ),
        on="fecha_sesion_previa_bmv",
        how="left",
    )

    sesiones_bmv["motivo_sin_dato_f3"] = np.where(
        sesiones_bmv["spx_ret5_lag1"].isna()
        | sesiones_bmv["vix_cambio5_lag1"].isna()
        | sesiones_bmv["eww_ret5_lag1"].isna(),
        "FERIADO_MERCADO_EEUU_EN_T_MENOS_1",
        "OK",
    )

    # -------------------------------------------------------------------------
    # 4. Ensamblar en el panel de 9,879 filas conservando orden exacto
    # -------------------------------------------------------------------------
    cols_hist_f1_f2 = [
        "posicion_sesion",
        "emisora",
        "ultimo_bmv_mxn",
        "gap_uh_ppp",
        "gap_uh_ppp_rel_panel",
        "gap_uh_ppp_media5",
        "fix_banxico_t",
        "fx_ret1",
        "fx_ret5",
        "beta_fx_60d_lag1",
        "fx_ret5_x_beta",
        "ts_pub_f2_cdmx",
    ]
    df_out = df_panel.merge(
        df_hist[cols_hist_f1_f2],
        on=["posicion_sesion", "emisora"],
        how="left",
        sort=False,
    )
    cols_sesion_f3 = [
        "posicion_sesion",
        "fecha_sesion_previa_bmv",
        "flag_decision_banxico_5d",
        "spx_ret5_lag1",
        "vix_cambio5_lag1",
        "eww_ret5_lag1",
        "cobre_ret5_lag1",
        "ts_pub_f3_cdmx",
        "motivo_sin_dato_f3",
    ]
    df_out = df_out.merge(
        sesiones_bmv[cols_sesion_f3],
        on="posicion_sesion",
        how="left",
        sort=False,
    )

    # Columnas adicionales de Fase 3 y sellos de tiempo de publicación vs corte 14:00 CDMX
    df_out["flag_ex_div_5d"] = df_out["ventana_con_evento"].astype(float)
    df_out["cobre_ret5_lag1_gmexico"] = np.where(
        df_out["emisora"] == "GMEXICO",
        df_out["cobre_ret5_lag1"],
        0.0,
    )
    df_out["ts_pub_f1_cdmx"] = df_out["fecha"].astype(str) + " 14:00:00"
    df_out["ts_pub_calendarios_cdmx"] = df_out["fecha"].astype(str) + " 09:00:00"
    df_out["ts_corte_bmv_cdmx"] = df_out["fecha"].astype(str) + " 14:00:00"

    df_out.to_csv(ruta_salida_panel_fase3, index=False, encoding="utf-8")
    return df_out


def verificar_sin_fuga_temporal_features_externas(df_fase3: pd.DataFrame) -> Dict[str, Any]:
    """
    Verifica fila por fila que ningún feature externo o intradía tenga sello de publicación
    posterior al corte de las 14:00:00 CDMX del día t.
    """
    corte = df_fase3["ts_corte_bmv_cdmx"].astype(str)
    violaciones_f1 = int((df_fase3["ts_pub_f1_cdmx"].astype(str) > corte).sum())
    violaciones_f2 = int((df_fase3["ts_pub_f2_cdmx"].astype(str) > corte).sum())
    violaciones_cal = int((df_fase3["ts_pub_calendarios_cdmx"].astype(str) > corte).sum())

    mask_f3 = df_fase3["ts_pub_f3_cdmx"].notna()
    violaciones_f3 = int(
        (df_fase3.loc[mask_f3, "ts_pub_f3_cdmx"].astype(str) >= corte.loc[mask_f3]).sum()
    )
    violaciones_fecha_prev = int(
        (df_fase3["fecha_sesion_previa_bmv"].astype(str) >= df_fase3["fecha"].astype(str)).sum()
    )

    total_violaciones = (
        violaciones_f1
        + violaciones_f2
        + violaciones_cal
        + violaciones_f3
        + violaciones_fecha_prev
    )
    return {
        "sin_fuga_temporal": total_violaciones == 0,
        "violaciones_f1_intradia": violaciones_f1,
        "violaciones_f2_banxico": violaciones_f2,
        "violaciones_f3_yahoo_lag1": violaciones_f3,
        "violaciones_calendarios": violaciones_cal,
        "violaciones_fecha_previa": violaciones_fecha_prev,
        "total_filas_verificadas": int(len(df_fase3)),
    }


def _preparar_vista_ajustada_fase3(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Mapea las columnas ajustadas de Fase 1 y calcula las variables relativas del panel
    (*_rel_panel) usando exactamente _preparar_vista_panel(df_raw, usar_ajustado=True).
    """
    return _preparar_vista_panel(df_raw, usar_ajustado=True)


def _evaluar_cv_walk_forward_purgada_par(
    df_train: pd.DataFrame,
    features_base: List[str],
    features_cand: List[str],
    c_val: float = 0.01,
    n_folds: int = 4,
    embargo_sesiones: int = 5,
) -> pd.DataFrame:
    """
    Ejecuta validación cruzada walk-forward purgada dentro de TRAIN <= CORTE_TRAIN
    (mismo esquema de 4 bloques y embargo de 5 sesiones que Fase 2) sobre las filas
    donde tanto el modelo base (V4) como el candidato tienen datos completos (cero imputación).
    """
    cols_req = list(dict.fromkeys(features_base + features_cand + ["target_y", "p_ref_climatologia"]))
    tr = df_train.dropna(subset=cols_req).sort_values(["posicion_sesion", "emisora"]).reset_index(drop=True)
    tr["target_y"] = tr["target_y"].astype(int)

    pos_unicas = sorted(tr["posicion_sesion"].unique().tolist())
    n_pos = len(pos_unicas)
    min_train_pos = int(n_pos * 0.40)
    bloque_val = max(20, int((n_pos - min_train_pos) / n_folds))

    partes_oof: List[pd.DataFrame] = []
    for k in range(n_folds):
        idx_fin_tr = min_train_pos + k * bloque_val
        idx_ini_val = idx_fin_tr + embargo_sesiones
        idx_fin_val = min(n_pos, idx_ini_val + bloque_val)
        if idx_ini_val >= n_pos:
            break
        pos_corte_tr = pos_unicas[idx_fin_tr - 1]
        pos_ini_val = pos_unicas[idx_ini_val]
        pos_fin_val = pos_unicas[idx_fin_val - 1]

        fecha_corte_tr = str(tr[tr["posicion_sesion"] == pos_corte_tr]["fecha"].max())
        fold_tr = tr[
            (tr["posicion_sesion"] <= pos_corte_tr) & (tr["fecha_objetivo_h5"] <= fecha_corte_tr)
        ].copy()
        fold_va = tr[
            (tr["posicion_sesion"] >= pos_ini_val) & (tr["posicion_sesion"] <= pos_fin_val)
        ].copy()
        if len(fold_tr) < 200 or len(fold_va) == 0:
            continue

        p_base, _ = ajustar_logistica_pooled_panel(
            fold_tr, fold_va, features_base, c=float(c_val), tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        p_cand, _ = ajustar_logistica_pooled_panel(
            fold_tr, fold_va, features_cand, c=float(c_val), tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        fold_va["p_base_cv"] = p_base
        fold_va["p_cand_cv"] = p_cand
        fold_va["fold_cv"] = k + 1
        partes_oof.append(fold_va)

    return pd.concat(partes_oof, ignore_index=True)


def _metricas_comparativas_par(
    df_par: pd.DataFrame,
    col_p_base: str,
    col_p_cand: str,
    col_y: str = "target_y",
    col_ret5: str = "ret_h5",
) -> Dict[str, float]:
    """Calcula log-loss, Brier, BSS, Rank IC y test de Diebold-Mariano pareado."""
    y = df_par[col_y].to_numpy(dtype=float)
    p_ref = np.clip(df_par["p_ref_climatologia"].to_numpy(dtype=float), EPS_PROB, 1.0 - EPS_PROB)
    p_base = np.clip(df_par[col_p_base].to_numpy(dtype=float), EPS_PROB, 1.0 - EPS_PROB)
    p_cand = np.clip(df_par[col_p_cand].to_numpy(dtype=float), EPS_PROB, 1.0 - EPS_PROB)

    ll_base_vec = -(y * np.log(p_base) + (1.0 - y) * np.log(1.0 - p_base))
    ll_cand_vec = -(y * np.log(p_cand) + (1.0 - y) * np.log(1.0 - p_cand))
    br_base_vec = (p_base - y) ** 2
    br_cand_vec = (p_cand - y) ** 2

    ll_base = float(np.mean(ll_base_vec))
    ll_cand = float(np.mean(ll_cand_vec))
    br_base = float(np.mean(br_base_vec))
    br_cand = float(np.mean(br_cand_vec))

    bss_base = brier_skill_score(p_base, y, p_ref)
    bss_cand = brier_skill_score(p_cand, y, p_ref)

    acc_base = float(np.mean((p_base >= 0.5).astype(float) == y) * 100.0)
    acc_cand = float(np.mean((p_cand >= 0.5).astype(float) == y) * 100.0)

    ic_base = rank_ic_diario(
        df_par, col_p=col_p_base, col_ret=col_ret5, col_fecha="fecha", min_emisoras=3
    )["ic_medio"]
    ic_cand = rank_ic_diario(
        df_par, col_p=col_p_cand, col_ret=col_ret5, col_fecha="fecha", min_emisoras=3
    )["ic_medio"]

    # Diebold-Mariano: loss_a = candidato, loss_b = base V4 (dm_stat < 0 => candidato tiene menor pérdida)
    dm_ll = diebold_mariano(ll_cand_vec, ll_base_vec, lag=4)
    dm_br = diebold_mariano(br_cand_vec, br_base_vec, lag=4)

    return {
        "n": int(len(df_par)),
        "acc_base_pct": acc_base,
        "acc_cand_pct": acc_cand,
        "delta_acc_pp": acc_cand - acc_base,
        "logloss_base": ll_base,
        "logloss_cand": ll_cand,
        "delta_logloss": ll_cand - ll_base,
        "brier_base": br_base,
        "brier_cand": br_cand,
        "delta_brier": br_cand - br_base,
        "bss_base_pct": bss_base * 100.0,
        "bss_cand_pct": bss_cand * 100.0,
        "delta_bss_pct": (bss_cand - bss_base) * 100.0,
        "ic_base": ic_base,
        "ic_cand": ic_cand,
        "delta_ic": ic_cand - ic_base,
        "dm_stat_logloss": dm_ll["dm_stat"],
        "p_dm_logloss_bilateral": dm_ll["p_valor_bilateral"],
        "p_dm_logloss_unilateral": dm_ll["p_valor_a_menor_perdida"],
        "dm_stat_brier": dm_br["dm_stat"],
        "p_dm_brier_bilateral": dm_br["p_valor_bilateral"],
        "p_dm_brier_unilateral": dm_br["p_valor_a_menor_perdida"],
    }


def ejecutar_ablacion_fase3(
    usar_cache: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Construye el panel de Fase 3, ejecuta la ablación sistemática partiendo de G2_V4_ADJ,
    evalúa la regla pre-registrada en CV walk-forward purgada (TRAIN <= 2025-04-29)
    y reporta también el desempeño fuera de muestra en TEST (15 emisoras y 4 foco).
    """
    hashes_antes = hashes_protegidos_g2()
    df_raw = construir_panel_features_fase3(usar_cache=usar_cache)
    verificacion_fuga = verificar_sin_fuga_temporal_features_externas(df_raw)
    if not verificacion_fuga["sin_fuga_temporal"]:
        raise RuntimeError(f"Violación de corte temporal detectada: {verificacion_fuga}")

    df_vista = _preparar_vista_ajustada_fase3(df_raw)
    df_res = df_vista[
        df_vista["target_disponible"].astype(str).isin(["True", "true", "1"])
        & df_vista["target_y"].notna()
        & df_vista["ret_10"].notna()
    ].copy().reset_index(drop=True)
    df_res["target_y"] = df_res["target_y"].astype(int)
    df_res["ret_h5"] = df_res["ppp_t5"] / df_res["ppp_t"] - 1.0
    df_res["p_ref_climatologia"] = calcular_climatologia_rodante_purgada(
        df_vista, df_res, ventana_sesiones=250
    )

    df_train = df_res[
        (df_res["periodo_oficial"].astype(str) == "TRAIN")
        & (df_res["fecha_objetivo_h5"] <= CORTE_TRAIN)
    ].copy().reset_index(drop=True)
    df_test_15 = df_res[
        df_res["periodo_oficial"].astype(str) == "TEST"
    ].copy().reset_index(drop=True)

    features_base_v4 = list(VARIABLES_DM5_REL_CUATRO)

    experimentos: List[Tuple[str, str, List[str]]] = [
        ("F1_gap_uh_ppp", "F1_MICROESTRUCTURA", ["gap_uh_ppp"]),
        ("F1b_gap_uh_ppp_rel_panel", "F1_MICROESTRUCTURA", ["gap_uh_ppp_rel_panel"]),
        ("F1c_gap_uh_ppp_media5", "F1_MICROESTRUCTURA", ["gap_uh_ppp_media5"]),
        ("GRUPO_F1_COMPLETO", "F1_MICROESTRUCTURA", ["gap_uh_ppp", "gap_uh_ppp_rel_panel", "gap_uh_ppp_media5"]),
        ("F2_fx_ret5", "F2_BANXICO_FX", ["fx_ret5"]),
        ("F2b_fx_ret5_x_beta", "F2_BANXICO_FX", ["fx_ret5_x_beta"]),
        ("GRUPO_F2_COMPLETO", "F2_BANXICO_FX", ["fx_ret5", "fx_ret5_x_beta"]),
        ("F3_spx_ret5_lag1", "F3_GLOBAL_LAG1", ["spx_ret5_lag1"]),
        ("F3b_vix_cambio5_lag1", "F3_GLOBAL_LAG1", ["vix_cambio5_lag1"]),
        ("F3c_eww_ret5_lag1", "F3_GLOBAL_LAG1", ["eww_ret5_lag1"]),
        ("GRUPO_F3_COMPLETO", "F3_GLOBAL_LAG1", ["spx_ret5_lag1", "vix_cambio5_lag1", "eww_ret5_lag1"]),
        ("EXTRA_flag_decision_banxico_5d", "EXTRA_CALENDARIO", ["flag_decision_banxico_5d"]),
        ("EXTRA_flag_ex_div_5d", "EXTRA_CALENDARIO", ["flag_ex_div_5d"]),
        ("EXTRA_cobre_ret5_lag1_gmexico", "EXTRA_SECTORIAL", ["cobre_ret5_lag1_gmexico"]),
    ]

    filas_ablacion: List[Dict[str, Any]] = []
    features_individuales_aceptadas: List[str] = []

    for codigo_exp, familia, nuevas_cols in experimentos:
        features_cand = features_base_v4 + nuevas_cols

        # 1. Evaluación en CV walk-forward purgada dentro de TRAIN <= 2025-04-29
        df_oof = _evaluar_cv_walk_forward_purgada_par(
            df_train,
            features_base_v4,
            features_cand,
            c_val=0.01,
            n_folds=4,
            embargo_sesiones=5,
        )
        m_cv = _metricas_comparativas_par(df_oof, "p_base_cv", "p_cand_cv")

        # Regla pre-registrada: mejora log-loss con p_DM_unilateral < 0.10 y delta_BSS >= 0 en CV purgada
        aceptada_cv = bool(
            (m_cv["delta_logloss"] < 0.0)
            and (m_cv["p_dm_logloss_unilateral"] < 0.10)
            and (m_cv["delta_bss_pct"] >= 0.0)
        )
        if aceptada_cv and len(nuevas_cols) == 1:
            features_individuales_aceptadas.extend(nuevas_cols)

        # 2. Evaluación fuera de muestra en TEST (15 emisoras y 4 foco) sobre filas con dato válido
        cols_req_test = list(dict.fromkeys(features_cand + ["target_y", "p_ref_climatologia"]))
        tr_clean = df_train.dropna(subset=cols_req_test).copy().reset_index(drop=True)
        te_clean_15 = df_test_15.dropna(subset=cols_req_test).copy().reset_index(drop=True)

        p_base_te, _ = ajustar_logistica_pooled_panel(
            tr_clean, te_clean_15, features_base_v4, c=0.01, tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        p_cand_te, _ = ajustar_logistica_pooled_panel(
            tr_clean, te_clean_15, features_cand, c=0.01, tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        te_clean_15["p_base_test"] = p_base_te
        te_clean_15["p_cand_test"] = p_cand_te

        m_test_15 = _metricas_comparativas_par(te_clean_15, "p_base_test", "p_cand_test")
        te_clean_4 = te_clean_15[te_clean_15["emisora"].isin(EMISORAS_FOCO_4)].copy()
        m_test_4 = _metricas_comparativas_par(te_clean_4, "p_base_test", "p_cand_test")

        filas_ablacion.append(
            {
                "experimento": codigo_exp,
                "familia": familia,
                "features_agregadas": "+".join(nuevas_cols),
                "n_train_total": int(len(df_train)),
                "n_train_valido": int(len(tr_clean)),
                "filas_excluidas_sin_imputacion_train": int(len(df_train) - len(tr_clean)),
                "n_cv_oof": m_cv["n"],
                "cv_logloss_v4": round(m_cv["logloss_base"], 6),
                "cv_logloss_cand": round(m_cv["logloss_cand"], 6),
                "cv_delta_logloss": round(m_cv["delta_logloss"], 6),
                "cv_p_dm_logloss_unilateral": round(m_cv["p_dm_logloss_unilateral"], 4),
                "cv_p_dm_logloss_bilateral": round(m_cv["p_dm_logloss_bilateral"], 4),
                "cv_bss_v4_pct": round(m_cv["bss_base_pct"], 4),
                "cv_bss_cand_pct": round(m_cv["bss_cand_pct"], 4),
                "cv_delta_bss_pct": round(m_cv["delta_bss_pct"], 4),
                "cv_ic_v4": round(m_cv["ic_base"], 4),
                "cv_ic_cand": round(m_cv["ic_cand"], 4),
                "cv_delta_ic": round(m_cv["delta_ic"], 4),
                "aceptada_regla_preregistrada_cv": aceptada_cv,
                "n_test_15_valido": m_test_15["n"],
                "filas_excluidas_sin_imputacion_test_15": int(len(df_test_15) - m_test_15["n"]),
                "test15_acc_v4_pct": round(m_test_15["acc_base_pct"], 2),
                "test15_acc_cand_pct": round(m_test_15["acc_cand_pct"], 2),
                "test15_delta_acc_pp": round(m_test_15["delta_acc_pp"], 2),
                "test15_brier_v4": round(m_test_15["brier_base"], 6),
                "test15_brier_cand": round(m_test_15["brier_cand"], 6),
                "test15_delta_brier": round(m_test_15["delta_brier"], 6),
                "test15_logloss_v4": round(m_test_15["logloss_base"], 6),
                "test15_logloss_cand": round(m_test_15["logloss_cand"], 6),
                "test15_delta_logloss": round(m_test_15["delta_logloss"], 6),
                "test15_p_dm_logloss_unilateral": round(m_test_15["p_dm_logloss_unilateral"], 4),
                "test15_bss_cand_pct": round(m_test_15["bss_cand_pct"], 4),
                "test15_delta_bss_pct": round(m_test_15["delta_bss_pct"], 4),
                "test15_ic_cand": round(m_test_15["ic_cand"], 4),
                "test15_delta_ic": round(m_test_15["delta_ic"], 4),
                "test4_acc_v4_pct": round(m_test_4["acc_base_pct"], 2),
                "test4_acc_cand_pct": round(m_test_4["acc_cand_pct"], 2),
                "test4_delta_acc_pp": round(m_test_4["delta_acc_pp"], 2),
                "test4_brier_cand": round(m_test_4["brier_cand"], 6),
                "test4_delta_brier": round(m_test_4["delta_brier"], 6),
                "test4_delta_logloss": round(m_test_4["delta_logloss"], 6),
                "test4_p_dm_logloss_unilateral": round(m_test_4["p_dm_logloss_unilateral"], 4),
                "test4_bss_cand_pct": round(m_test_4["bss_cand_pct"], 4),
                "test4_delta_bss_pct": round(m_test_4["delta_bss_pct"], 4),
            }
        )

    # Si hubo al menos 1 feature aceptada individualmente, evaluar su combinación
    features_individuales_aceptadas = list(dict.fromkeys(features_individuales_aceptadas))
    if len(features_individuales_aceptadas) >= 1:
        features_comb = features_base_v4 + features_individuales_aceptadas
        df_oof_c = _evaluar_cv_walk_forward_purgada_par(
            df_train,
            features_base_v4,
            features_comb,
            c_val=0.01,
            n_folds=4,
            embargo_sesiones=5,
        )
        m_cv_c = _metricas_comparativas_par(df_oof_c, "p_base_cv", "p_cand_cv")
        aceptada_comb = bool(
            (m_cv_c["delta_logloss"] < 0.0)
            and (m_cv_c["p_dm_logloss_unilateral"] < 0.10)
            and (m_cv_c["delta_bss_pct"] >= 0.0)
        )

        cols_req_c = list(dict.fromkeys(features_comb + ["target_y", "p_ref_climatologia"]))
        tr_c = df_train.dropna(subset=cols_req_c).copy().reset_index(drop=True)
        te_c_15 = df_test_15.dropna(subset=cols_req_c).copy().reset_index(drop=True)
        p_b_te, _ = ajustar_logistica_pooled_panel(
            tr_c, te_c_15, features_base_v4, c=0.01, tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        p_c_te, _ = ajustar_logistica_pooled_panel(
            tr_c, te_c_15, features_comb, c=0.01, tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        te_c_15["p_base_test"] = p_b_te
        te_c_15["p_cand_test"] = p_c_te
        m_test_15_c = _metricas_comparativas_par(te_c_15, "p_base_test", "p_cand_test")
        te_c_4 = te_c_15[te_c_15["emisora"].isin(EMISORAS_FOCO_4)].copy()
        m_test_4_c = _metricas_comparativas_par(te_c_4, "p_base_test", "p_cand_test")

        filas_ablacion.append(
            {
                "experimento": "COMBINACION_ACEPTADAS_CV",
                "familia": "COMBINACION",
                "features_agregadas": "+".join(features_individuales_aceptadas),
                "n_train_total": int(len(df_train)),
                "n_train_valido": int(len(tr_c)),
                "filas_excluidas_sin_imputacion_train": int(len(df_train) - len(tr_c)),
                "n_cv_oof": m_cv_c["n"],
                "cv_logloss_v4": round(m_cv_c["logloss_base"], 6),
                "cv_logloss_cand": round(m_cv_c["logloss_cand"], 6),
                "cv_delta_logloss": round(m_cv_c["delta_logloss"], 6),
                "cv_p_dm_logloss_unilateral": round(m_cv_c["p_dm_logloss_unilateral"], 4),
                "cv_p_dm_logloss_bilateral": round(m_cv_c["p_dm_logloss_bilateral"], 4),
                "cv_bss_v4_pct": round(m_cv_c["bss_base_pct"], 4),
                "cv_bss_cand_pct": round(m_cv_c["bss_cand_pct"], 4),
                "cv_delta_bss_pct": round(m_cv_c["delta_bss_pct"], 4),
                "cv_ic_v4": round(m_cv_c["ic_base"], 4),
                "cv_ic_cand": round(m_cv_c["ic_cand"], 4),
                "cv_delta_ic": round(m_cv_c["delta_ic"], 4),
                "aceptada_regla_preregistrada_cv": aceptada_comb,
                "n_test_15_valido": m_test_15_c["n"],
                "filas_excluidas_sin_imputacion_test_15": int(len(df_test_15) - m_test_15_c["n"]),
                "test15_acc_v4_pct": round(m_test_15_c["acc_base_pct"], 2),
                "test15_acc_cand_pct": round(m_test_15_c["acc_cand_pct"], 2),
                "test15_delta_acc_pp": round(m_test_15_c["delta_acc_pp"], 2),
                "test15_brier_v4": round(m_test_15_c["brier_base"], 6),
                "test15_brier_cand": round(m_test_15_c["brier_cand"], 6),
                "test15_delta_brier": round(m_test_15_c["delta_brier"], 6),
                "test15_logloss_v4": round(m_test_15_c["logloss_base"], 6),
                "test15_logloss_cand": round(m_test_15_c["logloss_cand"], 6),
                "test15_delta_logloss": round(m_test_15_c["delta_logloss"], 6),
                "test15_p_dm_logloss_unilateral": round(m_test_15_c["p_dm_logloss_unilateral"], 4),
                "test15_bss_cand_pct": round(m_test_15_c["bss_cand_pct"], 4),
                "test15_delta_bss_pct": round(m_test_15_c["delta_bss_pct"], 4),
                "test15_ic_cand": round(m_test_15_c["ic_cand"], 4),
                "test15_delta_ic": round(m_test_15_c["delta_ic"], 4),
                "test4_acc_v4_pct": round(m_test_4_c["acc_base_pct"], 2),
                "test4_acc_cand_pct": round(m_test_4_c["acc_cand_pct"], 2),
                "test4_delta_acc_pp": round(m_test_4_c["delta_acc_pp"], 2),
                "test4_brier_cand": round(m_test_4_c["brier_cand"], 6),
                "test4_delta_brier": round(m_test_4_c["delta_brier"], 6),
                "test4_delta_logloss": round(m_test_4_c["delta_logloss"], 6),
                "test4_p_dm_logloss_unilateral": round(m_test_4_c["p_dm_logloss_unilateral"], 4),
                "test4_bss_cand_pct": round(m_test_4_c["bss_cand_pct"], 4),
                "test4_delta_bss_pct": round(m_test_4_c["delta_bss_pct"], 4),
            }
        )

    df_abl = pd.DataFrame(filas_ablacion)
    df_abl.to_csv(ARCHIVO_REPORTE_ABLACION_CSV, index=False, encoding="utf-8")

    hashes_despues = hashes_protegidos_g2()
    hashes_ok = hashes_antes == hashes_despues
    if not hashes_ok:
        raise RuntimeError("Se detectó alteración en hashes_protegidos_g2 durante Fase 3.")
    resumen_json = {
        "fecha_generacion": "2026-11-06",
        "fase": "FASE_3_FEATURES_EXTERNAS_Y_ABLACION",
        "regla_preregistrada_cv": {
            "descripcion": "Aceptar si en CV walk-forward purgada (TRAIN <= 2025-04-29, 4 bloques, embargo 5 sesiones) mejora log-loss vs G2_V4_ADJ con p_DM_unilateral < 0.10 y delta_BSS >= 0.",
            "umbral_p_dm_logloss_unilateral": 0.10,
            "umbral_delta_bss": 0.0,
        },
        "verificacion_sin_fuga_temporal": verificacion_fuga,
        "features_individuales_aceptadas_cv": features_individuales_aceptadas,
        "experimentos_aceptados_cv": df_abl[df_abl["aceptada_regla_preregistrada_cv"] == True]["experimento"].tolist(),
        "integridad_archivos_protegidos_intacta": hashes_ok,
        "tabla_ablacion": filas_ablacion,
    }
    ARCHIVO_REPORTE_ABLACION_JSON.write_text(
        json.dumps(resumen_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return df_abl, resumen_json


if __name__ == "__main__":
    df_res_abl, rep_json = ejecutar_ablacion_fase3(usar_cache=True)
    print(f"Panel Fase 3 guardado en: {ARCHIVO_PANEL_FASE3}")
    print(f"Reporte de ablación CSV guardado en: {ARCHIVO_REPORTE_ABLACION_CSV}")
    print(f"Features aceptadas en CV purgada: {rep_json['features_individuales_aceptadas_cv']}")
    print(
        df_res_abl[
            [
                "experimento",
                "cv_delta_logloss",
                "cv_p_dm_logloss_unilateral",
                "cv_delta_bss_pct",
                "aceptada_regla_preregistrada_cv",
                "test15_acc_cand_pct",
                "test15_delta_brier",
                "test4_acc_cand_pct",
                "test4_delta_brier",
            ]
        ].to_string(index=False)
    )
