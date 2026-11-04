import hashlib
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

from experimento_ajuste_dividendos import (
    FEATURES_8,
    build_adjusted_features_and_indicator,
    evaluate_predictions,
    fit_logistic_regression_balanced,
    load_data,
    predict_proba_logistic,
    standard_scale,
)

DOWNLOADS = Path(r"C:\Users\GAELMENDOZABALLARDO\Downloads")
OUT_DIR = Path(r"D:\Universidad\7mo Semestre\Big Data\Proyecto final")


# ==============================================================================
# 1. IMPLEMENTACION DE ALGORITMOS DE IA / ML (SIN DEPENDENCIAS EXTERNAS)
# ==============================================================================

def fit_elasticnet_logistic_balanced(X, y, C=0.1, l1_ratio=0.5, max_iter=400, lr=0.05):
    """Regresion Logistica con penalizacion combinada L1 (Lasso) + L2 (Ridge) e ISTA."""
    n_samples, n_features = X.shape
    n0, n1 = np.sum(y == 0), np.sum(y == 1)
    w0, w1 = n_samples / (2.0 * n0), n_samples / (2.0 * n1)
    sw = np.where(y == 1, w1, w0) / n_samples

    w = np.zeros(n_features, dtype=float)
    b = 0.0
    lam = 1.0 / (C * n_samples)
    l1_pen = lam * l1_ratio
    l2_pen = lam * (1.0 - l1_ratio)

    for _ in range(max_iter):
        z = X @ w + b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))
        diff = sw * (p - y)
        grad_w = X.T @ diff + l2_pen * w
        grad_b = float(np.sum(diff))

        w_temp = w - lr * grad_w
        # Operador proximal de umbral suave (soft-thresholding) para L1
        thresh = lr * l1_pen
        w = np.sign(w_temp) * np.maximum(np.abs(w_temp) - thresh, 0.0)
        b -= lr * grad_b

    return w, b


class DecisionStumpNode:
    def __init__(self, feature=None, threshold=None, left=None, right=None, value=None):
        self.feature = feature
        self.threshold = threshold
        self.left = left
        self.right = right
        self.value = value


def build_tree(X, y, sw, depth=0, max_depth=3, min_samples_leaf=20, rng=None, mtry=None):
    n_samples, n_features = X.shape
    w_sum = float(np.sum(sw))
    p_leaf = float(np.sum(sw * y) / w_sum) if w_sum > 0 else 0.5

    if depth >= max_depth or n_samples < 2 * min_samples_leaf or len(np.unique(y)) == 1:
        return DecisionStumpNode(value=p_leaf)

    feat_indices = (
        rng.choice(n_features, size=mtry, replace=False)
        if (rng is not None and mtry is not None and mtry < n_features)
        else np.arange(n_features)
    )

    best_gain = 0.0
    best_feat = None
    best_thresh = None
    best_left_mask = None

    base_impurity = 2.0 * p_leaf * (1.0 - p_leaf) * w_sum

    for f in feat_indices:
        col = X[:, f]
        quantiles = np.percentile(col, [15, 30, 45, 50, 55, 70, 85])
        for th in np.unique(quantiles):
            left_mask = col <= th
            n_left = int(np.sum(left_mask))
            n_right = n_samples - n_left
            if n_left < min_samples_leaf or n_right < min_samples_leaf:
                continue
            sw_l = sw[left_mask]
            sw_r = sw[~left_mask]
            wl = float(np.sum(sw_l))
            wr = float(np.sum(sw_r))
            if wl <= 0 or wr <= 0:
                continue
            pl = float(np.sum(sw_l * y[left_mask]) / wl)
            pr = float(np.sum(sw_r * y[~left_mask]) / wr)
            imp = 2.0 * pl * (1.0 - pl) * wl + 2.0 * pr * (1.0 - pr) * wr
            gain = base_impurity - imp
            if gain > best_gain:
                best_gain = gain
                best_feat = int(f)
                best_thresh = float(th)
                best_left_mask = left_mask

    if best_feat is None:
        return DecisionStumpNode(value=p_leaf)

    left_node = build_tree(
        X[best_left_mask],
        y[best_left_mask],
        sw[best_left_mask],
        depth + 1,
        max_depth,
        min_samples_leaf,
        rng,
        mtry,
    )
    right_node = build_tree(
        X[~best_left_mask],
        y[~best_left_mask],
        sw[~best_left_mask],
        depth + 1,
        max_depth,
        min_samples_leaf,
        rng,
        mtry,
    )
    return DecisionStumpNode(feature=best_feat, threshold=best_thresh, left=left_node, right=right_node)


