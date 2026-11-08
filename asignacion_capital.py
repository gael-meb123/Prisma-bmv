"""
Fase 5: Política Institucional de Asignación de Capital y Backtest Neto de Costos (Prisma BMV).

Implementa la conversión de probabilidades direccionales a 5 sesiones en una cartera
operativa sobre las 5 emisoras principales (AMX, FEMSA, GFNORTE, GMEXICO, WALMEX):
  1. Encogimiento de probabilidad p_tilde = 0.5 + lambda * (p - 0.5) estimado solo con datos pasados.
  2. Banda muerta: si |p_tilde - 0.5| < 0.03 (o p_tilde <= 0.5), el peso es 0.
  3. Retorno esperado a 5 sesiones: mu_i = (2 * p_tilde_i - 1) * E_{250d}|r_{5,i}|.
  4. Matriz de covarianza Sigma con shrinkage analítico de Ledoit-Wolf a 250 sesiones purgadas.
  5. Fracción de Kelly 1/4: w = 0.25 * Sigma^{-1} mu, con clip a [0, 0.30], solo largo o en liquidez.
  6. Volatilidad objetivo máxima del 10% anual (escalamiento hacia abajo si la excede).
  7. Ejecución en 5 tramos traslapados (cada sesión rebalancea 1/5 del capital).
  8. Backtest en TEST neto de 20 pb ida y vuelta (10 pb por unidad de rotación |Delta w|),
     reportando Sharpe Ratio, Deflated Sharpe Ratio (DSR), Drawdown máximo, rotación y Hit Rate,
     comparado contra comprar y mantener el portafolio equiponderado de las 5 emisoras.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from evaluacion_institucional import _norm_cdf, _norm_ppf, curva_calibracion
from experimentos_entrenamiento_desarrollo import ajustar_logistica_pooled_panel
from features_externas import ARCHIVO_PANEL_FASE3, _preparar_vista_ajustada_fase3
from metodologia_ppp import CORTE_TRAIN, ROOT, timestamp_utc
from modelos_v6 import FEATURES_V4_BASE, FEATURES_V4_MAS_F1
from monitor_prospectivo_segunda_generacion import hashes_protegidos_g2


EMISORAS_PORTAFOLIO_5 = ["AMX", "FEMSA", "GFNORTE", "GMEXICO", "WALMEX"]

ARCHIVO_REPORTE_FASE5_JSON = ROOT / "reporte_fase5_portafolio.json"
ARCHIVO_CURVA_EQUITY_CSV = ROOT / "curva_equity_fase5_portafolio.csv"

# Constantes de la política institucional de Fase 5
LAMBDA_CV_TRAIN_FASE2 = 0.280333
BANDA_MUERTA_PROB = 0.03
FRACCION_KELLY = 0.25
PESO_MAX_EMISORA = 0.30
VOL_OBJETIVO_ANUAL = 0.10
TRAMOS_TRASLAPADOS = 5
COSTO_IDA_Y_VUELTA_BPS = 20.0
COSTO_POR_SENTIDO = (COSTO_IDA_Y_VUELTA_BPS / 2.0) / 10000.0  # 10 pb = 0.0010 por unidad de |Delta w|
EULER_MASCHERONI = 0.5772156649015329


def shrinkage_ledoit_wolf_cov(ret_matrix: np.ndarray, min_shrinkage: float = 0.05) -> Tuple[np.ndarray, float]:
    """
    Estimador analítico de Ledoit-Wolf (2004) hacia el objetivo isotrópico F = (tr(S)/K) * I_K.
    Recibe una matriz (T x K) de retornos de 5 sesiones sin valores faltantes.
    Devuelve (Sigma_LW, delta_shrinkage).
    """
    x = np.asarray(ret_matrix, dtype=float)
    t_obs, k_dim = x.shape
    if t_obs < 5:
        s_diag = np.full(k_dim, 0.001, dtype=float)
        return np.diag(s_diag), 1.0

    xc = x - np.mean(x, axis=0, keepdims=True)
    s_cov = (xc.T @ xc) / float(t_obs)
    mu_trace = float(np.trace(s_cov)) / float(k_dim)
    if mu_trace <= 1e-12:
        mu_trace = 1e-4
    f_target = mu_trace * np.eye(k_dim)

    d2 = float(np.sum((s_cov - f_target) ** 2)) / float(k_dim)
    if d2 <= 1e-18:
        return f_target, 1.0

    # Estimación de b^2 = (1 / (T^2 * K)) * sum_{t=1}^T ||x_t x_t' - S||_F^2
    b2_acc = 0.0
    for row in xc:
        outer = np.outer(row, row)
        b2_acc += float(np.sum((outer - s_cov) ** 2))
    b2 = min(d2, b2_acc / (float(t_obs * t_obs) * float(k_dim)))
    delta = float(np.clip(b2 / d2, min_shrinkage, 1.0))

    sigma_lw = (1.0 - delta) * s_cov + delta * f_target
    return sigma_lw, delta


def calcular_pesos_tramo_kelly(
    probs_raw: np.ndarray,
    lambda_cal: float,
    e_abs_r5: np.ndarray,
    sigma_lw_5d: np.ndarray,
    banda_muerta: float = BANDA_MUERTA_PROB,
    fraccion_kelly: float = FRACCION_KELLY,
    peso_max: float = PESO_MAX_EMISORA,
    vol_objetivo_anual: float = VOL_OBJETIVO_ANUAL,
) -> Dict[str, Any]:
    """
    Aplica los pasos 1 a 6 de la política de asignación de capital sobre las K emisoras
    en una sesión t dada:
      1. p_tilde = 0.5 + lambda_cal * (p - 0.5)
      2. Banda muerta: si |p_tilde - 0.5| < banda_muerta o p_tilde <= 0.5 => mu_i = 0
      3. mu_i = (2 * p_tilde_i - 1) * E|r_{5,i}|
      4. w_raw = fraccion_kelly * Sigma_LW^{-1} * mu
      5. Clip a [0, peso_max], forzando 0 en emisoras dentro de banda muerta, y suma <= 1.0
      6. Escalamiento por volatilidad objetivo anual (10%).
    """
    p = np.asarray(probs_raw, dtype=float)
    p_tilde = 0.5 + float(lambda_cal) * (p - 0.5)
    exceso_prob = p_tilde - 0.5

    # Solo operamos largo cuando p_tilde supera la banda muerta superior (p_tilde - 0.5 >= banda_muerta)
    activo_mask = np.isfinite(p_tilde) & (exceso_prob >= float(banda_muerta))
    mu_vec = np.where(activo_mask, (2.0 * p_tilde - 1.0) * np.asarray(e_abs_r5, dtype=float), 0.0)

    k_dim = len(p)
    if not np.any(activo_mask) or np.allclose(mu_vec, 0.0):
        return {
            "pesos": np.zeros(k_dim, dtype=float),
            "p_tilde": p_tilde,
            "mu_5d": mu_vec,
            "vol_ex_ante_anual": 0.0,
            "escalador_vol": 1.0,
            "efectivo": 1.0,
        }

    # Resolver sistema Sigma_LW^{-1} mu únicamente sobre el subconjunto de activos con señal activa
    idx_act = np.where(activo_mask)[0]
    sub_sigma = sigma_lw_5d[np.ix_(idx_act, idx_act)]
    sub_mu = mu_vec[idx_act]
    try:
        w_sub_raw = float(fraccion_kelly) * np.linalg.solve(sub_sigma, sub_mu)
    except np.linalg.LinAlgError:
        w_sub_raw = float(fraccion_kelly) * np.linalg.lstsq(sub_sigma, sub_mu, rcond=None)[0]

    w = np.zeros(k_dim, dtype=float)
    w[idx_act] = np.clip(w_sub_raw, 0.0, float(peso_max))

    suma_w = float(np.sum(w))
    if suma_w > 1.0:
        w = w / suma_w

    # Volatilidad anualizada implícita del tramo (Sigma_LW es covarianza de retornos a 5 sesiones)
    var_5d = float(w.T @ sigma_lw_5d @ w)
    vol_anual = math.sqrt(max(0.0, var_5d) * (252.0 / 5.0))
    escalador = 1.0
    if vol_anual > float(vol_objetivo_anual) and vol_anual > 1e-12:
        escalador = float(vol_objetivo_anual) / vol_anual
        w = w * escalador
        vol_anual = float(vol_objetivo_anual)

    return {
        "pesos": w,
        "p_tilde": p_tilde,
        "mu_5d": mu_vec,
        "vol_ex_ante_anual": vol_anual,
        "escalador_vol": escalador,
        "efectivo": float(max(0.0, 1.0 - float(np.sum(w)))),
    }


def deflated_sharpe_ratio(
    retornos_diarios: np.ndarray,
    num_variantes_probadas: int = 20,
) -> Dict[str, float]:
    """
    Calcula el Sharpe Ratio anualizado, el estadístico Probabilístico (PSR) y el
    Deflated Sharpe Ratio (DSR, Bailey & López de Prado, 2014) ajustado por asimetría,
    curtosis y el número total de variantes probadas en el proyecto (`num_variantes_probadas`).
    """
    r = np.asarray(retornos_diarios, dtype=float)
    n = len(r)
    if n < 10:
        return {"sharpe_anual": 0.0, "sharpe_diario": 0.0, "sr_umbral_diario": 0.0, "dsr_prob": 0.0}

    std_d = float(np.std(r, ddof=1))
    if std_d <= 1e-12:
        return {"sharpe_anual": 0.0, "sharpe_diario": 0.0, "sr_umbral_diario": 0.0, "dsr_prob": 0.0}

    mean_d = float(np.mean(r))
    sr_d = mean_d / std_d
    sr_anual = sr_d * math.sqrt(252.0)

    z = (r - mean_d) / std_d
    skew = float(np.mean(z**3))
    kurt = float(np.mean(z**4))  # Curtosis no centrada (3.0 para normal)

    # Varianza muestral de los estimadores de Sharpe diario bajo la nula
    var_sr_trials = 1.0 / float(max(1, n - 1))
    m = max(2, int(num_variantes_probadas))
    q1 = _norm_ppf(1.0 - 1.0 / float(m))
    q2 = _norm_ppf(1.0 - 1.0 / (float(m) * math.e))
    sr_0_d = math.sqrt(var_sr_trials) * ((1.0 - EULER_MASCHERONI) * q1 + EULER_MASCHERONI * q2)

    denom_sq = max(1e-8, 1.0 - skew * sr_d + ((kurt - 1.0) / 4.0) * (sr_d**2))
    stat_dsr = ((sr_d - sr_0_d) * math.sqrt(float(n - 1))) / math.sqrt(denom_sq)
    stat_psr0 = (sr_d * math.sqrt(float(n - 1))) / math.sqrt(denom_sq)

    return {
        "sharpe_anual": round(sr_anual, 4),
        "sharpe_diario": round(sr_d, 6),
        "sr_umbral_anual_max_trials": round(sr_0_d * math.sqrt(252.0), 4),
        "psr_vs_cero_prob": round(float(_norm_cdf(stat_psr0)), 4),
        "dsr_prob": round(float(_norm_cdf(stat_dsr)), 4),
        "asimetria": round(skew, 4),
        "curtosis": round(kurt, 4),
        "num_variantes_probadas": m,
    }


def _resumir_curva_portafolio(
    ret_bruto: np.ndarray,
    ret_neto: np.ndarray,
    turnover_diario: np.ndarray,
    exposicion_diaria: np.ndarray,
    num_variantes: int = 20,
) -> Dict[str, Any]:
    """Calcula métricas institucionales de portafolio sobre la serie diaria en TEST."""
    eq_bruto = np.cumprod(1.0 + ret_bruto)
    eq_neto = np.cumprod(1.0 + ret_neto)

    picos_neto = np.maximum.accumulate(np.concatenate([[1.0], eq_neto]))[1:]
    dd_neto = eq_neto / picos_neto - 1.0
    max_dd_neto = float(np.min(dd_neto))

    n_ses = len(ret_neto)
    ret_acum_bruto = float(eq_bruto[-1] - 1.0)
    ret_acum_neto = float(eq_neto[-1] - 1.0)
    cagr_neto = float(eq_neto[-1] ** (252.0 / float(max(1, n_ses))) - 1.0)
    vol_anual_neto = float(np.std(ret_neto, ddof=1) * math.sqrt(252.0))

    dias_activos = exposicion_diaria > 1e-6
    n_activos = int(np.sum(dias_activos))
    hit_rate_dias_activos = (
        float(np.mean(ret_neto[dias_activos] > 0.0) * 100.0) if n_activos > 0 else 0.0
    )

    dsr_bruto = deflated_sharpe_ratio(ret_bruto, num_variantes_probadas=num_variantes)
    dsr_neto = deflated_sharpe_ratio(ret_neto, num_variantes_probadas=num_variantes)

    return {
        "sesiones_test": n_ses,
        "sesiones_con_exposicion_activa": n_activos,
        "pct_tiempo_en_mercado": round(100.0 * n_activos / float(max(1, n_ses)), 2),
        "exposicion_media_pct": round(100.0 * float(np.mean(exposicion_diaria)), 2),
        "retorno_acumulado_bruto_pct": round(100.0 * ret_acum_bruto, 2),
        "retorno_acumulado_neto_20bps_pct": round(100.0 * ret_acum_neto, 2),
        "retorno_anualizado_neto_pct": round(100.0 * cagr_neto, 2),
        "volatilidad_anualizada_pct": round(100.0 * vol_anual_neto, 2),
        "sharpe_bruto": dsr_bruto["sharpe_anual"],
        "sharpe_neto_20bps": dsr_neto["sharpe_anual"],
        "psr_neto_vs_cero": dsr_neto["psr_vs_cero_prob"],
        "deflated_sharpe_ratio_neto": dsr_neto["dsr_prob"],
        "max_drawdown_neto_pct": round(100.0 * max_dd_neto, 2),
        "rotacion_media_diaria_pct": round(100.0 * float(np.mean(turnover_diario)), 2),
        "rotacion_anualizada_veces": round(float(np.mean(turnover_diario)) * 252.0 / 2.0, 2),
        "costo_total_pagado_pct": round(100.0 * float(np.sum(turnover_diario) * COSTO_POR_SENTIDO), 2),
        "hit_rate_sesiones_activas_pct": round(hit_rate_dias_activos, 2),
        "detalle_dsr_neto": dsr_neto,
    }


def ejecutar_backtest_fase5(
    ruta_panel_fase3: Path = ARCHIVO_PANEL_FASE3,
    ruta_reporte_json: Path = ARCHIVO_REPORTE_FASE5_JSON,
    ruta_curva_csv: Path = ARCHIVO_CURVA_EQUITY_CSV,
) -> Dict[str, Any]:
    """
    Ejecuta el backtest institucional en TEST (2025-04-30 a 2026-10-27) sobre las 5 emisoras
    del portafolio (AMX, FEMSA, GFNORTE, GMEXICO, WALMEX) con tramos traslapados (1/5 diario)
    y costos de 20 pb ida y vuelta.
    """
    hashes_antes = hashes_protegidos_g2()
    df_raw = pd.read_csv(ruta_panel_fase3)
    df_vista = _preparar_vista_ajustada_fase3(df_raw)

    df_res = df_vista[
        df_vista["target_disponible"].astype(str).isin(["True", "true", "1"])
        & df_vista["target_y"].notna()
        & df_vista["ret_10"].notna()
    ].copy().reset_index(drop=True)
    df_res["target_y"] = df_res["target_y"].astype(int)
    df_res["ret_h5"] = df_res["ppp_t5"] / df_res["ppp_t"] - 1.0
    df_res["abs_ret_h5"] = np.abs(df_res["ret_h5"])

    tr = df_res[
        (df_res["periodo_oficial"].astype(str) == "TRAIN")
        & (df_res["fecha_objetivo_h5"] <= CORTE_TRAIN)
    ].copy().reset_index(drop=True)
    te = df_res[
        df_res["periodo_oficial"].astype(str) == "TEST"
    ].copy().reset_index(drop=True)

    # Probabilidades en TRAIN y TEST para G2_V4_ADJ y G2_V4_F1_GAP
    p_v4_tr, _ = ajustar_logistica_pooled_panel(tr, tr, FEATURES_V4_BASE, c=0.01)
    p_v4_te, _ = ajustar_logistica_pooled_panel(tr, te, FEATURES_V4_BASE, c=0.01)
    p_f1_tr, _ = ajustar_logistica_pooled_panel(tr, tr, FEATURES_V4_MAS_F1, c=0.01)
    p_f1_te, _ = ajustar_logistica_pooled_panel(tr, te, FEATURES_V4_MAS_F1, c=0.01)

    tr["prob_v4_adj"] = p_v4_tr
    te["prob_v4_adj"] = p_v4_te
    tr["prob_v4_f1"] = p_f1_tr
    te["prob_v4_f1"] = p_f1_te

    df_all = pd.concat([tr, te], ignore_index=True).sort_values(["posicion_sesion", "emisora"]).reset_index(drop=True)
    df_5 = df_all[df_all["emisora"].isin(EMISORAS_PORTAFOLIO_5)].copy()

    # Tablas pivote por posicion_sesion para las 5 emisoras foco
    fechas_test = sorted(te["fecha"].unique().tolist())
    sesiones_test_df = (
        te[["posicion_sesion", "fecha", "fecha_objetivo_h5"]]
        .drop_duplicates(subset=["posicion_sesion"])
        .sort_values("posicion_sesion")
        .reset_index(drop=True)
    )
    n_test_ses = len(sesiones_test_df)
    k_em = len(EMISORAS_PORTAFOLIO_5)

    # Retorno de 1 sesión siguiente r_{1, i, t+1} para valuar día a día el portafolio
    piv_ret1 = df_5.pivot(index="posicion_sesion", columns="emisora", values="ret_1")[EMISORAS_PORTAFOLIO_5]
    piv_ret1_next = piv_ret1.shift(-1).fillna(0.0)

    piv_ret5 = df_5.pivot(index="posicion_sesion", columns="emisora", values="ret_h5")[EMISORAS_PORTAFOLIO_5]
    piv_abs_ret5 = np.abs(piv_ret5)
    piv_fecha = df_5.groupby("posicion_sesion")["fecha"].first()
    piv_fecha_obj = df_5.groupby("posicion_sesion")["fecha_objetivo_h5"].first()

    piv_p_v4 = df_5.pivot(index="posicion_sesion", columns="emisora", values="prob_v4_adj")[EMISORAS_PORTAFOLIO_5]
    piv_p_f1 = df_5.pivot(index="posicion_sesion", columns="emisora", values="prob_v4_f1")[EMISORAS_PORTAFOLIO_5]

    # Función auxiliar para simular una estrategia sobre todas las sesiones de TEST
    def _simular_estrategia(
        piv_probs: pd.DataFrame,
        col_prob_panel: str,
        modo_lambda: str,
        banda_muerta_efectiva: float,
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        cola_tramos: List[np.ndarray] = [np.zeros(k_em, dtype=float) for _ in range(TRAMOS_TRASLAPADOS)]
        w_port_prev = np.zeros(k_em, dtype=float)

        ret_bruto_arr = np.zeros(n_test_ses, dtype=float)
        ret_neto_arr = np.zeros(n_test_ses, dtype=float)
        turnover_arr = np.zeros(n_test_ses, dtype=float)
        exposicion_arr = np.zeros(n_test_ses, dtype=float)
        shrinkage_arr = np.zeros(n_test_ses, dtype=float)
        lambda_arr = np.zeros(n_test_ses, dtype=float)
        pesos_hist: List[np.ndarray] = []

        # Operaciones individuales a 5 días (tramos con peso > 0) para medir hit rate por operación
        aciertos_tramo_5d = 0
        total_tramos_5d = 0
        ret_tramos_5d: List[float] = []

        for idx_t, row_ses in sesiones_test_df.iterrows():
            pos_t = int(row_ses["posicion_sesion"])
            fecha_t = str(row_ses["fecha"])

            # Ventana histórica estrictamente purgada: fecha_objetivo_h5 <= fecha_t y fecha < fecha_t
            mask_purgada = (piv_fecha < fecha_t) & (piv_fecha_obj <= fecha_t)
            pos_purgadas = piv_ret5.index[mask_purgada].tolist()[-250:]

            ret5_hist = piv_ret5.loc[pos_purgadas].dropna(how="any").to_numpy(dtype=float)
            sigma_lw, delta_lw = shrinkage_ledoit_wolf_cov(ret5_hist)
            shrinkage_arr[idx_t] = delta_lw

            e_abs_r5 = piv_abs_ret5.loc[pos_purgadas].mean(axis=0).fillna(0.027).to_numpy(dtype=float)

            if modo_lambda == "RODANTE_250D_PURGADA":
                sub_cal = df_5[(df_5["fecha"] < fecha_t) & (df_5["fecha_objetivo_h5"] <= fecha_t)].tail(250 * k_em)
                lam_raw = float(
                    curva_calibracion(
                        sub_cal[col_prob_panel].to_numpy(dtype=float),
                        sub_cal["target_y"].to_numpy(dtype=int),
                        bins=10,
                    )["lambda_calibracion"]
                )
                # Acotar en [LAMBDA_CV_TRAIN_FASE2, 1.0] para nunca sobre-extender probabilidades (lambda <= 1.0)
                lam_t = float(np.clip(lam_raw if np.isfinite(lam_raw) else LAMBDA_CV_TRAIN_FASE2, LAMBDA_CV_TRAIN_FASE2, 1.0))
            else:
                lam_t = LAMBDA_CV_TRAIN_FASE2
            lambda_arr[idx_t] = lam_t

            probs_hoy = piv_probs.loc[pos_t].fillna(0.5).to_numpy(dtype=float)
            res_kelly = calcular_pesos_tramo_kelly(
                probs_raw=probs_hoy,
                lambda_cal=lam_t,
                e_abs_r5=e_abs_r5,
                sigma_lw_5d=sigma_lw,
                banda_muerta=banda_muerta_efectiva,
                fraccion_kelly=FRACCION_KELLY,
                peso_max=PESO_MAX_EMISORA,
                vol_objetivo_anual=VOL_OBJETIVO_ANUAL,
            )
            w_tramo_hoy = res_kelly["pesos"]

            # Contabilizar operaciones a 5 días generadas por el tramo hoy
            r5_hoy = piv_ret5.loc[pos_t].to_numpy(dtype=float)
            for j_em in range(k_em):
                if w_tramo_hoy[j_em] > 1e-6 and np.isfinite(r5_hoy[j_em]):
                    total_tramos_5d += 1
                    ret_tramos_5d.append(float(r5_hoy[j_em]))
                    if r5_hoy[j_em] > 0.0:
                        aciertos_tramo_5d += 1

            # Actualizar los 5 tramos traslapados (sale el tramo t-5, entra el tramo t)
            cola_tramos.pop(0)
            cola_tramos.append(w_tramo_hoy)
            w_port_hoy = np.mean(np.vstack(cola_tramos), axis=0)
            pesos_hist.append(w_port_hoy.copy())

            turnover_hoy = float(np.sum(np.abs(w_port_hoy - w_port_prev)))
            r1_sig = piv_ret1_next.loc[pos_t].to_numpy(dtype=float)
            r_bruto = float(np.dot(w_port_hoy, r1_sig))
            r_neto = r_bruto - turnover_hoy * COSTO_POR_SENTIDO

            ret_bruto_arr[idx_t] = r_bruto
            ret_neto_arr[idx_t] = r_neto
            turnover_arr[idx_t] = turnover_hoy
            exposicion_arr[idx_t] = float(np.sum(w_port_hoy))
            w_port_prev = w_port_hoy

        resumen = _resumir_curva_portafolio(
            ret_bruto_arr, ret_neto_arr, turnover_arr, exposicion_arr, num_variantes=20
        )
        resumen["operaciones_tramo_5d_totales"] = total_tramos_5d
        resumen["hit_rate_operaciones_5d_pct"] = (
            round(100.0 * aciertos_tramo_5d / float(total_tramos_5d), 2) if total_tramos_5d > 0 else 0.0
        )
        resumen["retorno_medio_por_operacion_5d_bps"] = (
            round(10000.0 * float(np.mean(ret_tramos_5d)), 2) if ret_tramos_5d else 0.0
        )
        resumen["shrinkage_ledoit_wolf_medio"] = round(float(np.mean(shrinkage_arr)), 4)
        resumen["lambda_calibracion_media_aplicada"] = round(float(np.mean(lambda_arr)), 4)

        pesos_mat = np.vstack(pesos_hist)
        resumen["peso_medio_por_emisora_pct"] = {
            em: round(100.0 * float(np.mean(pesos_mat[:, i])), 2)
            for i, em in enumerate(EMISORAS_PORTAFOLIO_5)
        }

        df_curva = pd.DataFrame(
            {
                "fecha": sesiones_test_df["fecha"],
                "ret_bruto": ret_bruto_arr,
                "ret_neto": ret_neto_arr,
                "equity_neto": np.cumprod(1.0 + ret_neto_arr),
                "exposicion": exposicion_arr,
                "turnover": turnover_arr,
            }
        )
        for i, em in enumerate(EMISORAS_PORTAFOLIO_5):
            df_curva[f"w_{em}"] = pesos_mat[:, i]

        return resumen, df_curva

    # 1. Portafolio principal: G2_V4_F1_GAP con recalibración rodante purgada 250d y banda muerta 0.03
    res_f1_250d, curva_f1 = _simular_estrategia(
        piv_p_f1, "prob_v4_f1", modo_lambda="RODANTE_250D_PURGADA", banda_muerta_efectiva=BANDA_MUERTA_PROB
    )
    # 2. Portafolio Campeón Base: G2_V4_ADJ con recalibración rodante purgada 250d y banda muerta 0.03
    res_v4_250d, curva_v4 = _simular_estrategia(
        piv_p_v4, "prob_v4_adj", modo_lambda="RODANTE_250D_PURGADA", banda_muerta_efectiva=BANDA_MUERTA_PROB
    )
    # 3. Variante ultra-conservadora con lambda fija de Fase 2 (0.280333) y banda muerta proporcional (0.03 * lambda_0)
    res_f1_lam_fija, curva_f1_fija = _simular_estrategia(
        piv_p_f1,
        "prob_v4_f1",
        modo_lambda="FIJA_CV_TRAIN",
        banda_muerta_efectiva=BANDA_MUERTA_PROB * LAMBDA_CV_TRAIN_FASE2,
    )
    # 4. Variante con lambda fija de Fase 2 (0.280333) y banda muerta nominal 0.03 sobre p_tilde (doble encogimiento)
    res_f1_doble_encogimiento, _ = _simular_estrategia(
        piv_p_f1,
        "prob_v4_f1",
        modo_lambda="FIJA_CV_TRAIN",
        banda_muerta_efectiva=BANDA_MUERTA_PROB,
    )

    # 5. Benchmark pasivo: Comprar y mantener (equiponderado de las 5 emisoras, 20% cada una)
    w_bh = np.full(k_em, 1.0 / float(k_em), dtype=float)
    r_bh_bruto = np.zeros(n_test_ses, dtype=float)
    turnover_bh = np.zeros(n_test_ses, dtype=float)
    turnover_bh[0] = 1.0  # Costo inicial de entrada (10 pb) y salida al final (10 pb) = 20 pb ida y vuelta
    turnover_bh[-1] = 1.0
    for idx_t, row_ses in sesiones_test_df.iterrows():
        pos_t = int(row_ses["posicion_sesion"])
        r1_sig = piv_ret1_next.loc[pos_t].to_numpy(dtype=float)
        r_bh_bruto[idx_t] = float(np.dot(w_bh, r1_sig))
    r_bh_neto = r_bh_bruto - turnover_bh * COSTO_POR_SENTIDO
    res_benchmark = _resumir_curva_portafolio(
        r_bh_bruto, r_bh_neto, turnover_bh, np.ones(n_test_ses, dtype=float), num_variantes=1
    )

    # Guardar CSV maestro con las curvas de equity
    df_csv = pd.DataFrame(
        {
            "fecha": curva_f1["fecha"],
            "equity_neto_g2_v4_f1_gap": np.round(curva_f1["equity_neto"], 6),
            "ret_neto_g2_v4_f1_gap": np.round(curva_f1["ret_neto"], 6),
            "exposicion_g2_v4_f1_gap": np.round(curva_f1["exposicion"], 4),
            "equity_neto_g2_v4_adj": np.round(curva_v4["equity_neto"], 6),
            "ret_neto_g2_v4_adj": np.round(curva_v4["ret_neto"], 6),
            "exposicion_g2_v4_adj": np.round(curva_v4["exposicion"], 4),
            "equity_neto_g2_v4_f1_lambda_fija": np.round(curva_f1_fija["equity_neto"], 6),
            "equity_neto_benchmark_equiponderado_5": np.round(np.cumprod(1.0 + r_bh_neto), 6),
            "ret_neto_benchmark_equiponderado_5": np.round(r_bh_neto, 6),
        }
    )
    for em in EMISORAS_PORTAFOLIO_5:
        df_csv[f"w_v4_f1_{em}"] = np.round(curva_f1[f"w_{em}"], 4)
    df_csv.to_csv(ruta_curva_csv, index=False, encoding="utf-8")

    hashes_despues = hashes_protegidos_g2()
    if hashes_antes != hashes_despues:
        raise RuntimeError("Se detectó alteración en archivos protegidos durante la Fase 5.")

    reporte = {
        "fase": "FASE_5_POLITICA_ASIGNACION_CAPITAL_Y_PORTAFOLIO",
        "timestamp_utc": timestamp_utc(),
        "parametros_politica": {
            "emisoras_portafolio": EMISORAS_PORTAFOLIO_5,
            "lambda_cv_train_fase2": LAMBDA_CV_TRAIN_FASE2,
            "banda_muerta_prob": BANDA_MUERTA_PROB,
            "fraccion_kelly": FRACCION_KELLY,
            "peso_max_emisora": PESO_MAX_EMISORA,
            "volatilidad_objetivo_anual": VOL_OBJETIVO_ANUAL,
            "tramos_traslapados": TRAMOS_TRASLAPADOS,
            "costo_ida_y_vuelta_bps": COSTO_IDA_Y_VUELTA_BPS,
            "punto_equilibrio_probabilidad_estimado_pct": 53.70,
        },
        "estrategias": {
            "G2_V4_F1_GAP_KELLY_250D": res_f1_250d,
            "G2_V4_ADJ_KELLY_250D": res_v4_250d,
            "G2_V4_F1_GAP_LAMBDA_FIJA_CONSERVADORA": res_f1_lam_fija,
            "G2_V4_F1_GAP_LAMBDA_FIJA_BANDA_ESTRICTA": res_f1_doble_encogimiento,
            "BENCHMARK_EQUIPONDERADO_5_EMISORAS": res_benchmark,
        },
        "archivo_curva_equity_csv": str(ruta_curva_csv.name),
        "integridad_archivos_protegidos_intacta": True,
    }
    ruta_reporte_json.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")
    return reporte


if __name__ == "__main__":
    rep = ejecutar_backtest_fase5()
    print(f"Reporte Fase 5 guardado en: {ARCHIVO_REPORTE_FASE5_JSON}")
    print(f"Curva de equity CSV guardada en: {ARCHIVO_CURVA_EQUITY_CSV}")
    for nombre, d in rep["estrategias"].items():
        print(
            f"{nombre:38s} | RetNeto={d['retorno_acumulado_neto_20bps_pct']:+6.2f}% "
            f"(CAGR={d['retorno_anualizado_neto_pct']:+5.2f}%) | Vol={d['volatilidad_anualizada_pct']:5.2f}% "
            f"| SharpeNeto={d['sharpe_neto_20bps']:+5.2f} (Bruto={d['sharpe_bruto']:+5.2f}, DSR={d['deflated_sharpe_ratio_neto']:.3f}) "
            f"| MaxDD={d['max_drawdown_neto_pct']:6.2f}% | ExpMedia={d['exposicion_media_pct']:5.2f}% "
            f"| Hit5d={d.get('hit_rate_operaciones_5d_pct', 0.0):5.2f}%"
        )
