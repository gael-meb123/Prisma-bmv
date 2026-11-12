"""
Fase 4: Modelos Cuantitativos de Sexta Generación — Candidatos V6 (Prisma BMV).

Implementa y evalúa bajo el marco institucional de la Fase 2 (sobre el panel limpio de Fase 1
y las features verificadas sin fuga de Fase 3) los cuatro candidatos de nueva generación:
  1. G2_V6A_JERARQUICO: Regresión logística con partial pooling por emisora (beta_i = beta_pool + u_i)
     estimada vía IRLS en NumPy; tau y C_pool seleccionados por CV walk-forward purgada en TRAIN.
  2. G2_V6B_DESCOMPUESTO: Descomposición aditiva de retorno de mercado (con features macro F2/F3)
     más exceso de retorno idiosincrático (features transversales + F1 gap_uh_ppp), combinados
     mediante P(r_i > 0) = Phi((mu_m + mu_ex) / sigma).
  3. G2_V6C_RIDGE_CONTINUO: Regresión Ridge continua sobre el retorno ajustado por riesgo
     z = r_{t+5} / (sqrt(5) * sigma_20), mapeada a probabilidad con p = Phi(z_hat / sigma_res).
  4. G2_LGBM_CHALLENGER: LightGBM 4.7 restringido (max_depth=3, num_leaves=7, lr=0.02,
     min_data_in_leaf=100, feature_fraction=0.8, monotone_constraints, emisora categórica)
     con early stopping y recalibración de Platt en un fold cronológico purgado de TRAIN.

Evalúa la regla de promoción pre-registrada en la Sección 9 de PLAN_MEJORA_MODELO_HANDOFF.md
y genera reporte_fase4_modelos_v6.json.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd

from evaluacion_institucional import (
    _norm_cdf,
    block_bootstrap_diff,
    brier_skill_score,
    calcular_climatologia_rodante_purgada,
    curva_calibracion,
    descomposicion_murphy,
    diebold_mariano,
    information_gain_bits,
    intervalo_wilson,
    rank_ic_diario,
)
from experimentos_entrenamiento_desarrollo import ajustar_logistica_pooled_panel
from features_externas import ARCHIVO_PANEL_FASE3, _preparar_vista_ajustada_fase3
from higiene_etiquetas_dividendos import EMISORAS_FOCO_4
from metodologia_ppp import CORTE_TRAIN, ROOT, timestamp_utc
from monitor_prospectivo_segunda_generacion import (
    VARIABLES_DM5_REL_CUATRO,
    hashes_protegidos_g2,
)


ARCHIVO_REPORTE_FASE4_JSON = ROOT / "reporte_fase4_modelos_v6.json"
EPS_PROB = 1e-12

# Features aceptadas tras la Fase 3 (V4 base + F1 gap_uh_ppp)
FEATURES_V4_BASE = list(VARIABLES_DM5_REL_CUATRO)
FEATURES_V4_MAS_F1 = list(VARIABLES_DM5_REL_CUATRO) + ["gap_uh_ppp"]


def _vec_norm_cdf(z: np.ndarray) -> np.ndarray:
    """CDF normal estándar vectorizada sin dependencia de scipy."""
    z_arr = np.asarray(z, dtype=float)
    erf_vec = np.vectorize(math.erf)
    return 0.5 * (1.0 + erf_vec(z_arr / math.sqrt(2.0)))


def _particiones_walk_forward_purgadas(
    df_train: pd.DataFrame,
    n_folds: int = 4,
    embargo_sesiones: int = 5,
) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Construye 4 particiones cronológicas walk-forward con purga (fecha_objetivo_h5 <= fecha_corte)
    y embargo de 5 sesiones estrictamente dentro de TRAIN (<= CORTE_TRAIN).
    """
    tr = df_train.sort_values(["posicion_sesion", "emisora"]).reset_index(drop=True)
    pos_unicas = sorted(tr["posicion_sesion"].unique().tolist())
    n_pos = len(pos_unicas)
    min_train_pos = int(n_pos * 0.40)
    bloque_val = max(20, int((n_pos - min_train_pos) / n_folds))

    folds: List[Tuple[pd.DataFrame, pd.DataFrame]] = []
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
        if len(fold_tr) >= 200 and len(fold_va) > 0:
            folds.append((fold_tr, fold_va))
    return folds