def predict_tree_single(node, x):
    while node.value is None:
        if x[node.feature] <= node.threshold:
            node = node.left
        else:
            node = node.right
    return node.value


def predict_tree(node, X):
    return np.array([predict_tree_single(node, row) for row in X], dtype=float)


def fit_predict_random_forest(X_tr, y_tr, X_va, n_estimators=80, max_depth=3, min_samples_leaf=25, seed=42):
    rng = np.random.default_rng(seed)
    n_samples, n_features = X_tr.shape
    n0, n1 = np.sum(y_tr == 0), np.sum(y_tr == 1)
    w0, w1 = n_samples / (2.0 * n0), n_samples / (2.0 * n1)
    sw = np.where(y_tr == 1, w1, w0)
    mtry = max(2, int(np.sqrt(n_features)))

    preds_va = np.zeros(len(X_va), dtype=float)
    for _ in range(n_estimators):
        idx = rng.choice(n_samples, size=n_samples, replace=True)
        tree = build_tree(
            X_tr[idx],
            y_tr[idx],
            sw[idx],
            depth=0,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            rng=rng,
            mtry=mtry,
        )
        preds_va += predict_tree(tree, X_va)
    return preds_va / n_estimators


def fit_predict_gbdt(X_tr, y_tr, X_va, n_estimators=50, learning_rate=0.05, max_depth=2, min_samples_leaf=30, seed=42):
    """Gradient Boosting Decision Trees sobre log-loss balanceado (estilo XGBoost/LightGBM)."""
    rng = np.random.default_rng(seed)
    n_samples, _ = X_tr.shape
    n0, n1 = np.sum(y_tr == 0), np.sum(y_tr == 1)
    w0, w1 = n_samples / (2.0 * n0), n_samples / (2.0 * n1)
    sw = np.where(y_tr == 1, w1, w0)

    # Inicializar en 0.0 (probabilidad 0.5 porque las clases estan balanceadas por sw)
    f_tr = np.zeros(n_samples, dtype=float)
    f_va = np.zeros(len(X_va), dtype=float)

    for _ in range(n_estimators):
        p_tr = 1.0 / (1.0 + np.exp(-np.clip(f_tr, -20, 20)))
        # Pseudo-residuo (gradiente negativo de log-loss)
        residual = y_tr - p_tr
        # Submuestreo estocastico al 80% para regularizar
        sub_idx = rng.choice(n_samples, size=int(0.8 * n_samples), replace=False)
        # Ajustar arbol de regresion sobre (residual + 0.5) escalado
        y_pseudo = np.clip(residual[sub_idx] + 0.5, 0.0, 1.0)
        tree = build_tree(
            X_tr[sub_idx],
            y_pseudo,
            sw[sub_idx],
            depth=0,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            rng=rng,
            mtry=None,
        )
        step_tr = (predict_tree(tree, X_tr) - 0.5) * 4.0  # Escala Newton aproximada p(1-p)~0.25
        step_va = (predict_tree(tree, X_va) - 0.5) * 4.0
        f_tr += learning_rate * step_tr
        f_va += learning_rate * step_va

    return 1.0 / (1.0 + np.exp(-np.clip(f_va, -20, 20)))


