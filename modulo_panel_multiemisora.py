"""
modulo_panel_multiemisora.py
=============================
Procesador de variables y modelado en panel multi-emisora para las 15 empresas del IPC.
Utiliza exclusivamente la serie reconstruida de PPP estricto de la BMV.

Reglas metodologicas estrictas:
1. Cero imputacion: ejemplos con huecos en la ventana de 21 sesiones o en t+5 se descartan
   documentadamente, sin sustitucion por ceros ni arrastre de precios anteriores.
2. Sin fuga temporal: corte temporal identico al oficial de Prisma BMV:
   - Train: sesiones hasta 2025-04-29
   - Test: sesiones desde 2025-04-30 hasta 2026-10-27
   - Prospectiva: 2026-10-28
3. Implementacion matematica exacta en NumPy puro (IRLS Newton-Raphson balanceado).
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
from metodologia_ppp import (
    FEATURE_NAMES, VERSION_FEATURES, VERSION_METODOLOGIA, calcular_features_ppp,
    seleccionar_train_test, validar_ventana_fechas, add_bmv_sessions,
)

WORKSPACE = Path(r"D:\Universidad\7mo Semestre\Big Data\Proyecto final")
INPUT_SERIE_CSV = WORKSPACE / "serie_ppp_historica_15_emisoras_bmv.csv"
OUTPUT_FEATURES_CSV = WORKSPACE / "dataset_panel_15_emisoras_features.csv"
OUTPUT_METRICAS_JSON = WORKSPACE / "metricas_panel_15_emisoras.json"

OUTPUT_COLS = [
    "fecha",
    "posicion_sesion",
    "emisora",
    "serie",
    "sector_economico",
    "anillo_madurez",
    "ppp_t",
    "ret_1",
    "ret_5",
    "ret_10",
    "ret_20",
    "volatilidad_5",
    "volatilidad_20",
    "distancia_media_5",
    "distancia_media_20",
    "fecha_objetivo_h5",
    "ppp_t5",
    "target_disponible",
    "target_y",
    "periodo_oficial",
    "version_features",
]


def extract_features_and_targets_for_issuer(df_issuer: pd.DataFrame, ticker: str):
    """
    Para una emisora dada, recorre la rejilla cronologica completa y extrae
    las 8 variables canonicas de PPP y la etiqueta Y_t = I(PPP_{t+5} > PPP_t).
    Descarta estrictamente cualquier posicion donde haya un hueco en [t-20..t] o en t+5.
    """
    sub = df_issuer.sort_values("posicion_sesion").reset_index(drop=True)
    n = len(sub)
    rows = []

    ppp_series = sub["ppp_bmv_mxn"].to_numpy(dtype=float)
    fechas = sub["fecha"].to_numpy(dtype=str)
    posiciones = sub["posicion_sesion"].to_numpy(dtype=int)
    estados = sub["estado_captura"].to_numpy(dtype=str)
    series = sub["serie"].to_numpy(dtype=str)
    sectores = sub["sector_economico"].to_numpy(dtype=str)
    anillos = sub["anillo_madurez"].to_numpy(dtype=str)

    if sub["fecha"].duplicated().any() or sub["posicion_sesion"].duplicated().any():
        raise ValueError(f"Fechas o posiciones duplicadas para {ticker}")
    is_valid = (estados == "PPP_PUBLICADO_VERIFICADO") & np.isfinite(ppp_series) & (ppp_series > 0)
    fecha_to_idx = {f: idx for idx, f in enumerate(fechas)}

    for i in range(20, n):
        f_t = fechas[i]
        pos_t = posiciones[i]

        # 1. Verificar que la ventana historica [i-20..i] (21 sesiones) sea 100% valida
        win_valid = is_valid[i - 20 : i + 1]
        if not np.all(win_valid):
            continue
        if not np.all(np.diff(posiciones[i - 20 : i + 1]) == 1):
            continue
        try:
            validar_ventana_fechas(fechas[i - 20 : i + 1], f_t)
        except ValueError:
            continue

        p_win = ppp_series[i - 20 : i + 1]
        p_t = p_win[20]
        feats = dict(zip(FEATURE_NAMES, calcular_features_ppp(p_win)))

        # 2. Objetivo a 5 sesiones (i+5)
        target_available = False
        y_val = np.nan
        fecha_obj = add_bmv_sessions(f_t, 5)
        p_target = np.nan

        j = fecha_to_idx.get(fecha_obj)
        if j is not None:
            # El target usa la fecha bursatil exacta, nunca la quinta fila disponible.
            if is_valid[j]:
                p_target = ppp_series[j]
                y_val = 1 if p_target > p_t else 0
                target_available = True

        rows.append({
            "fecha": f_t,
            "posicion_sesion": pos_t,
            "emisora": ticker,
            "serie": series[i],
            "sector_economico": sectores[i],
            "anillo_madurez": anillos[i],
            "ppp_t": p_t,
            **feats,
            "fecha_objetivo_h5": fecha_obj,
            "ppp_t5": p_target,
            "target_disponible": target_available,
            "target_y": y_val,
            "periodo_oficial": "TRAIN" if f_t <= "2025-04-29" else ("TEST" if f_t <= "2026-10-27" else "PROSPECTIVA"),
            "version_features": VERSION_FEATURES,
        })

    if not rows:
        return pd.DataFrame(columns=OUTPUT_COLS)
    return pd.DataFrame(rows)


def fit_predict_logistic_balanced(X_train, y_train, X_eval):
    """Ajusta LogisticRegression balanceada con C=1.0 via Newton-Raphson IRLS puro."""
    y_tr = y_train.astype(float)
    n_0 = np.sum(y_tr == 0)
    n_1 = np.sum(y_tr == 1)
    if n_0 == 0 or n_1 == 0:
        return np.full(len(X_eval), np.nan)

    w_0 = len(y_tr) / (2.0 * n_0)
    w_1 = len(y_tr) / (2.0 * n_1)
    sw = np.where(y_tr == 1, w_1, w_0)

    # Standardize
    mean_tr = np.mean(X_train, axis=0)
    std_tr = np.std(X_train, axis=0)
    std_tr[std_tr == 0] = 1.0

    X_tr_s = (X_train - mean_tr) / std_tr
    X_ev_s = (X_eval - mean_tr) / std_tr

    X_tr_aug = np.column_stack([np.ones(len(X_tr_s)), X_tr_s])
    X_ev_aug = np.column_stack([np.ones(len(X_ev_s)), X_ev_s])

    beta = np.zeros(X_tr_aug.shape[1])
    C_reg = 1.0
    lambda_val = 1.0 / C_reg

    for _ in range(40):
        p = 1.0 / (1.0 + np.exp(-np.clip(X_tr_aug @ beta, -35.0, 35.0)))
        W_diag = sw * p * (1.0 - p)
        W_diag = np.maximum(W_diag, 1e-12)
        grad = X_tr_aug.T @ (sw * (p - y_tr))
        grad[1:] += lambda_val * beta[1:]
        H = X_tr_aug.T @ (W_diag[:, None] * X_tr_aug)
        H[np.diag_indices(len(beta))[0][1:], np.diag_indices(len(beta))[1][1:]] += lambda_val
        try:
            d = np.linalg.solve(H + 1e-9 * np.eye(len(beta)), grad)
        except np.linalg.LinAlgError:
            break
        beta -= d
        if np.max(np.abs(d)) < 1e-7:
            break

    logits_eval = X_ev_aug @ beta
    probs = 1.0 / (1.0 + np.exp(-np.clip(logits_eval, -35.0, 35.0)))
    return probs


def evaluate_issuer_performance(df_feat: pd.DataFrame, ticker: str):
    """
    Entrena y evalua el modelo canónico en la emisora si cuenta con suficientes datos.
    """
    sub = df_feat[df_feat["emisora"] == ticker]
    if sub.empty:
        return {
            "ticker": ticker,
            "estado_evaluacion": "SIN_VENTANAS_CONTINUAS_21_SESIONES",
            "n_train_elegible": 0,
            "n_test_elegible": 0,
        }

    train_df, test_df = seleccionar_train_test(sub)

    n_train = len(train_df)
    n_test = len(test_df)

    if n_train < 50 or n_test < 10:
        return {
            "ticker": ticker,
            "estado_evaluacion": "DATOS_INSUFICIENTES_POR_HUECOS_BOLETIN",
            "n_train_elegible": n_train,
            "n_test_elegible": n_test,
        }

    y_train = train_df["target_y"].to_numpy(dtype=float)
    y_test = test_df["target_y"].to_numpy(dtype=float)

    if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
        return {
            "ticker": ticker,
            "estado_evaluacion": "MONOCLASE_EN_SUBMUESTRA",
            "n_train_elegible": n_train,
            "n_test_elegible": n_test,
        }

    X_train = train_df[FEATURE_NAMES].to_numpy(dtype=float)
    X_test = test_df[FEATURE_NAMES].to_numpy(dtype=float)

    probs_test = fit_predict_logistic_balanced(X_train, y_train, X_test)
    preds_test = (probs_test >= 0.5).astype(int)

    brier = float(np.mean((probs_test - y_test) ** 2))
    eps = 1e-15
    p_clip = np.clip(probs_test, eps, 1.0 - eps)
    log_loss = float(-np.mean(y_test * np.log(p_clip) + (1.0 - y_test) * np.log(1.0 - p_clip)))

    p_prior = np.mean(y_train)
    brier_dummy = float(np.mean((p_prior - y_test) ** 2))

    tpr = np.mean(preds_test[y_test == 1] == 1) if np.sum(y_test == 1) > 0 else 0.0
    tnr = np.mean(preds_test[y_test == 0] == 0) if np.sum(y_test == 0) > 0 else 0.0
    bal_acc = float((tpr + tnr) / 2.0)
    acc = float(np.mean(preds_test == y_test))

    return {
        "ticker": ticker,
        "estado_evaluacion": "EVALUADO_CON_EXITO",
        "version_metodologia": VERSION_METODOLOGIA,
        "version_features": VERSION_FEATURES,
        "naturaleza_evaluacion": "EXPLORATORIA_TEST_PREVIAMENTE_INSPECCIONADO",
        "n_train_purgado": int(((sub.periodo_oficial == "TRAIN") & sub.target_disponible).sum() - len(train_df)),
        "n_test_fuera_corte": int(((sub.periodo_oficial == "TEST") & sub.target_disponible).sum() - len(test_df)),
        "n_train_elegible": n_train,
        "n_test_elegible": n_test,
        "tasa_positiva_train": round(float(np.mean(y_train)), 4),
        "tasa_positiva_test": round(float(np.mean(y_test)), 4),
        "brier_score_test": round(brier, 6),
        "brier_score_dummy_referencia": round(brier_dummy, 6),
        "supera_referencia_brier": bool(brier < brier_dummy),
        "log_loss_test": round(log_loss, 6),
        "accuracy_test": round(acc, 4),
        "balanced_accuracy_test": round(bal_acc, 4),
    }


def main():
    if not INPUT_SERIE_CSV.exists():
        print(f"Error: {INPUT_SERIE_CSV} no existe todavia. Ejecuta primero reconstruccion_ppp_15_emisoras.py")
        return

    print("Cargando serie reconstruida de las 15 empresas...")
    df_serie = pd.read_csv(INPUT_SERIE_CSV)
    print(f"Total registros en serie: {len(df_serie)}")

    tickers = sorted(df_serie["emisora"].unique())
    all_features = []

    print("\nExtrayendo variables canonicas (lookback estricto de 21 sesiones)...")
    for tk in tickers:
        df_tk = df_serie[df_serie["emisora"] == tk]
        feat_tk = extract_features_and_targets_for_issuer(df_tk, tk)
        all_features.append(feat_tk)
        if not feat_tk.empty:
            n_tr = len(feat_tk[feat_tk["periodo_oficial"] == "TRAIN"])
            n_te = len(feat_tk[feat_tk["periodo_oficial"] == "TEST"])
            print(f"  {tk}: {len(feat_tk)} ejemplos continuos (Train: {n_tr}, Test: {n_te})")
        else:
            print(f"  {tk}: 0 ejemplos continuos (alta presencia de huecos en ventanas de 21 dias)")

    df_all_feats = pd.concat(all_features, ignore_index=True)
    df_all_feats.to_csv(OUTPUT_FEATURES_CSV, index=False, encoding="utf-8-sig")
    print(f"\nDataset panel de variables guardado: {OUTPUT_FEATURES_CSV} ({len(df_all_feats)} filas).")

    print("\nEvaluando modelo logistico canonico por emisora...")
    eval_results = {}
    for tk in tickers:
        res = evaluate_issuer_performance(df_all_feats, tk)
        eval_results[tk] = res

    with open(OUTPUT_METRICAS_JSON, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, indent=2, ensure_ascii=False)
    print(f"Metricas guardadas en: {OUTPUT_METRICAS_JSON}")

    print("\n" + "=" * 70)
    print("RESULTADOS DE EVALUACION POR EMISORA (LISTA VERTICAL):")
    print("=" * 70)
    for tk, res in eval_results.items():
        print(f"* {tk}:")
        print(f"    - Estado: {res['estado_evaluacion']}")
        print(f"    - Ejemplos Train: {res.get('n_train_elegible', 0)} | Test: {res.get('n_test_elegible', 0)}")
        if res["estado_evaluacion"] == "EVALUADO_CON_EXITO":
            print(f"    - Brier Score Test: {res['brier_score_test']} (Referencia Dummy: {res['brier_score_dummy_referencia']}) -> Supera: {res['supera_referencia_brier']}")
            print(f"    - Log Loss Test: {res['log_loss_test']}")
            print(f"    - Balanced Accuracy Test: {res['balanced_accuracy_test'] * 100:.2f}% | Accuracy: {res['accuracy_test'] * 100:.2f}%")


if __name__ == "__main__":
    main()