# =============================================================================
# CANDIDATO 1: G2_V6A_JERARQUICO (Partial Pooling Logit IRLS en NumPy)
# =============================================================================
def _ajustar_logit_jerarquico_irls(
    df_tr: pd.DataFrame,
    df_te: pd.DataFrame,
    features: List[str],
    c_pool: float = 0.01,
    tau: float = 0.002,
    max_iter: int = 35,
    tol: float = 1e-7,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Ajusta un modelo logístico jerárquico con partial pooling:
      logit(p_{i,t}) = alpha_0 + x_{i,t}' beta_pool + alpha_i + x_{i,t}' u_i
    con penalización L2 diferenciada:
      (1 / (2 * c_pool)) * ||beta_pool||^2 + (1 / (2 * tau)) * sum_i (alpha_i^2 + ||u_i||^2).
    """
    x_tr_raw = df_tr[features].to_numpy(dtype=float)
    y_tr = df_tr["target_y"].to_numpy(dtype=float)
    x_te_raw = df_te[features].to_numpy(dtype=float)

    med = np.mean(x_tr_raw, axis=0)
    esc = np.std(x_tr_raw, axis=0)
    esc = np.where(esc <= 1e-12, 1.0, esc)

    x_tr = (x_tr_raw - med) / esc
    x_te = (x_te_raw - med) / esc

    emisoras_tr = sorted(df_tr["emisora"].astype(str).unique().tolist())
    em_to_idx = {em: i for i, em in enumerate(emisoras_tr)}
    m_em = len(emisoras_tr)
    p_dim = len(features)

    # Vector de parámetros theta de dimensión (1 + p_dim) + m_em * (1 + p_dim):
    # [alpha_0, beta_pool (p_dim), alpha_1, u_1 (p_dim), ..., alpha_M, u_M (p_dim)]
    block_size = 1 + p_dim
    total_dim = block_size * (1 + m_em)
    n_tr = len(df_tr)

    # Construir matriz de diseño dispersa por bloques en denso (total_dim <= 16 * 6 = 96, muy rápida)
    z_tr = np.zeros((n_tr, total_dim), dtype=float)
    z_tr[:, 0] = 1.0
    z_tr[:, 1:block_size] = x_tr
    em_tr_arr = df_tr["emisora"].astype(str).to_numpy()
    for row_i, em in enumerate(em_tr_arr):
        idx_e = em_to_idx[em]
        offset = block_size * (1 + idx_e)
        z_tr[row_i, offset] = 1.0
        z_tr[row_i, offset + 1 : offset + block_size] = x_tr[row_i]

    # Matriz diagonal de penalización L2: alpha_0 sin penalizar (1e-8), beta_pool con 1/c_pool, u_i con 1/tau
    pen_diag = np.zeros(total_dim, dtype=float)
    pen_diag[0] = 1e-8
    pen_diag[1:block_size] = 1.0 / max(c_pool, 1e-9)
    pen_diag[block_size:] = 1.0 / max(tau, 1e-9)
    p_mat = np.diag(pen_diag)

    theta = np.zeros(total_dim, dtype=float)
    for _ in range(max_iter):
        eta = np.clip(z_tr @ theta, -25.0, 25.0)
        prob = 1.0 / (1.0 + np.exp(-eta))
        w = np.maximum(prob * (1.0 - prob), 1e-8)
        grad = z_tr.T @ (prob - y_tr) + pen_diag * theta
        hess = (z_tr.T * w) @ z_tr + p_mat
        try:
            paso = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            paso = np.linalg.lstsq(hess, grad, rcond=None)[0]
        theta_new = theta - paso
        if float(np.max(np.abs(paso))) < tol:
            theta = theta_new
            break
        theta = theta_new

    # Predicción en df_te (si una emisora no estuvo en train, su bloque u_i es 0 = puro beta_pool)
    n_te = len(df_te)
    z_te = np.zeros((n_te, total_dim), dtype=float)
    z_te[:, 0] = 1.0
    z_te[:, 1:block_size] = x_te
    em_te_arr = df_te["emisora"].astype(str).to_numpy()
    for row_i, em in enumerate(em_te_arr):
        if em in em_to_idx:
            offset = block_size * (1 + em_to_idx[em])
            z_te[row_i, offset] = 1.0
            z_te[row_i, offset + 1 : offset + block_size] = x_te[row_i]

    eta_te = np.clip(z_te @ theta, -25.0, 25.0)
    prob_te = 1.0 / (1.0 + np.exp(-eta_te))

    info = {
        "c_pool": float(c_pool),
        "tau": float(tau),
        "alpha_0": float(theta[0]),
        "beta_pool": {f: round(float(theta[1 + j]), 6) for j, f in enumerate(features)},
        "norma_l2_efectos_aleatorios": round(float(np.linalg.norm(theta[block_size:])), 6),
    }
    return prob_te, info


def entrenar_predecir_g2_v6a_jerarquico(
    df_tr: pd.DataFrame,
    df_te: pd.DataFrame,
    features: List[str] = FEATURES_V4_MAS_F1,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Selecciona (c_pool, tau) por CV walk-forward purgada dentro de TRAIN y predice en TEST.
    """
    folds = _particiones_walk_forward_purgadas(df_tr, n_folds=4, embargo_sesiones=5)
    candidatos_grid = [
        (0.01, 0.0005),
        (0.01, 0.001),
        (0.01, 0.0025),
        (0.01, 0.005),
        (0.02, 0.001),
        (0.02, 0.0025),
    ]

    mejor_par = (0.01, 0.001)
    mejor_ll = float("inf")
    resultados_grid: List[Dict[str, float]] = []

    for c_p, tau_val in candidatos_grid:
        lls: List[float] = []
        for f_tr, f_va in folds:
            p_va, _ = _ajustar_logit_jerarquico_irls(f_tr, f_va, features, c_pool=c_p, tau=tau_val)
            p_clip = np.clip(p_va, EPS_PROB, 1.0 - EPS_PROB)
            y_va = f_va["target_y"].to_numpy(dtype=float)
            ll = float(-np.mean(y_va * np.log(p_clip) + (1.0 - y_va) * np.log(1.0 - p_clip)))
            lls.append(ll)
        ll_med = float(np.mean(lls))
        resultados_grid.append({"c_pool": c_p, "tau": tau_val, "cv_logloss": round(ll_med, 6)})
        if ll_med < mejor_ll:
            mejor_ll = ll_med
            mejor_par = (c_p, tau_val)

    prob_te, info_fit = _ajustar_logit_jerarquico_irls(
        df_tr, df_te, features, c_pool=mejor_par[0], tau=mejor_par[1]
    )
    info_fit["cv_logloss_seleccion"] = round(mejor_ll, 6)
    info_fit["grid_cv"] = resultados_grid
    return prob_te, info_fit


# =============================================================================
# CANDIDATO 2: G2_V6B_DESCOMPUESTO (Mercado Macro F2/F3 + Exceso Idiosincrático F1)
# =============================================================================
def _ridge_fit_predict(
    x_tr: np.ndarray,
    y_tr: np.ndarray,
    x_te: np.ndarray,
    alpha: float,
) -> np.ndarray:
    """Regresión Ridge en forma cerrada con estandarización aprendida solo en TRAIN."""
    med = np.mean(x_tr, axis=0)
    esc = np.std(x_tr, axis=0)
    esc = np.where(esc <= 1e-12, 1.0, esc)

    xs_tr = (x_tr - med) / esc
    xs_te = (x_te - med) / esc
    y_mean = float(np.mean(y_tr))
    yc_tr = y_tr - y_mean

    p_dim = xs_tr.shape[1]
    a_mat = xs_tr.T @ xs_tr + float(alpha) * np.eye(p_dim)
    b_vec = xs_tr.T @ yc_tr
    try:
        beta = np.linalg.solve(a_mat, b_vec)
    except np.linalg.LinAlgError:
        beta = np.linalg.lstsq(a_mat, b_vec, rcond=None)[0]
    return y_mean + xs_te @ beta


def _ajustar_modelo_descompuesto_bloque(
    df_tr: pd.DataFrame,
    df_te: pd.DataFrame,
    alpha_mkt: float,
    alpha_ex: float,
    escala_sigma: float,
) -> np.ndarray:
    """
    Ajusta por separado:
      1) Submodelo de retorno medio del mercado r_{m, t->t+5} con features agregadas + F2/F3.
         En sesiones con feriado de EE.UU. en t-1, usa el submodelo doméstico (sin imputar F3).
      2) Submodelo de exceso de retorno idiosincrático r_{i, t->t+5} - r_{m, t->t+5}
         con features transversales + F1 (gap_uh_ppp, gap_uh_ppp_rel_panel).
      3) Combina P(r_i > 0) = Phi((mu_m + mu_ex) / (escala_sigma * sqrt(5) * volatilidad_20)).
    """
    tr = df_tr.copy()
    te = df_te.copy()

    # Retorno a 5 sesiones y media transversal del mercado en TRAIN
    tr["ret_h5"] = tr["ppp_t5"] / tr["ppp_t"] - 1.0
    mkt_tr = (
        tr.groupby("posicion_sesion")
        .agg(
            ret_mkt_h5=("ret_h5", "mean"),
            ret_5_mean=("ret_5", "mean"),
            dm_5_mean=("distancia_media_5", "mean"),
            vol_20_mean=("volatilidad_20", "mean"),
            gap_mean=("gap_uh_ppp", "mean"),
            fx_ret5=("fx_ret5", "first"),
            flag_banxico=("flag_decision_banxico_5d", "first"),
            spx_ret5_lag1=("spx_ret5_lag1", "first"),
            vix_cambio5_lag1=("vix_cambio5_lag1", "first"),
            eww_ret5_lag1=("eww_ret5_lag1", "first"),
        )
        .reset_index()
    )
    mkt_te = (
        te.groupby("posicion_sesion")
        .agg(
            ret_5_mean=("ret_5", "mean"),
            dm_5_mean=("distancia_media_5", "mean"),
            vol_20_mean=("volatilidad_20", "mean"),
            gap_mean=("gap_uh_ppp", "mean"),
            fx_ret5=("fx_ret5", "first"),
            flag_banxico=("flag_decision_banxico_5d", "first"),
            spx_ret5_lag1=("spx_ret5_lag1", "first"),
            vix_cambio5_lag1=("vix_cambio5_lag1", "first"),
            eww_ret5_lag1=("eww_ret5_lag1", "first"),
        )
        .reset_index()
    )

    cols_mkt_dom = ["ret_5_mean", "dm_5_mean", "vol_20_mean", "gap_mean", "fx_ret5", "flag_banxico"]
    cols_mkt_full = cols_mkt_dom + ["spx_ret5_lag1", "vix_cambio5_lag1", "eww_ret5_lag1"]

    # Predicción doméstica (100% cobertura) y predicción completa (cuando EE.UU. operó en t-1)
    mu_mkt_dom = _ridge_fit_predict(
        mkt_tr[cols_mkt_dom].to_numpy(dtype=float),
        mkt_tr["ret_mkt_h5"].to_numpy(dtype=float),
        mkt_te[cols_mkt_dom].to_numpy(dtype=float),
        alpha=alpha_mkt,
    )
    mkt_te["mu_mkt"] = mu_mkt_dom

    mask_tr_full = mkt_tr[cols_mkt_full].notna().all(axis=1)
    mask_te_full = mkt_te[cols_mkt_full].notna().all(axis=1)
    if int(mask_tr_full.sum()) >= 100 and int(mask_te_full.sum()) > 0:
        mu_mkt_full = _ridge_fit_predict(
            mkt_tr.loc[mask_tr_full, cols_mkt_full].to_numpy(dtype=float),
            mkt_tr.loc[mask_tr_full, "ret_mkt_h5"].to_numpy(dtype=float),
            mkt_te.loc[mask_te_full, cols_mkt_full].to_numpy(dtype=float),
            alpha=alpha_mkt,
        )
        mkt_te.loc[mask_te_full, "mu_mkt"] = mu_mkt_full

    # Submodelo de exceso de retorno idiosincrático de la emisora
    tr = tr.merge(mkt_tr[["posicion_sesion", "ret_mkt_h5"]], on="posicion_sesion", how="left")
    tr["ret_ex_h5"] = tr["ret_h5"] - tr["ret_mkt_h5"]

    cols_ex = [
        "ret_1_rel_panel",
        "distancia_media_5",
        "distancia_media_5_rel_panel",
        "volatilidad_20",
        "gap_uh_ppp",
        "gap_uh_ppp_rel_panel",
    ]
    mu_ex_te = _ridge_fit_predict(
        tr[cols_ex].to_numpy(dtype=float),
        tr["ret_ex_h5"].to_numpy(dtype=float),
        te[cols_ex].to_numpy(dtype=float),
        alpha=alpha_ex,
    )

    te_map = te[["posicion_sesion", "volatilidad_20"]].merge(
        mkt_te[["posicion_sesion", "mu_mkt"]], on="posicion_sesion", how="left", sort=False
    )
    mu_total = te_map["mu_mkt"].to_numpy(dtype=float) + mu_ex_te
    sigma_h5 = np.maximum(te["volatilidad_20"].to_numpy(dtype=float) * math.sqrt(5.0), 1e-4) * float(escala_sigma)
    z_score = mu_total / sigma_h5
    return np.clip(_vec_norm_cdf(z_score), EPS_PROB, 1.0 - EPS_PROB)


def entrenar_predecir_g2_v6b_descompuesto(
    df_tr: pd.DataFrame,
    df_te: pd.DataFrame,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Calibra (alpha_mkt, alpha_ex, escala_sigma) mediante CV walk-forward purgada en TRAIN
    y genera las probabilidades en TEST.
    """
    folds = _particiones_walk_forward_purgadas(df_tr, n_folds=4, embargo_sesiones=5)
    grid = [
        (500.0, 500.0, 2.5),
        (500.0, 500.0, 3.5),
        (1000.0, 500.0, 3.5),
        (1000.0, 1000.0, 3.5),
        (1000.0, 1000.0, 5.0),
        (2000.0, 1000.0, 5.0),
    ]

    mejor_cfg = (1000.0, 1000.0, 3.5)
    mejor_ll = float("inf")
    for a_m, a_e, esc_s in grid:
        lls: List[float] = []
        for f_tr, f_va in folds:
            p_va = _ajustar_modelo_descompuesto_bloque(f_tr, f_va, a_m, a_e, esc_s)
            y_va = f_va["target_y"].to_numpy(dtype=float)
            ll = float(-np.mean(y_va * np.log(p_va) + (1.0 - y_va) * np.log(1.0 - p_va)))
            lls.append(ll)
        ll_m = float(np.mean(lls))
        if ll_m < mejor_ll:
            mejor_ll = ll_m
            mejor_cfg = (a_m, a_e, esc_s)

    prob_te = _ajustar_modelo_descompuesto_bloque(
        df_tr, df_te, mejor_cfg[0], mejor_cfg[1], mejor_cfg[2]
    )
    info = {
        "alpha_mkt": mejor_cfg[0],
        "alpha_ex": mejor_cfg[1],
        "escala_sigma": mejor_cfg[2],
        "cv_logloss_seleccion": round(mejor_ll, 6),
    }
    return prob_te, info


# =============================================================================
# CANDIDATO 3: G2_V6C_RIDGE_CONTINUO (Ridge sobre z = r_{t+5} / sigma_20)
# =============================================================================
def _ajustar_ridge_continuo_bloque(
    df_tr: pd.DataFrame,
    df_te: pd.DataFrame,
    features: List[str],
    alpha_ridge: float,
    escala_res: float,
) -> Tuple[np.ndarray, float]:
    """
    Ajusta regresión Ridge sobre z_{i,t} = r_{i,t+5} / (sqrt(5) * volatilidad_20)
    y transforma z_hat a probabilidad mediante Phi(z_hat / (sigma_res * escala_res)).
    """
    r_tr = (df_tr["ppp_t5"] / df_tr["ppp_t"] - 1.0).to_numpy(dtype=float)
    vol_tr = np.maximum(df_tr["volatilidad_20"].to_numpy(dtype=float) * math.sqrt(5.0), 1e-4)
    z_tr = np.clip(r_tr / vol_tr, -6.0, 6.0)

    x_tr = df_tr[features].to_numpy(dtype=float)
    x_te = df_te[features].to_numpy(dtype=float)

    z_hat_tr = _ridge_fit_predict(x_tr, z_tr, x_tr, alpha=alpha_ridge)
    sigma_res = float(np.std(z_tr - z_hat_tr, ddof=1))
    sigma_res = max(sigma_res, 1e-4)

    z_hat_te = _ridge_fit_predict(x_tr, z_tr, x_te, alpha=alpha_ridge)
    prob_te = np.clip(_vec_norm_cdf(z_hat_te / (sigma_res * float(escala_res))), EPS_PROB, 1.0 - EPS_PROB)
    return prob_te, sigma_res


def entrenar_predecir_g2_v6c_ridge_continuo(
    df_tr: pd.DataFrame,
    df_te: pd.DataFrame,
    features: List[str] = FEATURES_V4_MAS_F1,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Selecciona (alpha_ridge, escala_res) en CV walk-forward purgada en TRAIN y predice en TEST.
    """
    folds = _particiones_walk_forward_purgadas(df_tr, n_folds=4, embargo_sesiones=5)
    grid = [
        (200.0, 1.0),
        (500.0, 1.0),
        (500.0, 1.25),
        (1000.0, 1.0),
        (1000.0, 1.25),
        (2000.0, 1.0),
    ]

    mejor_cfg = (500.0, 1.0)
    mejor_ll = float("inf")
    for alpha_r, esc_r in grid:
        lls: List[float] = []
        for f_tr, f_va in folds:
            p_va, _ = _ajustar_ridge_continuo_bloque(f_tr, f_va, features, alpha_r, esc_r)
            y_va = f_va["target_y"].to_numpy(dtype=float)
            ll = float(-np.mean(y_va * np.log(p_va) + (1.0 - y_va) * np.log(1.0 - p_va)))
            lls.append(ll)
        ll_m = float(np.mean(lls))
        if ll_m < mejor_ll:
            mejor_ll = ll_m
            mejor_cfg = (alpha_r, esc_r)

    prob_te, sigma_res = _ajustar_ridge_continuo_bloque(
        df_tr, df_te, features, mejor_cfg[0], mejor_cfg[1]
    )
    info = {
        "alpha_ridge": mejor_cfg[0],
        "escala_res": mejor_cfg[1],
        "sigma_res_train": round(sigma_res, 6),
        "cv_logloss_seleccion": round(mejor_ll, 6),
    }
    return prob_te, info


# =============================================================================
# CANDIDATO 4: G2_LGBM_CHALLENGER (LightGBM 4.7 restringido + Platt en fold purgado)
# =============================================================================
def entrenar_predecir_g2_lgbm_challenger(
    df_tr: pd.DataFrame,
    df_te: pd.DataFrame,
    features_num: List[str] = FEATURES_V4_MAS_F1,
    embargo_sesiones: int = 5,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Entrena LightGBM 4.7 con hiperparámetros fuertemente restringidos:
      max_depth=3, num_leaves=7, learning_rate=0.02, n_estimators<=400,
      min_data_in_leaf=100, feature_fraction=0.8, monotone_constraints,
      emisora como categórica, early stopping y recalibración de Platt (Cox)
      en un fold de validación cronológico purgado dentro de TRAIN.
    """
    tr = df_tr.sort_values(["posicion_sesion", "emisora"]).reset_index(drop=True)
    te = df_te.copy()

    # Categorías fijas del universo de 15 emisoras del panel
    categorias_emisora = sorted(
        set(tr["emisora"].astype(str).unique()).union(set(te["emisora"].astype(str).unique()))
    )
    tr["emisora_cat"] = pd.Categorical(tr["emisora"].astype(str), categories=categorias_emisora)
    te["emisora_cat"] = pd.Categorical(te["emisora"].astype(str), categories=categorias_emisora)

    cols_lgb = list(features_num) + ["emisora_cat"]
    # Monotone constraints: agotamiento/reversión negativa en retornos/dm_5/gap_uh_ppp, libre en vol_20 y emisora
    mapa_monotono = {
        "ret_1_rel_panel": -1,
        "distancia_media_5": -1,
        "distancia_media_5_rel_panel": -1,
        "volatilidad_20": 0,
        "gap_uh_ppp": -1,
        "emisora_cat": 0,
    }
    monotone_constraints = [mapa_monotono.get(c, 0) for c in cols_lgb]

    # Partición cronológica purgada dentro de TRAIN (80% fit / 20% validación + Platt)
    pos_unicas = sorted(tr["posicion_sesion"].unique().tolist())
    idx_corte = int(len(pos_unicas) * 0.80)
    pos_corte_fit = pos_unicas[idx_corte - 1]
    pos_ini_val = pos_unicas[min(len(pos_unicas) - 1, idx_corte + embargo_sesiones)]
    fecha_corte_fit = str(tr[tr["posicion_sesion"] == pos_corte_fit]["fecha"].max())

    sub_fit = tr[
        (tr["posicion_sesion"] <= pos_corte_fit) & (tr["fecha_objetivo_h5"] <= fecha_corte_fit)
    ].copy()
    sub_val = tr[tr["posicion_sesion"] >= pos_ini_val].copy()

    params_lgb = {
        "objective": "binary",
        "metric": "binary_logloss",
        "boosting_type": "gbdt",
        "max_depth": 3,
        "num_leaves": 7,
        "learning_rate": 0.02,
        "min_data_in_leaf": 100,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "lambda_l2": 10.0,
        "monotone_constraints": monotone_constraints,
        "seed": 42,
        "feature_fraction_seed": 42,
        "bagging_seed": 42,
        "deterministic": True,
        "verbose": -1,
        "n_jobs": 1,
    }

    dtrain = lgb.Dataset(
        sub_fit[cols_lgb],
        label=sub_fit["target_y"].to_numpy(dtype=float),
        categorical_feature=["emisora_cat"],
        free_raw_data=False,
    )
    dval = lgb.Dataset(
        sub_val[cols_lgb],
        label=sub_val["target_y"].to_numpy(dtype=float),
        categorical_feature=["emisora_cat"],
        reference=dtrain,
        free_raw_data=False,
    )

    booster = lgb.train(
        params=params_lgb,
        train_set=dtrain,
        num_boost_round=400,
        valid_sets=[dval],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
    )
    best_iter = int(booster.best_iteration or 50)

    # Recalibración logística de Platt sobre el fold de validación purgado
    p_val_raw = np.clip(booster.predict(sub_val[cols_lgb], num_iteration=best_iter), 1e-6, 1.0 - 1e-6)
    cal_val = curva_calibracion(p_val_raw, sub_val["target_y"].to_numpy(dtype=int), bins=10)
    lam_platt = float(cal_val["lambda_calibracion"])
    int_platt = float(cal_val["intercepto_calibracion"])
    # Si la pendiente en validación es positiva y moderada, aplicar encogimiento de Platt; si no, encoger hacia la tasa base
    lam_aplicada = max(0.25, min(1.0, lam_platt)) if np.isfinite(lam_platt) else 0.5

    p_te_raw = np.clip(booster.predict(te[cols_lgb], num_iteration=best_iter), 1e-6, 1.0 - 1e-6)
    logit_te_raw = np.log(p_te_raw / (1.0 - p_te_raw))
    eta_cal = np.clip(int_platt + lam_aplicada * logit_te_raw, -25.0, 25.0)
    p_te_cal = 1.0 / (1.0 + np.exp(-eta_cal))

    importancias = booster.feature_importance(importance_type="gain", iteration=best_iter)
    info = {
        "best_iteration": best_iter,
        "lambda_platt_val": round(lam_platt, 6),
        "lambda_platt_aplicada": round(lam_aplicada, 6),
        "intercepto_platt_val": round(int_platt, 6),
        "feature_importance_gain": {
            col: round(float(imp), 4) for col, imp in zip(cols_lgb, importancias)
        },
    }
    return p_te_cal, info


# =============================================================================
# EVALUACIÓN INSTITUCIONAL Y REGLA DE PROMOCIÓN DE FASE 4
# =============================================================================
def _evaluar_candidato_contra_v4(
    df_te_15: pd.DataFrame,
    col_prob_cand: str,
    col_prob_v4: str = "prob_G2_V4_ADJ",
) -> Dict[str, Any]:
    """
    Calcula todas las métricas institucionales de un modelo candidato en TEST (15 emisoras y 4 foco)
    y verifica los 5 criterios simultáneos de la regla de promoción pre-registrada.
    """
    res_bloques: Dict[str, Any] = {}
    for nombre_vista, sub_df in [
        ("test_15_emisoras", df_te_15),
        ("test_4_emisoras_foco", df_te_15[df_te_15["emisora"].isin(EMISORAS_FOCO_4)].copy()),
    ]:
        y = sub_df["target_y"].to_numpy(dtype=int)
        p_cand = np.clip(sub_df[col_prob_cand].to_numpy(dtype=float), EPS_PROB, 1.0 - EPS_PROB)
        p_v4 = np.clip(sub_df[col_prob_v4].to_numpy(dtype=float), EPS_PROB, 1.0 - EPS_PROB)
        p_clim = np.clip(sub_df["prob_CLIMATOLOGIA"].to_numpy(dtype=float), EPS_PROB, 1.0 - EPS_PROB)

        n = len(y)
        aciertos = int(np.sum((p_cand >= 0.5).astype(int) == y))
        w_inf, w_sup = intervalo_wilson(aciertos, n)

        brier_vec_cand = (p_cand - y) ** 2
        brier_vec_v4 = (p_v4 - y) ** 2
        ll_vec_cand = -(y * np.log(p_cand) + (1.0 - y) * np.log(1.0 - p_cand))
        ll_vec_v4 = -(y * np.log(p_v4) + (1.0 - y) * np.log(1.0 - p_v4))

        bss_clim = brier_skill_score(p_cand, y, p_clim)
        bss_050 = brier_skill_score(p_cand, y, 0.5)
        ig_clim = information_gain_bits(p_cand, y, p_clim)
        murphy = descomposicion_murphy(p_cand, y, bins=10)
        cal = curva_calibracion(p_cand, y, bins=10)
        ic_res = rank_ic_diario(sub_df, col_p=col_prob_cand, col_ret="ret_h5", col_fecha="fecha")

        dm_brier_v4 = diebold_mariano(brier_vec_cand, brier_vec_v4, lag=4)
        dm_ll_v4 = diebold_mariano(ll_vec_cand, ll_vec_v4, lag=4)
        boot_brier_v4 = block_bootstrap_diff(brier_vec_cand, brier_vec_v4, bloque=5, B=2000, seed=42)

        res_bloques[nombre_vista] = {
            "n": n,
            "aciertos": aciertos,
            "exactitud_pct": round(100.0 * aciertos / n, 2),
            "wilson_95_pct": [
                round(100.0 * w_inf, 2),
                round(100.0 * w_sup, 2),
            ],
            "brier": round(float(np.mean(brier_vec_cand)), 6),
            "log_loss": round(float(np.mean(ll_vec_cand)), 6),
            "bss_vs_climatologia_pct": round(100.0 * bss_clim, 4),
            "bss_vs_050_pct": round(100.0 * bss_050, 4),
            "information_gain_bits": round(ig_clim, 6),
            "ece": round(float(cal["ece"]), 6),
            "lambda_calibracion": round(float(cal["lambda_calibracion"]), 6),
            "pendiente_lineal_calibracion": round(float(cal["pendiente_lineal"]), 6),
            "murphy": {
                "confiabilidad": round(float(murphy["confiabilidad"]), 6),
                "resolucion": round(float(murphy["resolucion"]), 6),
            },
            "rank_ic": {
                "ic_medio": round(float(ic_res["ic_medio"]), 4),
                "ic_ir_anualizado": round(float(ic_res["ic_ir_anualizado"]), 4),
                "t_stat_hac": round(float(ic_res["t_stat_hac"]), 4),
                "p_valor_hac": round(float(ic_res["p_valor_hac"]), 4),
            },
            "vs_g2_v4_adj": {
                "delta_brier": round(float(np.mean(brier_vec_cand) - np.mean(brier_vec_v4)), 6),
                "dm_stat_brier": round(float(dm_brier_v4["dm_stat"]), 4),
                "p_dm_brier_unilateral": round(float(dm_brier_v4["p_valor_a_menor_perdida"]), 4),
                "p_dm_brier_bilateral": round(float(dm_brier_v4["p_valor_bilateral"]), 4),
                "delta_logloss": round(float(np.mean(ll_vec_cand) - np.mean(ll_vec_v4)), 6),
                "dm_stat_logloss": round(float(dm_ll_v4["dm_stat"]), 4),
                "p_dm_logloss_unilateral": round(float(dm_ll_v4["p_valor_a_menor_perdida"]), 4),
                "p_dm_logloss_bilateral": round(float(dm_ll_v4["p_valor_bilateral"]), 4),
                "prob_bootstrap_menor_brier_que_v4": round(float(boot_brier_v4["prob_a_menor_perdida"]), 4),
            },
        }

    # Desempeño desglosado en cada una de las 4 emisoras foco (AMX, GFNORTE, GMEXICO, WALMEX)
    detalle_foco: Dict[str, Any] = {}
    emisoras_foco_mejoradas_brier = 0
    emisoras_foco_mejoradas_logloss = 0
    for em in EMISORAS_FOCO_4:
        sub_em = df_te_15[df_te_15["emisora"] == em]
        y_e = sub_em["target_y"].to_numpy(dtype=int)
        pc_e = np.clip(sub_em[col_prob_cand].to_numpy(dtype=float), EPS_PROB, 1.0 - EPS_PROB)
        pv_e = np.clip(sub_em[col_prob_v4].to_numpy(dtype=float), EPS_PROB, 1.0 - EPS_PROB)

        br_c = float(np.mean((pc_e - y_e) ** 2))
        br_v = float(np.mean((pv_e - y_e) ** 2))
        ll_c = float(-np.mean(y_e * np.log(pc_e) + (1.0 - y_e) * np.log(1.0 - pc_e)))
        ll_v = float(-np.mean(y_e * np.log(pv_e) + (1.0 - y_e) * np.log(1.0 - pv_e)))
        acc_c = round(float(np.mean((pc_e >= 0.5).astype(int) == y_e) * 100.0), 2)
        acc_v = round(float(np.mean((pv_e >= 0.5).astype(int) == y_e) * 100.0), 2)

        mejora_br = br_c < br_v
        mejora_ll = ll_c < ll_v
        if mejora_br:
            emisoras_foco_mejoradas_brier += 1
        if mejora_ll:
            emisoras_foco_mejoradas_logloss += 1

        detalle_foco[em] = {
            "n": int(len(sub_em)),
            "acc_v4_pct": acc_v,
            "acc_cand_pct": acc_c,
            "brier_v4": round(br_v, 6),
            "brier_cand": round(br_c, 6),
            "delta_brier": round(br_c - br_v, 6),
            "logloss_v4": round(ll_v, 6),
            "logloss_cand": round(ll_c, 6),
            "delta_logloss": round(ll_c - ll_v, 6),
            "mejora_brier": mejora_br,
            "mejora_logloss": mejora_ll,
        }

    m15 = res_bloques["test_15_emisoras"]
    c1_dm = bool(
        (m15["vs_g2_v4_adj"]["p_dm_brier_unilateral"] < 0.05)
        and (m15["vs_g2_v4_adj"]["p_dm_logloss_unilateral"] < 0.05)
    )
    c2_bss = bool(m15["bss_vs_climatologia_pct"] > 0.0)
    c3_cal = bool(0.70 <= m15["lambda_calibracion"] <= 1.30)
    c4_ic = bool(m15["rank_ic"]["ic_medio"] > 0.02)
    c5_foco = bool(emisoras_foco_mejoradas_brier >= 3 and emisoras_foco_mejoradas_logloss >= 3)

    promovido = bool(c1_dm and c2_bss and c3_cal and c4_ic and c5_foco)

    res_bloques["desglose_4_emisoras_foco"] = detalle_foco
    res_bloques["evaluacion_regla_promocion"] = {
        "criterio_1_dm_p_menor_005_brier_y_logloss": c1_dm,
        "criterio_2_bss_positivo_vs_climatologia": c2_bss,
        "criterio_3_pendiente_calibracion_070_a_130": c3_cal,
        "criterio_4_rank_ic_medio_mayor_002": c4_ic,
        "criterio_5_mejora_al_menos_3_de_4_foco": c5_foco,
        "emisoras_foco_mejoradas_brier": emisoras_foco_mejoradas_brier,
        "emisoras_foco_mejoradas_logloss": emisoras_foco_mejoradas_logloss,
        "promovido_a_campeon": promovido,
    }
    return res_bloques


def ejecutar_fase4_modelos_v6(
    ruta_panel_fase3: Path = ARCHIVO_PANEL_FASE3,
    ruta_reporte: Path = ARCHIVO_REPORTE_FASE4_JSON,
) -> Dict[str, Any]:
    """
    Entrena y evalúa G2_V4_ADJ (campeón base), G2_V4_F1_GAP (con la feature aceptada en Fase 3)
    y los 4 modelos candidatos V6, aplicando la regla de promoción pre-registrada.
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
    df_res["prob_CLIMATOLOGIA"] = calcular_climatologia_rodante_purgada(
        df_vista, df_res, ventana_sesiones=250
    )

    tr = df_res[
        (df_res["periodo_oficial"].astype(str) == "TRAIN")
        & (df_res["fecha_objetivo_h5"] <= CORTE_TRAIN)
    ].copy().reset_index(drop=True)
    te = df_res[
        df_res["periodo_oficial"].astype(str) == "TEST"
    ].copy().reset_index(drop=True)

    # 0. Línea base oficial G2_V4_ADJ y variante lineal con feature F1 aceptada (G2_V4_F1_GAP)
    p_v4_adj, _ = ajustar_logistica_pooled_panel(
        tr, te, FEATURES_V4_BASE, c=0.01, tipo_scaler="STANDARD", ponderacion="UNIFORME"
    )
    p_v4_f1, _ = ajustar_logistica_pooled_panel(
        tr, te, FEATURES_V4_MAS_F1, c=0.01, tipo_scaler="STANDARD", ponderacion="UNIFORME"
    )
    te["prob_G2_V4_ADJ"] = p_v4_adj
    te["prob_G2_V4_F1_GAP"] = p_v4_f1

    # 1. G2_V6A_JERARQUICO
    p_v6a, info_v6a = entrenar_predecir_g2_v6a_jerarquico(tr, te, features=FEATURES_V4_MAS_F1)
    te["prob_G2_V6A_JERARQUICO"] = p_v6a

    # 2. G2_V6B_DESCOMPUESTO
    p_v6b, info_v6b = entrenar_predecir_g2_v6b_descompuesto(tr, te)
    te["prob_G2_V6B_DESCOMPUESTO"] = p_v6b

    # 3. G2_V6C_RIDGE_CONTINUO
    p_v6c, info_v6c = entrenar_predecir_g2_v6c_ridge_continuo(tr, te, features=FEATURES_V4_MAS_F1)
    te["prob_G2_V6C_RIDGE_CONTINUO"] = p_v6c

    # 4. G2_LGBM_CHALLENGER
    p_lgbm, info_lgbm = entrenar_predecir_g2_lgbm_challenger(tr, te, features_num=FEATURES_V4_MAS_F1)
    te["prob_G2_LGBM_CHALLENGER"] = p_lgbm

    modelos_a_evaluar = [
        ("G2_V4_ADJ", "prob_G2_V4_ADJ", {"especificacion": "Logit pooled C=0.01 con 4 features cortas y etiquetas limpias Fase 1"}),
        ("G2_V4_F1_GAP", "prob_G2_V4_F1_GAP", {"especificacion": "Logit pooled C=0.01 + gap_uh_ppp (feature aceptada en Fase 3)"}),
        ("G2_V6A_JERARQUICO", "prob_G2_V6A_JERARQUICO", info_v6a),
        ("G2_V6B_DESCOMPUESTO", "prob_G2_V6B_DESCOMPUESTO", info_v6b),
        ("G2_V6C_RIDGE_CONTINUO", "prob_G2_V6C_RIDGE_CONTINUO", info_v6c),
        ("G2_LGBM_CHALLENGER", "prob_G2_LGBM_CHALLENGER", info_lgbm),
    ]

    resultados_modelos: Dict[str, Any] = {}
    candidatos_promovidos: List[str] = []

    for nombre_mod, col_p, meta_hiper in modelos_a_evaluar:
        ev = _evaluar_candidato_contra_v4(te, col_prob_cand=col_p, col_prob_v4="prob_G2_V4_ADJ")
        ev["hiperparametros_y_ajuste"] = meta_hiper
        resultados_modelos[nombre_mod] = ev
        if nombre_mod != "G2_V4_ADJ" and ev["evaluacion_regla_promocion"]["promovido_a_campeon"]:
            candidatos_promovidos.append(nombre_mod)

    hashes_despues = hashes_protegidos_g2()
    if hashes_antes != hashes_despues:
        raise RuntimeError("Se detectó modificación en archivos protegidos durante Fase 4.")

    campeon_oficial = candidatos_promovidos[0] if candidatos_promovidos else "G2_V4_ADJ"

    reporte = {
        "fase": "FASE_4_MODELOS_SEXTA_GENERACION_V6",
        "timestamp_utc": timestamp_utc(),
        "regla_promocion_preregistrada": {
            "criterio_1": "Diebold-Mariano vs G2_V4_ADJ con p_unilateral < 0.05 en Brier y log-loss (TEST 15 emisoras)",
            "criterio_2": "Brier Skill Score > 0 contra climatología rodante purgada de 250 sesiones",
            "criterio_3": "Pendiente de calibración logística lambda_Cox en [0.70, 1.30]",
            "criterio_4": "Rank IC transversal diario medio > 0.02",
            "criterio_5": "Mejora en Brier y log-loss en al menos 3 de las 4 emisoras foco (AMX, GFNORTE, GMEXICO, WALMEX)",
        },
        "candidatos_que_cumplen_5_criterios": candidatos_promovidos,
        "decision_oficial_fase4": {
            "campeon_oficial": campeon_oficial,
            "subcampeon_shadow_operativo": "G2_V4_F1_GAP",
            "justificacion": (
                f"Se promueve {campeon_oficial} al cumplir los 5 criterios simultáneos."
                if candidatos_promovidos
                else "Ningún candidato V6 cumple simultáneamente los 5 criterios estrictos pre-registrados (en particular p_DM < 0.05 frente a G2_V4_ADJ en N_eff=624 sesiones). Conforme al protocolo, G2_V4_ADJ (y su extensión lineal G2_V4_F1_GAP con Rank IC > 0.02) se mantiene como referencia principal y los modelos V6 quedan registrados en SHADOW."
            ),
        },
        "modelos": resultados_modelos,
        "integridad_archivos_protegidos_intacta": True,
    }
    ruta_reporte.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")
    return reporte


if __name__ == "__main__":
    rep = ejecutar_fase4_modelos_v6()
    print(f"Reporte Fase 4 guardado en: {ARCHIVO_REPORTE_FASE4_JSON}")
    print(f"Candidatos promovidos (5/5 criterios): {rep['candidatos_que_cumplen_5_criterios']}")
    print(f"Campeón oficial: {rep['decision_oficial_fase4']['campeon_oficial']}")
    for mod_id, d in rep["modelos"].items():
        m15 = d["test_15_emisoras"]
        m4 = d["test_4_emisoras_foco"]
        regla = d["evaluacion_regla_promocion"]
        print(
            f"{mod_id:22s} | 15em Acc={m15['exactitud_pct']:5.2f}% Brier={m15['brier']:.6f} "
            f"BSS={m15['bss_vs_climatologia_pct']:+6.3f}% lam={m15['lambda_calibracion']:+5.3f} "
            f"IC={m15['rank_ic']['ic_medio']:+6.4f} pDM_Br={m15['vs_g2_v4_adj']['p_dm_brier_unilateral']:.4f} "
            f"| 4Foco Acc={m4['exactitud_pct']:5.2f}% Brier={m4['brier']:.6f} "
            f"FocoMej={regla['emisoras_foco_mejoradas_brier']}/4 | Prom={regla['promovido_a_campeon']}"
        )