def fit_predict_mlp(X_tr, y_tr, X_va, hidden=(16, 8), lr=0.01, l2_reg=0.02, epochs=250, seed=42):
    """Red Neuronal Perceptron Multicapa (MLP) con activacion tanh, L2 weight decay y Adam."""
    rng = np.random.default_rng(seed)
    n_samples, n_in = X_tr.shape
    n0, n1 = np.sum(y_tr == 0), np.sum(y_tr == 1)
    w0, w1 = n_samples / (2.0 * n0), n_samples / (2.0 * n1)
    sw = (np.where(y_tr == 1, w1, w0) / n_samples).reshape(-1, 1)
    y_col = y_tr.reshape(-1, 1)

    h1, h2 = hidden
    W1 = rng.normal(0, np.sqrt(1.0 / n_in), size=(n_in, h1))
    b1 = np.zeros((1, h1))
    W2 = rng.normal(0, np.sqrt(1.0 / h1), size=(h1, h2))
    b2 = np.zeros((1, h2))
    W3 = rng.normal(0, np.sqrt(1.0 / h2), size=(h2, 1))
    b3 = np.zeros((1, 1))

    params = [W1, b1, W2, b2, W3, b3]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    beta1, beta2, eps = 0.9, 0.999, 1e-8

    for t in range(1, epochs + 1):
        # Forward
        z1 = X_tr @ W1 + b1
        a1 = np.tanh(z1)
        z2 = a1 @ W2 + b2
        a2 = np.tanh(z2)
        z3 = a2 @ W3 + b3
        p = 1.0 / (1.0 + np.exp(-np.clip(z3, -50, 50)))

        # Backward
        dz3 = sw * (p - y_col)
        dW3 = a2.T @ dz3 + l2_reg * W3
        db3 = np.sum(dz3, axis=0, keepdims=True)

        da2 = dz3 @ W3.T
        dz2 = da2 * (1.0 - a2 ** 2)
        dW2 = a1.T @ dz2 + l2_reg * W2
        db2 = np.sum(dz2, axis=0, keepdims=True)

        da1 = dz2 @ W2.T
        dz1 = da1 * (1.0 - a1 ** 2)
        dW1 = X_tr.T @ dz1 + l2_reg * W1
        db1 = np.sum(dz1, axis=0, keepdims=True)

        grads = [dW1, db1, dW2, db2, dW3, db3]
        for i, (param, g) in enumerate(zip(params, grads)):
            m[i] = beta1 * m[i] + (1.0 - beta1) * g
            v[i] = beta2 * v[i] + (1.0 - beta2) * (g ** 2)
            m_hat = m[i] / (1.0 - beta1 ** t)
            v_hat = v[i] / (1.0 - beta2 ** t)
            param -= lr * m_hat / (np.sqrt(v_hat) + eps)

    # Prediccion en validacion
    a1_va = np.tanh(X_va @ W1 + b1)
    a2_va = np.tanh(a1_va @ W2 + b2)
    z3_va = (a2_va @ W3 + b3).ravel()
    return 1.0 / (1.0 + np.exp(-np.clip(z3_va, -50, 50)))


# ==============================================================================
# 2. EXTRACCION DE BOLETINES REGULATORIOS TRIMESTRALES OFICIALES (WALMEX / BMV)
# ==============================================================================

def load_official_quarterly_regulatory_data():
    """
    Extrae de Resumen_Ventas_Walmex_2T26.xlsx las tasas oficiales de crecimiento de
    Ventas Unidades Iguales (Mismas Tiendas - SSS) y Unidades Totales en Mexico de 1T16 a 2T26,
    y las vincula con las fechas de publicacion trimestral con rezago estricto t+1.
    """
    xlsx_path = DOWNLOADS / "Resumen_Ventas_Walmex_2T26.xlsx"
    df_ut = pd.read_excel(xlsx_path, sheet_name="UT México")
    df_ui = pd.read_excel(xlsx_path, sheet_name="UI México")

    years = [int(y) for y in df_ui.iloc[4, 2:13].tolist()]
    q_map_ut = {}
    q_map_ui = {}
    for q_idx, row_idx in enumerate([5, 6, 7, 8], start=1):
        for col_offset, yr in enumerate(years):
            val_ut = df_ut.iloc[row_idx, 2 + col_offset]
            val_ui = df_ui.iloc[row_idx, 2 + col_offset]
            if pd.notna(val_ui):
                q_map_ut[(yr, q_idx)] = float(val_ut)
                q_map_ui[(yr, q_idx)] = float(val_ui)

    # Las fechas de publicacion se leen SOLO de fechas_reportes_walmex_verificadas.csv y
    # unicamente las filas con estado == VERIFICADA. No se completan fechas por memoria.
    # La variable solo se activa a partir de la sesion siguiente (t+1) durante 5 sesiones.
    dates_path = OUT_DIR / "fechas_reportes_walmex_verificadas.csv"
    dates_df = pd.read_csv(dates_path)
    dates_df = dates_df[dates_df["estado"] == "VERIFICADA"].copy()
    release_schedule = []
    for _, d in dates_df.iterrows():
        q_txt = str(d["trimestre"])
        release_schedule.append((str(d["fecha_publicacion"]), 2000 + int(q_txt[2:]), int(q_txt[0])))
    release_schedule.sort()

    records = []
    for pub_date, yr, q in release_schedule:
        ui = q_map_ui.get((yr, q), np.nan)
        ut = q_map_ut.get((yr, q), np.nan)
        prev_yr, prev_q = (yr, q - 1) if q > 1 else (yr - 1, 4)
        prev_ui = q_map_ui.get((prev_yr, prev_q), np.nan)
        prev_ut = q_map_ut.get((prev_yr, prev_q), np.nan)
        # Sin valor previo documentado o sin valor del trimestre: la sorpresa queda en NaN, nunca en 0 inventado
        surprise_ui = ui - prev_ui if (pd.notna(ui) and pd.notna(prev_ui)) else np.nan
        surprise_ut = ut - prev_ut if (pd.notna(ut) and pd.notna(prev_ut)) else np.nan
        records.append(
            {
                "fecha_publicacion": pub_date,
                "trimestre": f"{q}T{str(yr)[-2:]}",
                "sss_ui_mex_pct": ui,
                "ut_mex_pct": ut,
                "sorpresa_sss_vs_trim_previo_pp": round(surprise_ui, 2) if pd.notna(surprise_ui) else np.nan,
                "sorpresa_ut_vs_trim_previo_pp": round(surprise_ut, 2) if pd.notna(surprise_ut) else np.nan,
                "signo_sorpresa_regulatoria": (1 if surprise_ui > 0 else (-1 if surprise_ui < 0 else 0)) if pd.notna(surprise_ui) else np.nan,
            }
        )

    return pd.DataFrame(records)


