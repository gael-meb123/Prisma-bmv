from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from experimentos_avanzados_entrenamiento import ajustar_logistica_con_zona_neutral
from experimentos_entrenamiento_desarrollo import (
    VARIABLES_REL_TRES,
    ajustar_logistica_pooled_panel,
)
from higiene_etiquetas_dividendos import (
    EMISORAS_FOCO_4,
    PANEL_AJUSTADO_PATH,
    _preparar_vista_panel,
    construir_panel_con_ppp_ajustado,
)
from metodologia_ppp import CORTE_TRAIN, ROOT, timestamp_utc
from monitor_prospectivo_segunda_generacion import (
    PANEL_PATH,
    VARIABLES_DM5_REL_CUATRO,
    hashes_protegidos_g2,
    predecir_g2_v5_adaptativo_regimen_sectorial,
)

REPORTE_EVAL_INSTITUCIONAL_PATH = ROOT / "reporte_evaluacion_institucional.json"


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Aproximación racional de Acklam para el cuantil normal estándar."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p debe estar en (0, 1)")
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if phigh < p:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def intervalo_wilson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Calcula el intervalo de confianza binomial de Wilson (1927) al nivel 1 - alpha."""
    if n <= 0:
        return (0.0, 1.0)
    k = int(max(0, min(k, n)))
    z = _norm_ppf(1.0 - alpha / 2.0)
    z2 = z * z
    p_hat = float(k) / float(n)
    denom = 1.0 + z2 / float(n)
    centro = (p_hat + z2 / (2.0 * float(n))) / denom
    rad = max(0.0, (p_hat * (1.0 - p_hat) + z2 / (4.0 * float(n))) / float(n))
    margen = (z * math.sqrt(rad)) / denom
    return (float(max(0.0, centro - margen)), float(min(1.0, centro + margen)))


def brier_skill_score(
    p: np.ndarray | list[float],
    y: np.ndarray | list[int],
    p_ref: np.ndarray | list[float] | float,
) -> float:
    """Calcula 1 - Brier(p, y) / Brier(p_ref, y)."""
    p_arr = np.asarray(p, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    p_ref_arr = np.asarray(p_ref, dtype=float)
    brier_mod = float(np.mean((p_arr - y_arr) ** 2))
    brier_ref = float(np.mean((p_ref_arr - y_arr) ** 2))
    if brier_ref <= 1e-15:
        return 0.0
    return float(1.0 - brier_mod / brier_ref)


def descomposicion_murphy(
    p: np.ndarray | list[float],
    y: np.ndarray | list[int],
    bins: int = 10,
) -> dict[str, float]:
    """
    Descomposición clásica de Murphy (1973) del Brier Score:
      Brier_agrupado = Confiabilidad (REL) - Resolución (RES) + Incertidumbre (UNC)
    """
    p_arr = np.clip(np.asarray(p, dtype=float), 0.0, 1.0)
    y_arr = np.asarray(y, dtype=float)
    n = len(y_arr)
    if n == 0:
        return {
            "brier": np.nan,
            "confiabilidad": np.nan,
            "resolucion": np.nan,
            "incertidumbre": np.nan,
            "brier_murphy": np.nan,
        }

    y_bar = float(np.mean(y_arr))
    unc = float(y_bar * (1.0 - y_bar))
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx_bins = np.clip(np.digitize(p_arr, edges[1:-1], right=False), 0, bins - 1)

    rel = 0.0
    res = 0.0
    for b in range(bins):
        mask_b = idx_bins == b
        n_b = int(np.sum(mask_b))
        if n_b == 0:
            continue
        p_b = float(np.mean(p_arr[mask_b]))
        y_b = float(np.mean(y_arr[mask_b]))
        w_b = float(n_b) / float(n)
        rel += w_b * ((p_b - y_b) ** 2)
        res += w_b * ((y_b - y_bar) ** 2)

    brier_exacto = float(np.mean((p_arr - y_arr) ** 2))
    return {
        "brier": brier_exacto,
        "confiabilidad": float(rel),
        "resolucion": float(res),
        "incertidumbre": float(unc),
        "brier_murphy": float(rel - res + unc),
    }


def information_gain_bits(
    p: np.ndarray | list[float],
    y: np.ndarray | list[int],
    p_ref: np.ndarray | list[float] | float = 0.5,
) -> float:
    """
    Ganancia de información esperada en bits por señal respecto a la referencia p_ref:
      IG = LogLoss_base2(p_ref, y) - LogLoss_base2(p, y)
    """
    eps = 1e-12
    p_arr = np.clip(np.asarray(p, dtype=float), eps, 1.0 - eps)
    y_arr = np.asarray(y, dtype=float)
    p_ref_arr = np.clip(np.asarray(p_ref, dtype=float), eps, 1.0 - eps)

    ll_mod_bits = -np.mean(y_arr * np.log2(p_arr) + (1.0 - y_arr) * np.log2(1.0 - p_arr))
    ll_ref_bits = -np.mean(y_arr * np.log2(p_ref_arr) + (1.0 - y_arr) * np.log2(1.0 - p_ref_arr))
    return float(ll_ref_bits - ll_mod_bits)


def curva_calibracion(
    p: np.ndarray | list[float],
    y: np.ndarray | list[int],
    bins: int = 10,
) -> dict[str, Any]:
    """
    Calcula la curva de confiabilidad por cuantiles/intervalos, el Expected Calibration Error (ECE)
    y la pendiente/intercepto de recalibración logística de Cox:
      logit(P(Y=1)) = intercepto + lambda * logit(p)
    Además estima la pendiente lineal alrededor de 0.5 para contracción directa p_tilde = 0.5 + lambda * (p - 0.5).
    """
    eps = 1e-6
    p_arr = np.clip(np.asarray(p, dtype=float), eps, 1.0 - eps)
    y_arr = np.asarray(y, dtype=float)
    n = len(y_arr)
    if n == 0:
        return {
            "ece": np.nan,
            "lambda_calibracion": np.nan,
            "intercepto_calibracion": np.nan,
            "pendiente_lineal": np.nan,
            "bins_detalle": [],
        }

    edges = np.linspace(0.0, 1.0, bins + 1)
    idx_bins = np.clip(np.digitize(p_arr, edges[1:-1], right=False), 0, bins - 1)
    ece = 0.0
    detalle: list[dict[str, Any]] = []
    for b in range(bins):
        mask_b = idx_bins == b
        n_b = int(np.sum(mask_b))
        if n_b == 0:
            continue
        p_b = float(np.mean(p_arr[mask_b]))
        y_b = float(np.mean(y_arr[mask_b]))
        ece += (float(n_b) / float(n)) * abs(p_b - y_b)
        detalle.append(
            {
                "bin": int(b),
                "rango_min": round(float(edges[b]), 2),
                "rango_max": round(float(edges[b + 1]), 2),
                "n": n_b,
                "prob_media": round(p_b, 6),
                "frecuencia_observada": round(y_b, 6),
            }
        )

    # Ajuste de calibración logística de Cox: logit(Y=1) = alpha + lambda * logit(p)
    logits_in = np.log(p_arr / (1.0 - p_arr))
    var_logit = float(np.var(logits_in))
    if var_logit <= 1e-12 or len(np.unique(y_arr)) < 2:
        alpha_cox = 0.0
        lambda_cox = 0.0
        pendiente_lin = 0.0
    else:
        X_aug = np.column_stack([np.ones(n, dtype=float), logits_in])
        beta = np.array([0.0, 1.0], dtype=float)
        reg = np.diag([0.0, 1e-6])
        for _ in range(60):
            z = np.clip(X_aug @ beta, -30.0, 30.0)
            pr = 1.0 / (1.0 + np.exp(-z))
            w = np.maximum(pr * (1.0 - pr), 1e-10)
            grad = X_aug.T @ (pr - y_arr) + reg @ beta
            H = (X_aug.T * w) @ X_aug + reg
            try:
                step = np.linalg.solve(H, grad)
            except np.linalg.LinAlgError:
                break
            beta -= step
            if float(np.max(np.abs(step))) < 1e-8:
                break
        alpha_cox = float(beta[0])
        lambda_cox = float(beta[1])

        # Pendiente OLS con intercepto libre: y = a + b * p
        p_cent = p_arr - float(np.mean(p_arr))
        y_cent = y_arr - float(np.mean(y_arr))
        denom_ols = float(np.sum(p_cent ** 2))
        pendiente_lin = float(np.sum(p_cent * y_cent) / denom_ols) if denom_ols > 1e-12 else 0.0

    return {
        "ece": float(ece),
        "lambda_calibracion": float(lambda_cox),
        "intercepto_calibracion": float(alpha_cox),
        "pendiente_lineal": float(pendiente_lin),
        "bins_detalle": detalle,
    }


def _spearman_corr(x: np.ndarray, y: np.ndarray) -> float:
    s_x = pd.Series(x).rank(method="average").to_numpy(dtype=float)
    s_y = pd.Series(y).rank(method="average").to_numpy(dtype=float)
    vx = s_x - np.mean(s_x)
    vy = s_y - np.mean(s_y)
    denom = float(np.sqrt(np.sum(vx ** 2) * np.sum(vy ** 2)))
    if denom <= 1e-12:
        return np.nan
    return float(np.sum(vx * vy) / denom)


def _newey_west_se_media(serie: np.ndarray, lag: int = 4) -> float:
    x = np.asarray(serie, dtype=float)
    t_len = len(x)
    if t_len <= 1:
        return np.nan
    u = x - float(np.mean(x))
    gamma_0 = float(np.sum(u * u) / t_len)
    omega = gamma_0
    max_k = min(int(lag), t_len - 1)
    for k in range(1, max_k + 1):
        w_k = 1.0 - float(k) / float(max_k + 1)
        gamma_k = float(np.sum(u[k:] * u[:-k]) / t_len)
        omega += 2.0 * w_k * gamma_k
    if omega <= 1e-18:
        omega = max(gamma_0, 1e-18)
    return float(math.sqrt(omega / float(t_len)))


def rank_ic_diario(
    df: pd.DataFrame,
    col_p: str = "prob",
    col_ret: str = "ret_h5",
    col_fecha: str = "fecha",
    min_emisoras: int = 3,
    lag_hac: int = 4,
) -> dict[str, float]:
    """
    Calcula el Rank Information Coefficient (Spearman transversal por sesión) entre la
    probabilidad predicha p y el retorno futuro a 5 sesiones r_{t+5}.
    Devuelve media, desviación estándar, IC-IR anualizado (sqrt(252/5)) y estadístico t HAC.
    """
    ics: list[float] = []
    for _, grp in df.groupby(col_fecha, sort=True):
        sub = grp[[col_p, col_ret]].dropna()
        if len(sub) < min_emisoras:
            continue
        p_v = sub[col_p].to_numpy(dtype=float)
        r_v = sub[col_ret].to_numpy(dtype=float)
        if np.std(p_v) <= 1e-12 or np.std(r_v) <= 1e-12:
            continue
        ic_val = _spearman_corr(p_v, r_v)
        if np.isfinite(ic_val):
            ics.append(ic_val)

    n_fechas = len(ics)
    if n_fechas == 0:
        return {
            "n_fechas_ic": 0,
            "ic_medio": 0.0,
            "ic_std": 0.0,
            "ic_ir_anualizado": 0.0,
            "t_stat_hac": 0.0,
            "p_valor_hac": 1.0,
        }

    ic_arr = np.asarray(ics, dtype=float)
    ic_mean = float(np.mean(ic_arr))
    ic_std = float(np.std(ic_arr, ddof=1)) if n_fechas > 1 else 0.0
    ic_ir = float((ic_mean / ic_std) * math.sqrt(252.0 / 5.0)) if ic_std > 1e-12 else 0.0
    se_hac = _newey_west_se_media(ic_arr, lag=lag_hac)
    t_hac = float(ic_mean / se_hac) if (np.isfinite(se_hac) and se_hac > 1e-12) else 0.0
    p_val = float(2.0 * (1.0 - _norm_cdf(abs(t_hac))))
    return {
        "n_fechas_ic": int(n_fechas),
        "ic_medio": ic_mean,
        "ic_std": ic_std,
        "ic_ir_anualizado": ic_ir,
        "t_stat_hac": t_hac,
        "p_valor_hac": p_val,
    }


def diebold_mariano(
    loss_a: np.ndarray | list[float],
    loss_b: np.ndarray | list[float],
    lag: int = 4,
) -> dict[str, float]:
    """
    Prueba de Diebold-Mariano (1995) con errores estándar Newey-West HAC de rezago `lag`.
    Evalúa d_t = loss_a_t - loss_b_t (valores negativos indican que el modelo A tiene menor pérdida).
    """
    la = np.asarray(loss_a, dtype=float)
    lb = np.asarray(loss_b, dtype=float)
    if len(la) != len(lb) or len(la) == 0:
        raise ValueError("loss_a y loss_b deben tener la misma longitud positiva.")
    d = la - lb
    diff_mean = float(np.mean(d))
    if np.allclose(d, 0.0):
        return {
            "diff_media": 0.0,
            "se_hac": 0.0,
            "dm_stat": 0.0,
            "p_valor_bilateral": 1.0,
            "p_valor_a_menor_perdida": 0.5,
        }
    se_hac = _newey_west_se_media(d, lag=lag)
    dm_stat = float(diff_mean / se_hac) if se_hac > 1e-15 else 0.0
    p_bi = float(2.0 * (1.0 - _norm_cdf(abs(dm_stat))))
    p_uni_a_mejor = float(_norm_cdf(dm_stat))
    return {
        "diff_media": diff_mean,
        "se_hac": float(se_hac),
        "dm_stat": dm_stat,
        "p_valor_bilateral": p_bi,
        "p_valor_a_menor_perdida": p_uni_a_mejor,
    }


def block_bootstrap_diff(
    loss_a: np.ndarray | list[float],
    loss_b: np.ndarray | list[float],
    bloque: int = 5,
    B: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict[str, float]:
    """
    Moving Block Bootstrap sobre d_t = loss_a_t - loss_b_t con tamaño de bloque `bloque`.
    """
    la = np.asarray(loss_a, dtype=float)
    lb = np.asarray(loss_b, dtype=float)
    if len(la) != len(lb) or len(la) == 0:
        raise ValueError("loss_a y loss_b deben tener la misma longitud positiva.")
    d = la - lb
    n = len(d)
    b_len = max(1, min(int(bloque), n))
    n_blocks = int(math.ceil(float(n) / float(b_len)))
    rng = np.random.default_rng(seed)

    starts = rng.integers(0, n - b_len + 1, size=(B, n_blocks))
    offsets = np.arange(b_len)[None, None, :]
    idx = (starts[:, :, None] + offsets).reshape(B, n_blocks * b_len)[:, :n]
    boot_means = np.mean(d[idx], axis=1)

    q_low = float(np.percentile(boot_means, 100.0 * (alpha / 2.0)))
    q_high = float(np.percentile(boot_means, 100.0 * (1.0 - alpha / 2.0)))
    prob_a_mejor = float(np.mean(boot_means < 0.0))
    return {
        "diff_media": float(np.mean(d)),
        "ic_inferior": q_low,
        "ic_superior": q_high,
        "prob_a_menor_perdida": prob_a_mejor,
    }


def n_efectivo(y: np.ndarray | list[float], lag: int = 4) -> float:
    """
    Tamaño de muestra efectivo ajustado por autocorrelación serial hasta el orden `lag`:
      N_eff = N / (1 + 2 * sum_{k=1..lag} (1 - k/(lag+1)) * max(0, rho_k))
    """
    arr = np.asarray(y, dtype=float)
    n = len(arr)
    if n <= 1:
        return float(n)
    u = arr - float(np.mean(arr))
    var_u = float(np.sum(u * u))
    if var_u <= 1e-15:
        return float(n)

    factor_inflacion = 1.0
    max_k = min(int(lag), n - 1)
    for k in range(1, max_k + 1):
        rho_k = float(np.sum(u[k:] * u[:-k]) / var_u)
        if rho_k > 0.0:
            w_k = 1.0 - float(k) / float(max_k + 1)
            factor_inflacion += 2.0 * w_k * rho_k
    return float(max(1.0, min(float(n), float(n) / factor_inflacion)))


def calcular_climatologia_rodante_purgada(
    df_panel: pd.DataFrame,
    df_eval: pd.DataFrame,
    ventana_sesiones: int = 250,
) -> np.ndarray:
    """
    Para cada fila de df_eval en fecha t, calcula la prevalencia histórica de target_y
    usando exclusivamente observaciones con etiqueta vencida (fecha_objetivo_h5 <= t y fecha < t)
    en las últimas `ventana_sesiones` sesiones disponibles antes de t.
    """
    hist_elig = df_panel[
        df_panel["target_disponible"].astype(str).isin(["True", "true", "1"])
        & df_panel["target_y"].notna()
    ].copy()
    hist_elig = hist_elig.sort_values(["posicion_sesion", "emisora"]).reset_index(drop=True)

    fechas_eval = df_eval["fecha"].astype(str).tolist()
    cache_por_fecha: dict[str, float] = {}
    for f_t in sorted(set(fechas_eval)):
        sub = hist_elig[(hist_elig["fecha"] < f_t) & (hist_elig["fecha_objetivo_h5"] <= f_t)]
        if sub.empty:
            cache_por_fecha[f_t] = 0.5
            continue
        ult_posiciones = sorted(sub["posicion_sesion"].unique().tolist())[-ventana_sesiones:]
        sub_win = sub[sub["posicion_sesion"].isin(ult_posiciones)]
        cache_por_fecha[f_t] = float(sub_win["target_y"].mean())

    return np.array([cache_por_fecha[f] for f in fechas_eval], dtype=float)


def estimar_lambda_calibracion_cv_purgada_train(
    df_vista: pd.DataFrame,
    features: list[str],
    c_val: float = 0.01,
    n_folds: int = 4,
    embargo_sesiones: int = 5,
) -> dict[str, float]:
    """
    Estima la pendiente de calibración (lambda) exclusivamente dentro de TRAIN (<= CORTE_TRAIN)
    mediante validación cruzada walk-forward expandida con purga y embargo de 5 sesiones.
    Esta lambda es 100% libre de fuga hacia TEST y alimenta el dimensionamiento en la Fase 5.
    """
    mask_tr = (
        (df_vista["periodo_oficial"].astype(str) == "TRAIN")
        & (df_vista["target_disponible"].astype(str).isin(["True", "true", "1"]))
        & (df_vista["fecha_objetivo_h5"] <= CORTE_TRAIN)
        & df_vista["target_y"].notna()
        & df_vista["ret_10"].notna()
    )
    tr = df_vista[mask_tr].sort_values(["posicion_sesion", "emisora"]).reset_index(drop=True)
    tr["target_y"] = tr["target_y"].astype(int)

    pos_unicas = sorted(tr["posicion_sesion"].unique().tolist())
    n_pos = len(pos_unicas)
    min_train_pos = int(n_pos * 0.40)
    bloque_val = max(20, int((n_pos - min_train_pos) / n_folds))

    probs_oof: list[float] = []
    ys_oof: list[int] = []
    for k in range(n_folds):
        idx_fin_tr = min_train_pos + k * bloque_val
        idx_ini_val = idx_fin_tr + embargo_sesiones
        idx_fin_val = min(n_pos, idx_ini_val + bloque_val)
        if idx_ini_val >= n_pos:
            break
        pos_corte_tr = pos_unicas[idx_fin_tr - 1]
        pos_ini_val = pos_unicas[idx_ini_val]
        pos_fin_val = pos_unicas[idx_fin_val - 1]

        # Purga: fecha_objetivo_h5 de train no puede traslapar con el inicio de validación
        fecha_corte_tr = str(tr[tr["posicion_sesion"] == pos_corte_tr]["fecha"].max())
        fold_tr = tr[
            (tr["posicion_sesion"] <= pos_corte_tr) & (tr["fecha_objetivo_h5"] <= fecha_corte_tr)
        ].copy()
        fold_va = tr[
            (tr["posicion_sesion"] >= pos_ini_val) & (tr["posicion_sesion"] <= pos_fin_val)
        ].copy()
        if len(fold_tr) < 200 or len(fold_va) == 0:
            continue

        p_va, _ = ajustar_logistica_pooled_panel(
            fold_tr, fold_va, features, c=float(c_val), tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        probs_oof.extend(p_va.tolist())
        ys_oof.extend(fold_va["target_y"].astype(int).tolist())

    cal = curva_calibracion(probs_oof, ys_oof, bins=10)
    return {
        "n_oof_train": len(ys_oof),
        "lambda_calibracion_cox": round(float(cal["lambda_calibracion"]), 6),
        "pendiente_lineal": round(float(cal["pendiente_lineal"]), 6),
        "ece_oof_train": round(float(cal["ece"]), 6),
    }


def _evaluar_panel_completo_en_test(df_vista: pd.DataFrame) -> pd.DataFrame:
    """
    Genera en TEST las probabilidades de los 3 baselines obligatorios:
      - CLIMATOLOGIA (prevalencia rodante purgada a 250 sesiones)
      - SIEMPRE_SUBIDA (p = 1 - 1e-6, predicción constante clase 1)
      - MOMENTUM_INGENUO (p = 0.5 + 0.1 * sign(ret_5))
    y de los 5 modelos G2 (V1, V2, V3, V4, V5).
    """
    mask_tr = (
        (df_vista["periodo_oficial"].astype(str) == "TRAIN")
        & (df_vista["target_disponible"].astype(str).isin(["True", "true", "1"]))
        & (df_vista["fecha_objetivo_h5"] <= CORTE_TRAIN)
        & df_vista["target_y"].notna()
        & df_vista["ret_10"].notna()
    )
    mask_te = (
        (df_vista["periodo_oficial"].astype(str) == "TEST")
        & (df_vista["target_disponible"].astype(str).isin(["True", "true", "1"]))
        & df_vista["target_y"].notna()
        & df_vista["ret_10"].notna()
    )

    tr = df_vista[mask_tr].copy().reset_index(drop=True)
    te = df_vista[mask_te].copy().reset_index(drop=True)
    tr["target_y"] = tr["target_y"].astype(int)
    te["target_y"] = te["target_y"].astype(int)
    te["ret_h5"] = te["ppp_t5"] / te["ppp_t"] - 1.0

    # Baselines obligatorios
    te["prob_CLIMATOLOGIA"] = calcular_climatologia_rodante_purgada(
        df_vista, te, ventana_sesiones=250
    )
    # SIEMPRE_SUBIDA: predicción direccional siempre 1 con probabilidad 0.55 para log-loss/Brier definidos
    te["prob_SIEMPRE_SUBIDA"] = np.full(len(te), 0.55, dtype=float)
    te["prob_MOMENTUM_INGENUO"] = 0.5 + 0.1 * np.sign(te["ret_5"].to_numpy(dtype=float))

    # Modelos G2 V1..V5
    p_v1, _ = ajustar_logistica_pooled_panel(
        tr, te, VARIABLES_REL_TRES, c=0.01, tipo_scaler="STANDARD", ponderacion="UNIFORME"
    )
    p_v2 = ajustar_logistica_con_zona_neutral(
        tr, te, VARIABLES_REL_TRES, c=0.01, tau=0.0025, modo_panel=True
    )
    p_v3, _ = ajustar_logistica_pooled_panel(
        tr, te, VARIABLES_REL_TRES, c=0.001, tipo_scaler="STANDARD", ponderacion="UNIFORME"
    )
    p_v4, _ = ajustar_logistica_pooled_panel(
        tr, te, VARIABLES_DM5_REL_CUATRO, c=0.01, tipo_scaler="STANDARD", ponderacion="UNIFORME"
    )
    p_v5 = predecir_g2_v5_adaptativo_regimen_sectorial(tr, te)

    te["prob_G2_V1"] = p_v1
    te["prob_G2_V2"] = p_v2
    te["prob_G2_V3"] = p_v3
    te["prob_G2_V4"] = p_v4
    te["prob_G2_V5"] = p_v5
    return te


def _resumir_bloque_institucional(df_te: pd.DataFrame, sufijo_etiqueta: str = "") -> dict[str, Any]:
    """
    Calcula todas las métricas institucionales para los baselines y modelos en un subconjunto de TEST.
    """
    y = df_te["target_y"].to_numpy(dtype=int)
    n = len(y)
    n_eff_y = n_efectivo(y, lag=4)
    p_clim = np.clip(df_te["prob_CLIMATOLOGIA"].to_numpy(dtype=float), 1e-12, 1.0 - 1e-12)
    loss_brier_clim = (p_clim - y) ** 2
    loss_ll_clim = -(y * np.log(p_clim) + (1.0 - y) * np.log(1.0 - p_clim))

    p_v1 = np.clip(df_te["prob_G2_V1"].to_numpy(dtype=float), 1e-12, 1.0 - 1e-12)
    loss_brier_v1 = (p_v1 - y) ** 2

    series_evaluar = [
        ("CLIMATOLOGIA", "prob_CLIMATOLOGIA"),
        ("SIEMPRE_SUBIDA", "prob_SIEMPRE_SUBIDA"),
        ("MOMENTUM_INGENUO", "prob_MOMENTUM_INGENUO"),
        (f"G2_V1{sufijo_etiqueta}", "prob_G2_V1"),
        (f"G2_V2{sufijo_etiqueta}", "prob_G2_V2"),
        (f"G2_V3{sufijo_etiqueta}", "prob_G2_V3"),
        (f"G2_V4{sufijo_etiqueta}", "prob_G2_V4"),
        (f"G2_V5{sufijo_etiqueta}", "prob_G2_V5"),
    ]

    resultados: dict[str, Any] = {}
    for nombre_serie, col_p in series_evaluar:
        p = np.clip(df_te[col_p].to_numpy(dtype=float), 1e-12, 1.0 - 1e-12)
        pred = (p >= 0.5).astype(int)
        aciertos = int(np.sum(pred == y))
        acc_pct = round(100.0 * aciertos / n, 2)
        w_low, w_high = intervalo_wilson(aciertos, n, alpha=0.05)

        brier = float(np.mean((p - y) ** 2))
        bss_clim = brier_skill_score(p, y, p_clim)
        bss_05 = brier_skill_score(p, y, 0.5)
        murphy = descomposicion_murphy(p, y, bins=10)

        ll_nats = float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))
        ig_bits_clim = information_gain_bits(p, y, p_clim)
        ig_bits_05 = information_gain_bits(p, y, 0.5)

        cal = curva_calibracion(p, y, bins=10)
        ic_info = rank_ic_diario(
            df_te, col_p=col_p, col_ret="ret_h5", col_fecha="fecha", min_emisoras=3, lag_hac=4
        )

        loss_brier_m = (p - y) ** 2
        loss_ll_m = -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))
        dm_brier_clim = diebold_mariano(loss_brier_m, loss_brier_clim, lag=4)
        dm_ll_clim = diebold_mariano(loss_ll_m, loss_ll_clim, lag=4)
        dm_brier_v1 = diebold_mariano(loss_brier_m, loss_brier_v1, lag=4)
        boot_brier_clim = block_bootstrap_diff(
            loss_brier_m, loss_brier_clim, bloque=5, B=2000, alpha=0.05, seed=42
        )

        resultados[nombre_serie] = {
            "n": int(n),
            "n_efectivo_lag4": round(float(n_eff_y), 1),
            "aciertos": aciertos,
            "exactitud_pct": acc_pct,
            "intervalo_wilson_95_pct": [round(100.0 * w_low, 2), round(100.0 * w_high, 2)],
            "brier": round(brier, 6),
            "bss_vs_climatologia": round(bss_clim, 6),
            "bss_vs_050": round(bss_05, 6),
            "descomposicion_murphy": {
                "confiabilidad": round(murphy["confiabilidad"], 6),
                "resolucion": round(murphy["resolucion"], 6),
                "incertidumbre": round(murphy["incertidumbre"], 6),
                "brier_murphy": round(murphy["brier_murphy"], 6),
            },
            "log_loss_nats": round(ll_nats, 6),
            "information_gain_bits_vs_climatologia": round(ig_bits_clim, 6),
            "information_gain_bits_vs_050": round(ig_bits_05, 6),
            "calibracion": {
                "ece": round(cal["ece"], 6),
                "lambda_calibracion": round(cal["lambda_calibracion"], 6),
                "intercepto_calibracion": round(cal["intercepto_calibracion"], 6),
                "pendiente_lineal": round(cal["pendiente_lineal"], 6),
                "bins_detalle": cal["bins_detalle"],
            },
            "rank_ic": {
                "n_fechas_ic": ic_info["n_fechas_ic"],
                "ic_medio": round(ic_info["ic_medio"], 6),
                "ic_std": round(ic_info["ic_std"], 6),
                "ic_ir_anualizado": round(ic_info["ic_ir_anualizado"], 4),
                "t_stat_hac": round(ic_info["t_stat_hac"], 4),
                "p_valor_hac": round(ic_info["p_valor_hac"], 4),
            },
            "diebold_mariano_brier_vs_climatologia": {
                k: round(float(v), 6) for k, v in dm_brier_clim.items()
            },
            "diebold_mariano_logloss_vs_climatologia": {
                k: round(float(v), 6) for k, v in dm_ll_clim.items()
            },
            "diebold_mariano_brier_vs_v1": {
                k: round(float(v), 6) for k, v in dm_brier_v1.items()
            },
            "block_bootstrap_brier_vs_climatologia": {
                k: round(float(v), 6) for k, v in boot_brier_clim.items()
            },
        }
    return resultados


def ejecutar_evaluacion_institucional(
    panel_ajustado_path: Path = PANEL_AJUSTADO_PATH,
    reporte_path: Path = REPORTE_EVAL_INSTITUCIONAL_PATH,
) -> dict[str, Any]:
    """
    Ejecuta la evaluación institucional completa (Fase 2) sobre TEST para:
      - 15 emisoras y 4 emisoras foco (vista original congelada)
      - 15 emisoras y 4 emisoras foco (vista limpia ajustada por dividendos de la Fase 1)
    y documenta la pendiente de calibración lambda de V4 (tanto en CV purgada dentro de TRAIN
    como en TEST).
    """
    hashes_antes = hashes_protegidos_g2()

    if not panel_ajustado_path.exists():
        df_panel_adj = construir_panel_con_ppp_ajustado(output_path=panel_ajustado_path)
    else:
        df_panel_adj = pd.read_csv(panel_ajustado_path, dtype=str)

    vista_orig = _preparar_vista_panel(df_panel_adj, usar_ajustado=False)
    vista_adj = _preparar_vista_panel(df_panel_adj, usar_ajustado=True)

    te_orig_15 = _evaluar_panel_completo_en_test(vista_orig)
    te_orig_4 = te_orig_15[te_orig_15["emisora"].isin(EMISORAS_FOCO_4)].copy().reset_index(drop=True)

    te_adj_15 = _evaluar_panel_completo_en_test(vista_adj)
    te_adj_4 = te_adj_15[te_adj_15["emisora"].isin(EMISORAS_FOCO_4)].copy().reset_index(drop=True)

    res_orig_15 = _resumir_bloque_institucional(te_orig_15, sufijo_etiqueta="")
    res_orig_4 = _resumir_bloque_institucional(te_orig_4, sufijo_etiqueta="")
    res_adj_15 = _resumir_bloque_institucional(te_adj_15, sufijo_etiqueta="_ADJ")
    res_adj_4 = _resumir_bloque_institucional(te_adj_4, sufijo_etiqueta="_ADJ")

    # Estimación de lambda exclusivamente con datos pasados (CV walk-forward purgada en TRAIN <= 2025-04-29)
    lam_cv_orig = estimar_lambda_calibracion_cv_purgada_train(
        vista_orig, VARIABLES_DM5_REL_CUATRO, c_val=0.01
    )
    lam_cv_adj = estimar_lambda_calibracion_cv_purgada_train(
        vista_adj, VARIABLES_DM5_REL_CUATRO, c_val=0.01
    )

    hashes_despues = hashes_protegidos_g2()
    if hashes_antes != hashes_despues:
        raise RuntimeError("Se detectó modificación en archivos protegidos durante Fase 2.")

    reporte = {
        "fase": "FASE_2_MARCO_EVALUACION_INSTITUCIONAL",
        "timestamp_utc": timestamp_utc(),
        "lambda_calibracion_v4": {
            "train_cv_purgada_sin_fuga_orig": lam_cv_orig,
            "train_cv_purgada_sin_fuga_adj": lam_cv_adj,
            "test_15_emisoras_orig": res_orig_15["G2_V4"]["calibracion"]["lambda_calibracion"],
            "test_4_foco_orig": res_orig_4["G2_V4"]["calibracion"]["lambda_calibracion"],
            "test_15_emisoras_adj": res_adj_15["G2_V4_ADJ"]["calibracion"]["lambda_calibracion"],
            "test_4_foco_adj": res_adj_4["G2_V4_ADJ"]["calibracion"]["lambda_calibracion"],
        },
        "test_15_emisoras": res_orig_15,
        "test_4_emisoras_foco": res_orig_4,
        "test_15_emisoras_ajustado_fase1": res_adj_15,
        "test_4_emisoras_foco_ajustado_fase1": res_adj_4,
        "integridad_archivos_protegidos_intacta": True,
    }
    reporte_path.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")
    return reporte


if __name__ == "__main__":
    rep = ejecutar_evaluacion_institucional()
    print(json.dumps(rep["lambda_calibracion_v4"], indent=2, ensure_ascii=False))

