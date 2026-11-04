"""
investigacion_profunda_gmexico.py
==================================
Estudio profundo de modelado cuantitativo sobre Grupo Mexico (GMEXICO B)
utilizando la serie oficial reconstruida de PPP estricto de la BMV (2016-2026).

Objetivos cientificos:
1. Evaluar las caracteristicas de distribucion y correlacion de las 8 variables canonicas.
2. Comparar 7 algoritmos en el Test historico, con etiquetas dentro del corte:
   - M1: Regresion Logistica Balanceada (C=1.0)
   - M2: Regresion Logistica ElasticNet (ISTA sparse)
   - M3: Arbol de Decision Restringido (d=3)
   - M4: Random Forest (60 arboles, d=3, bootstrap, feature subsampling)
   - M5: Gradient Boosted Trees (GBDT, 40 arboles, lr=0.05, d=2)
   - M6: Red Neuronal MLP (1 capa oculta de 8 neuronas, ReLU, L2=0.01)
   - M7: Dummy Prior (Linea base de referencia)
3. Recalcular retrospectivamente el corte del 28 de octubre de 2026.
   Este reporte no emite ni reemplaza las senales prospectivas originales.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
from metodologia_ppp import (
    FEATURE_NAMES, VERSION_FEATURES, VERSION_METODOLOGIA, seleccionar_train_test,
    add_bmv_sessions, timestamp_utc,
)

WORKSPACE = Path(r"D:\Universidad\7mo Semestre\Big Data\Proyecto final")
INPUT_FEATURES_CSV = WORKSPACE / "dataset_panel_15_emisoras_features.csv"
OUTPUT_REPORTE_JSON = WORKSPACE / "reporte_investigacion_profunda_gmexico.json"


# =====================================================================
# 1. Implementaciones de Modelos en NumPy Puro (Sin dependencias externas)
# =====================================================================

def fit_predict_logistic(X_tr, y_tr, X_ev, C=1.0, balanced=True):
    """Regresion Logistica balanceada con regularizacion L2 via Newton-Raphson IRLS."""
    n_samples, n_feats = X_tr.shape
    y_tr = y_tr.astype(float)

    if balanced:
        n_0 = np.sum(y_tr == 0)
        n_1 = np.sum(y_tr == 1)
        w_0 = n_samples / (2.0 * n_0) if n_0 > 0 else 1.0
        w_1 = n_samples / (2.0 * n_1) if n_1 > 0 else 1.0
        sw = np.where(y_tr == 1, w_1, w_0)
    else:
        sw = np.ones(n_samples)

    mu = np.mean(X_tr, axis=0)
    sig = np.std(X_tr, axis=0)
    sig[sig == 0] = 1.0

    X_tr_s = (X_tr - mu) / sig
    X_ev_s = (X_ev - mu) / sig

    X_tr_aug = np.column_stack([np.ones(n_samples), X_tr_s])
    X_ev_aug = np.column_stack([np.ones(len(X_ev_s)), X_ev_s])

    beta = np.zeros(n_feats + 1)
    lambda_val = 1.0 / C

    for _ in range(50):
        logits = np.clip(X_tr_aug @ beta, -35.0, 35.0)
        p = 1.0 / (1.0 + np.exp(-logits))
        W_diag = np.maximum(sw * p * (1.0 - p), 1e-12)

        grad = X_tr_aug.T @ (sw * (p - y_tr))
        grad[1:] += lambda_val * beta[1:]

        H = X_tr_aug.T @ (W_diag[:, None] * X_tr_aug)
        diag_idx = np.diag_indices(len(beta))
        H[diag_idx[0][1:], diag_idx[1][1:]] += lambda_val

        try:
            d = np.linalg.solve(H + 1e-8 * np.eye(len(beta)), grad)
        except np.linalg.LinAlgError:
            break
        beta -= d
        if np.max(np.abs(d)) < 1e-7:
            break

    ev_logits = np.clip(X_ev_aug @ beta, -35.0, 35.0)
    probs = 1.0 / (1.0 + np.exp(-ev_logits))
    return probs, beta


def fit_predict_elasticnet(X_tr, y_tr, X_ev, C=1.0, l1_ratio=0.5, max_iter=20000, lr=1.0):
    """Regresion Logistica ElasticNet via Descenso Proximal (ISTA / FISTA)."""
    n_samples, n_feats = X_tr.shape
    y_tr = y_tr.astype(float)

    n_0 = np.sum(y_tr == 0)
    n_1 = np.sum(y_tr == 1)
    w_0 = n_samples / (2.0 * n_0) if n_0 > 0 else 1.0
    w_1 = n_samples / (2.0 * n_1) if n_1 > 0 else 1.0
    sw = np.where(y_tr == 1, w_1, w_0)

    mu = np.mean(X_tr, axis=0)
    sig = np.std(X_tr, axis=0)
    sig[sig == 0] = 1.0

    X_tr_s = (X_tr - mu) / sig
    X_ev_s = (X_ev - mu) / sig

    X_tr_aug = np.column_stack([np.ones(n_samples), X_tr_s])
    X_ev_aug = np.column_stack([np.ones(len(X_ev_s)), X_ev_s])

    beta = np.zeros(n_feats + 1)
    # La perdida esta promediada; equivale a sum(loss) + penalizacion/C.
    if C <= 0 or not 0 <= l1_ratio <= 1:
        raise ValueError("C debe ser positivo y l1_ratio debe estar entre 0 y 1")
    lambda_val = 1.0 / (C * n_samples)
    l1_pen = lambda_val * l1_ratio
    l2_pen = lambda_val * (1.0 - l1_ratio)

    lip = 0.25 * np.linalg.norm(np.sqrt(sw)[:, None] * X_tr_aug, ord=2) ** 2 / n_samples + l2_pen
    step = min(lr, 1.0 / lip)
    z, accel = beta.copy(), 1.0
    for _ in range(max_iter):
        p = 1.0 / (1.0 + np.exp(-np.clip(X_tr_aug @ z, -35.0, 35.0)))
        grad = (X_tr_aug.T @ (sw * (p - y_tr))) / n_samples
        grad[1:] += l2_pen * z[1:]
        updated = z - step * grad
        updated[1:] = np.sign(updated[1:]) * np.maximum(np.abs(updated[1:]) - step * l1_pen, 0.0)
        accel_new = (1 + np.sqrt(1 + 4 * accel ** 2)) / 2
        z = updated + (accel - 1) / accel_new * (updated - beta)
        beta, accel = updated, accel_new
        # Residuo proximal (KKT) en el iterado, no solo cambio entre pasos acelerados.
        pp = 1 / (1 + np.exp(-np.clip(X_tr_aug @ beta, -35, 35)))
        gg = X_tr_aug.T @ (sw * (pp - y_tr)) / n_samples
        gg[1:] += l2_pen * beta[1:]
        prox = beta - step * gg
        prox[1:] = np.sign(prox[1:]) * np.maximum(np.abs(prox[1:]) - step * l1_pen, 0)
        if np.max(np.abs(beta - prox)) / step < 1e-7:
            break
    else:
        raise RuntimeError("ElasticNet no alcanzo la tolerancia KKT; no se publican metricas sin convergencia")

    ev_logits = np.clip(X_ev_aug @ beta, -35.0, 35.0)
    probs = 1.0 / (1.0 + np.exp(-ev_logits))
    return probs, beta


class PureNumPyDecisionTree:
    """Arbol de clasificacion binario optimizado para baja profundidad."""
    def __init__(self, max_depth=3, min_samples_leaf=20, max_features=None, random_state=42):
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.rng = np.random.RandomState(random_state)
        self.tree = None

    def _gini(self, y):
        n = len(y)
        if n == 0:
            return 0.0
        p1 = np.mean(y)
        return 2.0 * p1 * (1.0 - p1)

    def _best_split(self, X, y):
        n_samples, n_features = X.shape
        if n_samples < 2 * self.min_samples_leaf:
            return None

        current_gini = self._gini(y)
        best_gain = 0.0
        best_split = None

        feature_indices = np.arange(n_features)
        if self.max_features and self.max_features < n_features:
            feature_indices = self.rng.choice(n_features, self.max_features, replace=False)

        for feat in feature_indices:
            vals = np.unique(X[:, feat])
            if len(vals) < 2:
                continue
            thresholds = (vals[:-1] + vals[1:]) / 2.0
            if len(thresholds) > 15:
                thresholds = np.percentile(thresholds, np.linspace(5, 95, 15))

            for t in thresholds:
                left_mask = X[:, feat] <= t
                right_mask = ~left_mask
                n_l, n_r = np.sum(left_mask), np.sum(right_mask)
                if n_l < self.min_samples_leaf or n_r < self.min_samples_leaf:
                    continue

                gini_l = self._gini(y[left_mask])
                gini_r = self._gini(y[right_mask])
                gain = current_gini - (n_l / n_samples * gini_l + n_r / n_samples * gini_r)

                if gain > best_gain:
                    best_gain = gain
                    best_split = {"feat": feat, "threshold": t}

        return best_split

    def _build_tree(self, X, y, depth=0):
        p_leaf = float(np.mean(y)) if len(y) > 0 else 0.5
        if depth >= self.max_depth or len(y) < 2 * self.min_samples_leaf:
            return {"leaf": True, "prob": p_leaf}

        split = self._best_split(X, y)
        if split is None:
            return {"leaf": True, "prob": p_leaf}

        feat, t = split["feat"], split["threshold"]
        left_mask = X[:, feat] <= t
        right_mask = ~left_mask

        left_child = self._build_tree(X[left_mask], y[left_mask], depth + 1)
        right_child = self._build_tree(X[right_mask], y[right_mask], depth + 1)

        return {"leaf": False, "feat": feat, "threshold": t, "left": left_child, "right": right_child, "prob": p_leaf}

    def fit(self, X, y):
        self.tree = self._build_tree(X, y, depth=0)
        return self

    def _predict_row(self, row, node):
        if node["leaf"]:
            return node["prob"]
        if row[node["feat"]] <= node["threshold"]:
            return self._predict_row(row, node["left"])
        else:
            return self._predict_row(row, node["right"])

    def predict_proba(self, X):
        return np.array([self._predict_row(row, self.tree) for row in X])


class PureNumPyRandomForest:
    """Random Forest binario con ensamble de arboles con bootstrap."""
    def __init__(self, n_estimators=60, max_depth=3, min_samples_leaf=15, max_features=None, random_state=42):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.random_state = random_state
        self.trees = []

    def fit(self, X, y):
        rng = np.random.RandomState(self.random_state)
        n_samples, n_feats = X.shape
        max_f = self.max_features or int(np.sqrt(n_feats))
        self.trees = []

        for i in range(self.n_estimators):
            idx = rng.choice(n_samples, n_samples, replace=True)
            X_b, y_b = X[idx], y[idx]
            dt = PureNumPyDecisionTree(
                max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf,
                max_features=max_f,
                random_state=rng.randint(0, 100000),
            )
            dt.fit(X_b, y_b)
            self.trees.append(dt)
        return self

    def predict_proba(self, X):
        preds = np.column_stack([dt.predict_proba(X) for dt in self.trees])
        return np.mean(preds, axis=1)


class PureNumPyRegressionTree(PureNumPyDecisionTree):
    """Arbol de minimos cuadrados para ajustar residuos reales, incluso negativos."""
    def _gini(self, y):
        return float(np.var(y)) if len(y) else 0.0

    def predict(self, X):
        return super().predict_proba(X)


class PureNumPyGBDT:
    """Gradient Boosted Decision Trees para clasificacion logistica binaria."""
    def __init__(self, n_estimators=40, learning_rate=0.05, max_depth=2, random_state=42):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.random_state = random_state
        self.trees = []
        self.base_logit = 0.0

    def fit(self, X, y):
        n_samples = len(y)
        p_prior = np.mean(y)
        p_prior = np.clip(p_prior, 1e-4, 1.0 - 1e-4)
        self.base_logit = np.log(p_prior / (1.0 - p_prior))
        F_m = np.full(n_samples, self.base_logit)
        rng = np.random.RandomState(self.random_state)

        self.trees = []
        for i in range(self.n_estimators):
            p = 1.0 / (1.0 + np.exp(-np.clip(F_m, -35.0, 35.0)))
            residuals = y - p
            # Entrenar arbol regresor en residuos
            dt = PureNumPyRegressionTree(max_depth=self.max_depth, min_samples_leaf=15, random_state=rng.randint(0, 100000))
            dt.fit(X, residuals)
            step_pred = dt.predict(X)
            F_m += self.learning_rate * step_pred
            self.trees.append(dt)
        return self

    def predict_proba(self, X):
        F_m = np.full(len(X), self.base_logit)
        for dt in self.trees:
            step_pred = dt.predict(X)
            F_m += self.learning_rate * step_pred
        return 1.0 / (1.0 + np.exp(-np.clip(F_m, -35.0, 35.0)))


def fit_predict_mlp(X_tr, y_tr, X_ev, hidden_units=8, l2=0.01, epochs=300, lr=0.03, random_state=42):
    """Perceptron Multicapa (MLP) con 1 capa oculta, activacion ReLU y regularizacion L2."""
    rng = np.random.RandomState(random_state)
    n_samples, n_feats = X_tr.shape

    mu = np.mean(X_tr, axis=0)
    sig = np.std(X_tr, axis=0)
    sig[sig == 0] = 1.0
    X_tr_s = (X_tr - mu) / sig
    X_ev_s = (X_ev - mu) / sig

    # Inicializacion He
    W1 = rng.randn(n_feats, hidden_units) * np.sqrt(2.0 / n_feats)
    b1 = np.zeros(hidden_units)
    W2 = rng.randn(hidden_units, 1) * np.sqrt(2.0 / hidden_units)
    b2 = np.zeros(1)

    y_2d = y_tr[:, None]

    for epoch in range(epochs):
        # Forward pass
        Z1 = X_tr_s @ W1 + b1
        A1 = np.maximum(0, Z1)  # ReLU
        Z2 = A1 @ W2 + b2
        P = 1.0 / (1.0 + np.exp(-np.clip(Z2, -35.0, 35.0)))

        # Backward pass
        dZ2 = (P - y_2d) / n_samples
        dW2 = A1.T @ dZ2 + l2 * W2
        db2 = np.sum(dZ2, axis=0)

        dA1 = dZ2 @ W2.T
        dZ1 = dA1 * (Z1 > 0)
        dW1 = X_tr_s.T @ dZ1 + l2 * W1
        db1 = np.sum(dZ1, axis=0)

        W1 -= lr * dW1
        b1 -= lr * db1
        W2 -= lr * dW2
        b2 -= lr * db2

    # Inferencia en Test
    Z1_ev = X_ev_s @ W1 + b1
    A1_ev = np.maximum(0, Z1_ev)
    Z2_ev = A1_ev @ W2 + b2
    probs = 1.0 / (1.0 + np.exp(-np.clip(Z2_ev, -35.0, 35.0))).flatten()
    return probs


def compute_metrics(y_true, probs, p_prior_train):
    """Calcula el conjunto completo de metricas de validacion cuantitativa."""
    y = y_true.astype(float)
    preds = (probs >= 0.5).astype(int)

    brier = float(np.mean((probs - y) ** 2))
    brier_dummy = float(np.mean((p_prior_train - y) ** 2))

    eps = 1e-15
    p_clip = np.clip(probs, eps, 1.0 - eps)
    log_loss = float(-np.mean(y * np.log(p_clip) + (1.0 - y) * np.log(1.0 - p_clip)))

    acc = float(np.mean(preds == y))

    tpr = np.mean(preds[y == 1] == 1) if np.sum(y == 1) > 0 else 0.0
    tnr = np.mean(preds[y == 0] == 0) if np.sum(y == 0) > 0 else 0.0
    bal_acc = float((tpr + tnr) / 2.0)

    # ROC AUC simple exacto
    pos_probs = probs[y == 1]
    neg_probs = probs[y == 0]
    if len(pos_probs) > 0 and len(neg_probs) > 0:
        matches = np.sum(pos_probs[:, None] > neg_probs[None, :]) + 0.5 * np.sum(pos_probs[:, None] == neg_probs[None, :])
        auc = float(matches / (len(pos_probs) * len(neg_probs)))
    else:
        auc = 0.5

    return {
        "brier_score": round(brier, 6),
        "brier_dummy": round(brier_dummy, 6),
        "supera_dummy_brier": bool(brier < brier_dummy),
        "log_loss": round(log_loss, 6),
        "accuracy": round(acc * 100.0, 2),
        "balanced_accuracy": round(bal_acc * 100.0, 2),
        "roc_auc": round(auc, 4),
        "tasa_predicha_positiva": round(float(np.mean(preds)) * 100.0, 2),
    }


def main():
    print("=" * 70)
    print("ESTUDIO PROFUNDO DE MODELADO - GRUPO MEXICO (GMEXICO B)")
    print("=" * 70)

    df_feats = pd.read_csv(INPUT_FEATURES_CSV)
    gm = df_feats[df_feats["emisora"] == "GMEXICO"].sort_values("posicion_sesion").reset_index(drop=True)

    print(f"Total registros continuos de GMEXICO: {len(gm)}")
    if "version_features" not in gm or not gm.version_features.eq(VERSION_FEATURES).all():
        raise ValueError("Regenera primero el panel con las variables canonicas v2")
    train_df, test_df = seleccionar_train_test(gm)

    X_train = train_df[FEATURE_NAMES].to_numpy(dtype=float)
    y_train = train_df["target_y"].to_numpy(dtype=float)

    X_test = test_df[FEATURE_NAMES].to_numpy(dtype=float)
    y_test = test_df["target_y"].to_numpy(dtype=float)

    p_prior = float(np.mean(y_train))
    print(f"Muestra Train: {len(train_df)} sesiones (Tasa subida: {p_prior * 100.0:.2f}%)")
    print(f"Muestra Test:  {len(test_df)} sesiones (Tasa subida: {np.mean(y_test) * 100.0:.2f}%)")

    # 1. Correlaciones con el objetivo
    print("\n" + "=" * 70)
    print("ANALISIS DE SENAL: CORRELACION LINEAL CON Y_t = I(PPP_{t+5} > PPP_t)")
    print("=" * 70)
    corrs = {}
    for f in FEATURE_NAMES:
        c = float(np.corrcoef(train_df[f], y_train)[0, 1])
        corrs[f] = c
        print(f"* {f}: {c:+.4f}")

    # 2. Entrenar y evaluar los 7 algoritmos
    print("\n" + "=" * 70)
    print("EVALUACION EXPLORATORIA DE LOS 7 ALGORITMOS EN TEST HISTORICO")
    print("=" * 70)

    models_eval = {}

    # M1: Regresion Logistica Balanceada (C=1.0)
    p_logreg, beta_logreg = fit_predict_logistic(X_train, y_train, X_test, C=1.0, balanced=True)
    models_eval["M1_Regresion_Logistica_Balanceada"] = compute_metrics(y_test, p_logreg, p_prior)

    # M2: Regresion Logistica ElasticNet (L1/L2)
    p_enet, beta_enet = fit_predict_elasticnet(X_train, y_train, X_test, C=0.5, l1_ratio=0.5)
    models_eval["M2_ElasticNet_Logistica"] = compute_metrics(y_test, p_enet, p_prior)

    # M3: Arbol de Decision (d=3)
    dt = PureNumPyDecisionTree(max_depth=3, min_samples_leaf=20, random_state=2026)
    dt.fit(X_train, y_train)
    p_dt = dt.predict_proba(X_test)
    models_eval["M3_Arbol_Decision_d3"] = compute_metrics(y_test, p_dt, p_prior)

    # M4: Random Forest (60 arboles, d=3)
    rf = PureNumPyRandomForest(n_estimators=60, max_depth=3, min_samples_leaf=15, random_state=2026)
    rf.fit(X_train, y_train)
    p_rf = rf.predict_proba(X_test)
    models_eval["M4_Random_Forest_60_arboles"] = compute_metrics(y_test, p_rf, p_prior)

    # M5: GBDT (40 arboles, lr=0.05, d=2)
    gbdt = PureNumPyGBDT(n_estimators=40, learning_rate=0.05, max_depth=2, random_state=2026)
    gbdt.fit(X_train, y_train)
    p_gbdt = gbdt.predict_proba(X_test)
    models_eval["M5_Gradient_Boosting_GBDT"] = compute_metrics(y_test, p_gbdt, p_prior)

    # M6: MLP Red Neuronal (8 neuronas, L2=0.01)
    p_mlp = fit_predict_mlp(X_train, y_train, X_test, hidden_units=8, l2=0.01, epochs=350, lr=0.03, random_state=2026)
    models_eval["M6_Red_Neuronal_MLP"] = compute_metrics(y_test, p_mlp, p_prior)

    # M7: Dummy Prior
    p_dummy = np.full(len(y_test), p_prior)
    models_eval["M7_Dummy_Prior_Referencia"] = compute_metrics(y_test, p_dummy, p_prior)

    # Imprimir resultados en lista vertical
    for m_name, m_res in models_eval.items():
        print(f"\n* Modelo: {m_name}")
        print(f"    - Brier Score: {m_res['brier_score']} (Supera Dummy: {m_res['supera_dummy_brier']})")
        print(f"    - Log Loss: {m_res['log_loss']}")
        print(f"    - Balanced Accuracy: {m_res['balanced_accuracy']}%")
        print(f"    - Accuracy: {m_res['accuracy']}%")
        print(f"    - ROC AUC: {m_res['roc_auc']}")
        print(f"    - Tasa de Seleccion Positiva: {m_res['tasa_predicha_positiva']}%")

    # 3. Recalculo retrospectivo, separado del registro de emisiones originales.
    print("\n" + "=" * 70)
    print("RECALCULO RETROACTIVO GMEXICO - CORTE 28 DE OCTUBRE DE 2026")
    print("=" * 70)

    prospective_row = gm[gm["fecha"] == "2026-10-28"]
    if prospective_row.empty:
        raise ValueError("No existe ventana elegible para el corte solicitado; no se sustituye por otra fecha")

    X_today = prospective_row[FEATURE_NAMES].to_numpy(dtype=float)
    p_today = float(prospective_row["ppp_t"].iloc[0])
    fecha_hoy = str(prospective_row["fecha"].iloc[0])

    print(f"Fecha de senal: {fecha_hoy} | PPP oficial: ${p_today:.2f} MXN")
    print("Variables calculadas al cierre del 28 de octubre:")
    for f in FEATURE_NAMES:
        print(f"  * {f}: {float(prospective_row[f].iloc[0]):+.4f}")

    # Evaluar senales con cada modelo entrenado
    prob_m1, _ = fit_predict_logistic(X_train, y_train, X_today, C=1.0, balanced=True)
    prob_m2, _ = fit_predict_elasticnet(X_train, y_train, X_today, C=0.5, l1_ratio=0.5)
    prob_m3 = dt.predict_proba(X_today)
    prob_m4 = rf.predict_proba(X_today)
    prob_m5 = gbdt.predict_proba(X_today)
    prob_m6 = fit_predict_mlp(X_train, y_train, X_today, hidden_units=8, l2=0.01, epochs=350, lr=0.03, random_state=2026)

    prob_m1_val = float(prob_m1[0])
    prob_m2_val = float(prob_m2[0])
    prob_m3_val = float(prob_m3[0])
    prob_m4_val = float(prob_m4[0])
    prob_m5_val = float(prob_m5[0])
    prob_m6_val = float(prob_m6[0])

    # Promedio fijo exploratorio; no se seleccionan ganadores mirando Test.
    prob_ensamble = float(np.mean([prob_m1_val, prob_m4_val, prob_m5_val]))

    senales_gmexico = {
        "fecha_senal": fecha_hoy,
        "fecha_objetivo_h5": add_bmv_sessions(fecha_hoy, 5),
        "naturaleza_resultado": "RECALCULO_RETROACTIVO_NO_ES_SENAL_EMITIDA",
        "ppp_senal_mxn": p_today,
        "M1_Regresion_Logistica_Balanceada": {
            "probabilidad_subida": round(prob_m1_val, 4),
            "clase_predicha": "SUBIDA" if prob_m1_val >= 0.5 else "NO_SUBIDA",
        },
        "M2_ElasticNet": {
            "probabilidad_subida": round(prob_m2_val, 4),
            "clase_predicha": "SUBIDA" if prob_m2_val >= 0.5 else "NO_SUBIDA",
        },
        "M3_Arbol_Decision": {
            "probabilidad_subida": round(prob_m3_val, 4),
            "clase_predicha": "SUBIDA" if prob_m3_val >= 0.5 else "NO_SUBIDA",
        },
        "M4_Random_Forest": {
            "probabilidad_subida": round(prob_m4_val, 4),
            "clase_predicha": "SUBIDA" if prob_m4_val >= 0.5 else "NO_SUBIDA",
        },
        "M5_GBDT": {
            "probabilidad_subida": round(prob_m5_val, 4),
            "clase_predicha": "SUBIDA" if prob_m5_val >= 0.5 else "NO_SUBIDA",
        },
        "M6_MLP": {
            "probabilidad_subida": round(prob_m6_val, 4),
            "clase_predicha": "SUBIDA" if prob_m6_val >= 0.5 else "NO_SUBIDA",
        },
        "Ensamble_Promedio_Fijo_Exploratorio": {
            "probabilidad_subida": round(prob_ensamble, 4),
            "clase_predicha": "SUBIDA" if prob_ensamble >= 0.5 else "NO_SUBIDA",
        },
    }

    print("\nPredicciones del modelo para el 5 de noviembre de 2026:")
    print(f"* M1 Regresion Logistica: {prob_m1_val * 100.0:.2f}% -> {senales_gmexico['M1_Regresion_Logistica_Balanceada']['clase_predicha']}")
    print(f"* M2 ElasticNet:          {prob_m2_val * 100.0:.2f}% -> {senales_gmexico['M2_ElasticNet']['clase_predicha']}")
    print(f"* M3 Arbol Decision:     {prob_m3_val * 100.0:.2f}% -> {senales_gmexico['M3_Arbol_Decision']['clase_predicha']}")
    print(f"* M4 Random Forest:       {prob_m4_val * 100.0:.2f}% -> {senales_gmexico['M4_Random_Forest']['clase_predicha']}")
    print(f"* M5 GBDT Boosting:       {prob_m5_val * 100.0:.2f}% -> {senales_gmexico['M5_GBDT']['clase_predicha']}")
    print(f"* M6 Red Neuronal MLP:    {prob_m6_val * 100.0:.2f}% -> {senales_gmexico['M6_MLP']['clase_predicha']}")
    print(f"* Promedio exploratorio: {prob_ensamble * 100.0:.2f}% -> {senales_gmexico['Ensamble_Promedio_Fijo_Exploratorio']['clase_predicha']}")

    reporte_completo = {
        "version_metodologia": VERSION_METODOLOGIA,
        "version_features": VERSION_FEATURES,
        "timestamp_recalculo_utc": timestamp_utc(),
        "naturaleza_evaluacion": "EXPLORATORIA_TEST_PREVIAMENTE_INSPECCIONADO",
        "corte_etiquetas_train": "2025-04-29",
        "corte_etiquetas_test": "2026-10-27",
        "ticker": "GMEXICO",
        "serie": "B",
        "sector": "Mineria y materiales",
        "anillo": "Plata",
        "muestras": {
            "train_sesiones": len(train_df),
            "test_sesiones": len(test_df),
            "tasa_positiva_train": p_prior,
            "tasa_positiva_test": float(np.mean(y_test)),
        },
        "correlaciones_variables": corrs,
        "evaluacion_modelos_test": models_eval,
        "recalculo_retroactivo_20261028": senales_gmexico,
    }

    with open(OUTPUT_REPORTE_JSON, "w", encoding="utf-8") as f:
        json.dump(reporte_completo, f, indent=2, ensure_ascii=False)
    print(f"\nReporte JSON guardado en: {OUTPUT_REPORTE_JSON}")


if __name__ == "__main__":
    main()