def attach_regulatory_features(merged, reg_df):
    """
    Asigna a cada sesion t:
    - post_rep_5d: 1 en las primeras 5 sesiones posteriores a fecha_publicacion (empezando en t+1, nunca el mismo dia)
    - sorpresa_regulatoria_5d: cambio en puntos porcentuales de Ventas Mismas Tiendas del reporte recien publicado
      durante esas 5 sesiones posteriores (0 fuera de la ventana de 5 sesiones).
    - regimen_sss_vigente: ultimo crecimiento conocido de Ventas Mismas Tiendas publicado hasta t-1.
    """
    fechas = merged["fecha"].astype(str).tolist()
    n = len(fechas)
    post_rep_5d = np.zeros(n, dtype=float)
    sorpresa_5d = np.zeros(n, dtype=float)
    regimen_sss = np.full(n, 7.9, dtype=float)  # valor inicial conocido 4T15/1T16

    pub_dates = reg_df["fecha_publicacion"].astype(str).tolist()
    surprises = reg_df["sorpresa_sss_vs_trim_previo_pp"].to_numpy(dtype=float)
    sss_vals = reg_df["sss_ui_mex_pct"].to_numpy(dtype=float)

    for pub_d, surp, sss in zip(pub_dates, surprises, sss_vals):
        # Primera sesion ESTRICTAMENTE posterior a pub_d (rezago t+1 obligatorio)
        after_indices = [i for i, f in enumerate(fechas) if f > pub_d]
        if not after_indices:
            continue
        start_idx = after_indices[0]
        for k in range(start_idx, min(start_idx + 5, n)):
            post_rep_5d[k] = 1.0
            sorpresa_5d[k] = surp
        for k in range(start_idx, n):
            regimen_sss[k] = sss

    out = merged.copy()
    out["post_rep_5d"] = post_rep_5d
    out["sorpresa_regulatoria_5d"] = sorpresa_5d
    out["regimen_sss_vigente"] = regimen_sss
    return out


# ==============================================================================
# 3. EVALUACION MULTIMODELO SOBRE LOS 4 PERIODOS (495 FECHAS)
# ==============================================================================

def evaluate_all_models_on_495(merged, periodos9e):
    """Modelos 1-7 (exploratorio). Los modelos 8-10 basados en fechas de reportes se retiraron
    el 2026-10-29 porque dependian de fechas sin fuente documentada."""
    results = []

    model_specs = [
        ("1. Regresion Logistica Base (8 vars, muestra original 1,036)", "logreg_base", False),
        ("2. Regresion Logistica + Ajuste Dividendos Desacoplado (1,443 train)", "logreg_div_decoupled", True),
        ("3. Regularizacion Fuerte Ridge L2 (C=0.05) + Ajuste Dividendos", "ridge_strong", True),
        ("4. Regularizacion ElasticNet (L1+L2, C=0.10) + Ajuste Dividendos", "elasticnet", True),
        ("5. Random Forest Balanceado (80 arboles, max_depth=3) + Ajuste Dividendos", "rf_d3", True),
        ("6. Gradient Boosting (GBDT / estilo XGBoost, max_depth=2) + Ajuste Dividendos", "gbdt_d2", True),
        ("7. Red Neuronal MLP (16x8, tanh + Adam + L2) + Ajuste Dividendos", "mlp", True),
    ]

    for label, code, use_adj_train in model_specs:
        all_preds = []
        fold_baccs = []
        folds_beating_base = 0
        base_fold_baccs = [58.73, 53.78, 54.64, 51.91]

        for idx_f, row in periodos9e.iterrows():
            fold = int(row["fold"])
            t_start, t_end = int(row["inicio_train_pos"]), int(row["fin_train_exclusivo_pos"])
            v_start, v_end = int(row["inicio_validacion_pos"]), int(row["fin_validacion_exclusivo_pos"])

            in_tr = (merged["posicion_sesion"] - 20 >= t_start) & (merged["posicion_sesion"] + 5 < t_end)
            in_va = (merged["posicion_sesion"] - 20 >= v_start) & (merged["posicion_sesion"] + 5 < v_end)

            if use_adj_train:
                tr_mask = in_tr & (merged["apto_features_ajustadas"] == True) & (merged["apto_label_h5"] == True)
            else:
                tr_mask = in_tr & (merged["apto_dataset"] == True)
            va_mask = in_va & (merged["apto_dataset"] == True)

            df_tr = merged.loc[tr_mask].copy()
            df_va = merged.loc[va_mask].copy()

            feat_cols = [f"{c}_adj" for c in FEATURES_8]
            if code == "reg_date_only":
                feat_cols = feat_cols + ["post_rep_5d"]
            elif code == "reg_surprise_base":
                feat_cols = feat_cols + ["sorpresa_regulatoria_5d"]

            X_tr = df_tr[feat_cols].to_numpy(dtype=float)
            y_tr = df_tr["y_h5"].to_numpy(dtype=int)
            X_va = df_va[feat_cols].to_numpy(dtype=float)
            y_va = df_va["y_h5"].to_numpy(dtype=int)

            X_tr_s, X_va_s, _, _ = standard_scale(X_tr, X_va)

            if code in ("logreg_base", "logreg_div_decoupled", "reg_date_only", "reg_surprise_base", "reg_surprise_div"):
                coef, intercept = fit_logistic_regression_balanced(X_tr_s, y_tr, C=1.0)
                prob = predict_proba_logistic(X_va_s, coef, intercept)
            elif code == "ridge_strong":
                coef, intercept = fit_logistic_regression_balanced(X_tr_s, y_tr, C=0.05)
                prob = predict_proba_logistic(X_va_s, coef, intercept)
            elif code == "elasticnet":
                coef, intercept = fit_elasticnet_logistic_balanced(X_tr_s, y_tr, C=0.10, l1_ratio=0.5)
                prob = predict_proba_logistic(X_va_s, coef, intercept)
            elif code == "rf_d3":
                prob = fit_predict_random_forest(X_tr_s, y_tr, X_va_s, n_estimators=80, max_depth=3, seed=42 + fold)
            elif code == "gbdt_d2":
                prob = fit_predict_gbdt(X_tr_s, y_tr, X_va_s, n_estimators=50, learning_rate=0.05, max_depth=2, seed=42 + fold)
            elif code == "mlp":
                prob = fit_predict_mlp(X_tr_s, y_tr, X_va_s, hidden=(16, 8), lr=0.008, l2_reg=0.03, epochs=220, seed=42 + fold)
            else:
                raise ValueError(code)

            # Ajuste desacoplado en vispera de ex-dividendo (sin pasar por StandardScaler)
            if use_adj_train:
                tr_div = df_tr[df_tr["ex_div_inminente_5d"] == 1]
                p_div_tr = float(np.mean(tr_div["y_h5"].to_numpy(dtype=float)))
                logit_shift_div = np.log(p_div_tr / (1.0 - p_div_tr))
                prob_c = np.clip(prob, 1e-6, 1.0 - 1e-6)
                z_va = np.log(prob_c / (1.0 - prob_c))
                z_va = z_va + np.where(df_va["ex_div_inminente_5d"].to_numpy(int) == 1, logit_shift_div, 0.0)

                if code == "reg_surprise_div":
                    # Ajuste desacoplado de sorpresa regulatoria en las 5 sesiones post-reporte (t+1..t+5)
                    # En train, calcular log-odds en post_rep_5d cuando sorpresa > 0 vs sorpresa < 0
                    tr_pos = df_tr[(df_tr["post_rep_5d"] == 1) & (df_tr["sorpresa_regulatoria_5d"] > 0)]
                    tr_neg = df_tr[(df_tr["post_rep_5d"] == 1) & (df_tr["sorpresa_regulatoria_5d"] < 0)]
                    p_pos = float(np.mean(tr_pos["y_h5"])) if len(tr_pos) > 5 else 0.5
                    p_neg = float(np.mean(tr_neg["y_h5"])) if len(tr_neg) > 5 else 0.5
                    shift_pos = 0.5 * np.log(np.clip(p_pos, 0.1, 0.9) / (1.0 - np.clip(p_pos, 0.1, 0.9)))
                    shift_neg = 0.5 * np.log(np.clip(p_neg, 0.1, 0.9) / (1.0 - np.clip(p_neg, 0.1, 0.9)))
                    surp_va = df_va["sorpresa_regulatoria_5d"].to_numpy(float)
                    post_va = df_va["post_rep_5d"].to_numpy(int)
                    z_va = z_va + np.where((post_va == 1) & (surp_va > 0), shift_pos, 0.0)
                    z_va = z_va + np.where((post_va == 1) & (surp_va < 0), shift_neg, 0.0)

                prob = 1.0 / (1.0 + np.exp(-np.clip(z_va, -50, 50)))

            pred = (prob >= 0.5).astype(int)
            fold_df = pd.DataFrame(
                {
                    "fold": fold,
                    "fecha": df_va["fecha"].values,
                    "posicion_sesion": df_va["posicion_sesion"].values,
                    "y_real": y_va,
                    "y_predicho": pred,
                    "prob_alza": prob,
                    "retorno_futuro_h5": df_va["retorno_futuro_h5"].values,
                }
            )
            fm = evaluate_predictions(fold_df)
            fold_baccs.append(fm["balanced_accuracy_pct"])
            if fm["balanced_accuracy_pct"] > base_fold_baccs[idx_f]:
                folds_beating_base += 1
            all_preds.append(fold_df)

        full_df = pd.concat(all_preds, ignore_index=True)
        gm = evaluate_predictions(full_df)
        gm["modelo"] = label
        gm["codigo"] = code
        gm["mean_fold_bacc_pct"] = round(float(np.mean(fold_baccs)), 2)
        gm["fold_baccs"] = fold_baccs
        gm["periodos_que_superan_base"] = folds_beating_base
        results.append(gm)

    return results


# ==============================================================================
# 4. SCRAPING EN VIVO DE BOLETINES REGULATORIOS BMV Y NOTICIAS PROSPECTIVAS (2026-2027)
# ==============================================================================

POSITIVE_TERMS = [
    "crecimiento", "incremento", "sube", "alza", "ganancia", "expansión", "expansion",
    "dividendo", "supera", "récord", "record", "sólido", "solido", "positivo", "apertura",
    "inversión", "inversion", "lidera", "compra", "favorable", "utilidad",
]
NEGATIVE_TERMS = [
    "caída", "caida", "cayó", "cayo", "cae", "caen", "baja", "retroceso",
    "pérdida", "perdida", "multa", "cofece", "investigación", "investigacion",
    "presión", "presion", "débil", "debil", "inflación", "inflacion",
    "desaceleración", "desaceleracion", "riesgo", "recorte", "negativo",
    "mayores gastos", "mayores costos", "costos",
]


def score_financial_text_lexical(text):
    t_low = text.lower()
    pos_hits = sum(1 for w in POSITIVE_TERMS if w in t_low)
    neg_hits = sum(1 for w in NEGATIVE_TERMS if w in t_low)
    total = pos_hits + neg_hits
    score = (pos_hits - neg_hits) / total if total > 0 else 0.0
    return pos_hits, neg_hits, round(score, 4)


def run_live_regulatory_and_news_scraper():
    """
    Ejecuta scraping real en vivo (con sello SHA-256 y control de horario de corte 15:00 CDMX)
    sobre:
    1) Eventos Relevantes oficiales de WALMEX en BMV
    2) Informacion Financiera / Reportes Trimestrales oficiales de WALMEX en BMV
    3) Boletin diario de mercado BMV
    4) Canal RSS publico de noticias financieras de WALMEX (para seguimiento prospectivo 2026-2027)
    """
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PrismaBMV-Audit/1.0"}

    sources = [
        (
            "BMV_EVENTOS_RELEVANTES_OFICIAL",
            "https://www.bmv.com.mx/es/emisoras/eventosrelevantes/WALMEX-6153-CGEN_CAPIT",
        ),
        (
            "BMV_INFO_FINANCIERA_OFICIAL",
            "https://www.bmv.com.mx/es/emisoras/informacionfinanciera/WALMEX-6153-CGEN_CAPIT",
        ),
        (
            "BMV_PERFIL_EMISORA_OFICIAL",
            "https://www.bmv.com.mx/es/emisoras/perfil/WALMEX-6153",
        ),
        (
            "GOOGLE_NEWS_RSS_PROSPECTIVO_WALMEX",
            "https://news.google.com/rss/search?q=WALMEX+OR+%22Walmart+de+Mexico%22&hl=es-419&gl=MX&ceid=MX:es-419",
        ),
    ]

    audit_evidence = []
    scraped_items = []

    for src_name, url in sources:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw_bytes = resp.read()
                status_code = resp.status
            sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
            text_body = raw_bytes.decode("utf-8", errors="ignore")

            doc_links = re.findall(r"/docs-pub/[^\"'\s<>]+", text_body)

            audit_evidence.append(
                {
                    "fuente": src_name,
                    "url": url,
                    "timestamp_captura_utc": now_iso,
                    "http_status": status_code,
                    "bytes_descargados": len(raw_bytes),
                    "sha256_payload": sha256_hash,
                    "documentos_oficiales_detectados": len(doc_links),
                    "muestra_documentos": doc_links[:8],
                }
            )

            if src_name == "GOOGLE_NEWS_RSS_PROSPECTIVO_WALMEX":
                root = ET.fromstring(raw_bytes)
                for item in root.findall(".//item")[:20]:
                    title = item.findtext("title") or ""
                    pub_date = item.findtext("pubDate") or ""
                    link = item.findtext("link") or ""
                    source_tag = item.find("source")
                    publisher = source_tag.text if source_tag is not None else "Desconocido"
                    item_hash = hashlib.sha256(f"{title}|{pub_date}|{link}".encode("utf-8")).hexdigest()
                    pos_h, neg_h, sent_score = score_financial_text_lexical(title)
                    scraped_items.append(
                        {
                            "tipo_fuente": "NOTICIA_PROSPECTIVA_TIEMPO_REAL",
                            "medio_o_emisor": publisher,
                            "fecha_publicacion_declarada": pub_date,
                            "timestamp_captura_utc": now_iso,
                            "titular_o_evento": title,
                            "url": link,
                            "sha256_item": item_hash,
                            "palabras_positivas": pos_h,
                            "palabras_negativas": neg_h,
                            "puntaje_lexico": sent_score,
                            "regla_uso_temporal": "SOLO_SEGUIMIENTO_PROSPECTIVO_DESDE_SIGUIENTE_CORTE_15H_CDMX",
                        }
                    )
            else:
                for dlink in dict.fromkeys(doc_links[:10]):
                    full_doc_url = f"https://www.bmv.com.mx{dlink}"
                    item_hash = hashlib.sha256(full_doc_url.encode("utf-8")).hexdigest()
                    scraped_items.append(
                        {
                            "tipo_fuente": src_name,
                            "medio_o_emisor": "Bolsa Mexicana de Valores (EMISNET / Docs-Pub)",
                            "fecha_publicacion_declarada": "DOCUMENTO_REGULATORIO_BMV",
                            "timestamp_captura_utc": now_iso,
                            "titular_o_evento": dlink.split("/")[-1],
                            "url": full_doc_url,
                            "sha256_item": item_hash,
                            "palabras_positivas": 0,
                            "palabras_negativas": 0,
                            "puntaje_lexico": 0.0,
                            "regla_uso_temporal": "APLICAR_EN_SESION_T_MAS_1_TRAS_PUBLICACION",
                        }
                    )
        except Exception as exc:
            audit_evidence.append(
                {
                    "fuente": src_name,
                    "url": url,
                    "timestamp_captura_utc": now_iso,
                    "error": str(exc),
                }
            )

    df_items = pd.DataFrame(scraped_items)
    df_items.to_csv(OUT_DIR / "bitacora_noticias_boletines_prospectiva.csv", index=False, encoding="utf-8-sig")
    with open(OUT_DIR / "evidencia_scraping_20261028.json", "w", encoding="utf-8") as f:
        json.dump(audit_evidence, f, indent=2, ensure_ascii=False)

    return audit_evidence, df_items


def main():
    s9d, el9d, divs9d, periodos9e, pred9e, coefs9e, pred9f, s9g, sel9g, pred9g, divs9g = load_data()
    div_map = dict(zip(divs9d["fecha_ex"].astype(str), divs9d["dividendo_documentado"].astype(float)))
    for _, r in divs9g.iterrows():
        div_map[str(r["fecha_ex"])] = float(r["dividendo_documentado"])

    merged = build_adjusted_features_and_indicator(s9d, el9d, div_map)
    reg_df = load_official_quarterly_regulatory_data()
    reg_df.to_csv(OUT_DIR / "boletines_trimestrales_walmex_oficiales.csv", index=False, encoding="utf-8-sig")

    merged = attach_regulatory_features(merged, reg_df)

    print("\n=== EJECUTANDO COMPARATIVA DE ALGORITMOS DE IA/ML Y BOLETINES REGULATORIOS (495 FECHAS) ===")
    results = evaluate_all_models_on_495(merged, periodos9e)
    pd.DataFrame(results).to_csv(OUT_DIR / "comparativa_algoritmos_y_boletines.csv", index=False, encoding="utf-8-sig")

    for r in results:
        print(f"\n>> {r['modelo']}")
        print(
            f"   Aciertos: {r['aciertos']}/{r['n']} ({r['accuracy_pct']}%) | "
            f"Exactitud bal. agrupada: {r['balanced_accuracy_pct']}% | "
            f"Exactitud bal. media (4 periodos): {r['mean_fold_bacc_pct']}%"
        )
        print(
            f"   Log loss: {r['log_loss']} | Brier: {r['brier']} | "
            f"TN={r['TN']}, FP={r['FP']} (caidas>=2%: {r['FP_caida_ge_2pct']}), FN={r['FN']}, TP={r['TP']}"
        )
        print(
            f"   Exactitud bal. por periodo: {r['fold_baccs']} "
            f"(Supera al base en {r['periodos_que_superan_base']}/4 periodos)"
        )

    print("\n=== EJECUTANDO SCRAPER EN VIVO DE BOLETINES BMV Y NOTICIAS PROSPECTIVAS (2026-10-28) ===")
    evidence, df_items = run_live_regulatory_and_news_scraper()
    for ev in evidence:
        print(
            f" - Fuente: {ev['fuente']} | Status: {ev.get('http_status', 'ERR')} | "
            f"Bytes: {ev.get('bytes_descargados', 0)} | SHA256: {ev.get('sha256_payload', '')[:16]}... | "
            f"Docs detectados: {ev.get('documentos_oficiales_detectados', 0)}"
        )
    print(f"Total registros guardados en bitacora prospectiva: {len(df_items)}")
    if len(df_items) > 0:
        news_only = df_items[df_items["tipo_fuente"] == "NOTICIA_PROSPECTIVA_TIEMPO_REAL"]
        print(f"Noticias en tiempo real capturadas hoy: {len(news_only)}")
        for _, nrow in news_only.head(8).iterrows():
            print(
                f"   * [{nrow['fecha_publicacion_declarada']}] ({nrow['medio_o_emisor']}) "
                f"Score={nrow['puntaje_lexico']}: {nrow['titular_o_evento'][:95]}"
            )


if __name__ == "__main__":
    main()
