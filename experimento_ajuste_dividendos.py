import json
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from metodologia_ppp import FEATURE_NAMES, calcular_features_ppp, localizar_insumo, validar_ventana_fechas

DOWNLOADS = Path.home() / "Downloads"
Z9D = localizar_insumo("etapa9D_WALMEX_PPP_20261028T153956182393Z.zip")
Z9E = localizar_insumo("etapa9E_WALMEX_PPP_20261028T155304028544Z.zip")
Z9F = localizar_insumo("etapa9F_WALMEX_PPP_20261028T160422494281Z.zip")
Z9G = localizar_insumo("etapa9G_WALMEX_PPP_20261028T164002342440Z.zip")
Z9G_IN = localizar_insumo("Prisma_BMV_Etapa9G_Insumos_Prueba_Final_CORREGIDO.zip")

FEATURES_8 = FEATURE_NAMES


def standard_scale(X_train, X_eval):
    mean = np.mean(X_train, axis=0)
    scale = np.std(X_train, axis=0, ddof=0)
    scale_safe = np.where(scale == 0.0, 1.0, scale)
    return (X_train - mean) / scale_safe, (X_eval - mean) / scale_safe, mean, scale_safe


def fit_logistic_regression_balanced(X, y, C=1.0, tol=1e-12, max_iter=200):
    """
    Exacta reproduccion de sklearn.linear_model.LogisticRegression(C=1.0, class_weight='balanced')
    mediante Newton-Raphson (IRLS) sobre el objetivo estrictamente convexo:
      L(w, b) = sum_i s_i * [ -y_i z_i + log(1 + exp(z_i)) ] + 0.5 / C * ||w||_2^2
    donde s_i = N / (2 * N_{y_i}).
    """
    n_samples, n_features = X.shape
    n0 = np.sum(y == 0)
    n1 = np.sum(y == 1)
    w0 = n_samples / (2.0 * n0)
    w1 = n_samples / (2.0 * n1)
    sample_weights = np.where(y == 1, w1, w0)

    # Aumentar X con columna de 1s al final para el intercepto (no penalizado por L2)
    X_aug = np.hstack([X, np.ones((n_samples, 1), dtype=float)])
    theta = np.zeros(n_features + 1, dtype=float)
    reg_diag = np.ones(n_features + 1, dtype=float) / C
    reg_diag[-1] = 0.0  # El intercepto no se penaliza en sklearn

    for _ in range(max_iter):
        z = X_aug @ theta
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))
        grad = X_aug.T @ (sample_weights * (p - y)) + reg_diag * theta
        W = sample_weights * p * (1.0 - p)
        H = (X_aug.T * W) @ X_aug + np.diag(reg_diag)
        step = np.linalg.solve(H, grad)
        theta -= step
        if np.max(np.abs(step)) < tol:
            break

    coef = theta[:-1]
    intercept = float(theta[-1])
    return coef, intercept


def predict_proba_logistic(X, coef, intercept):
    z = X @ coef + intercept
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))


def load_data():
    with zipfile.ZipFile(Z9D) as zf:
        s9d = pd.read_csv(zf.open("datos/serie_PPP_con_controles.csv"))
        el9d = pd.read_csv(zf.open("reportes/elegibilidad_por_fecha.csv"))
        divs9d = pd.read_csv(zf.open("procedencia/dividendos_documentados_incorporados.csv"))

    with zipfile.ZipFile(Z9E) as zf:
        periodos9e = pd.read_csv(zf.open("reportes/fechas_periodos.csv"))
        pred9e = pd.read_csv(zf.open("resultados/predicciones_solo_train.csv"))
        coefs9e = pd.read_csv(zf.open("resultados/coeficientes.csv"))

    with zipfile.ZipFile(Z9F) as zf:
        pred9f = pd.read_csv(zf.open("resultados/predicciones_validacion.csv"))

    with zipfile.ZipFile(Z9G) as zf:
        s9g = pd.read_csv(zf.open("datos/PPP_final_controles.csv"))
        sel9g = pd.read_csv(zf.open("datos/seleccion_final.csv"))
        pred9g = pd.read_csv(zf.open("resultados/predicciones_finales.csv"))

    with zipfile.ZipFile(Z9G_IN) as zf:
        divs9g = pd.read_csv(zf.open("datos/eventos_ex_final_documentados.csv"))

    return s9d, el9d, divs9d, periodos9e, pred9e, coefs9e, pred9f, s9g, sel9g, pred9g, divs9g


def build_adjusted_features_and_indicator(s_df, el_df, div_map):
    df = s_df.sort_values("posicion_rejilla_heredada").reset_index(drop=True).copy()
    el = el_df.sort_values("posicion_sesion").reset_index(drop=True).copy()

    n = len(df)
    prices = df["precio_para_calculo"].to_numpy(dtype=float)
    apto_precio = df["precio_apto_calculo"].to_numpy(dtype=bool)
    fechas = df["fecha"].astype(str).tolist()
    divs = np.array([div_map.get(f, 0.0) for f in fechas], dtype=float)
    evento_ex = df["evento_ex_en_fecha"].to_numpy(dtype=bool)

    adj_rows = []
    for t in range(n):
        if t + 5 < n:
            ex_inminente = int(np.any(evento_ex[t + 1 : t + 6]))
            div_futuro_monto = float(np.sum(divs[t + 1 : t + 6]))
        else:
            ex_inminente = 0
            div_futuro_monto = 0.0

        if t < 20:
            adj_rows.append(
                {
                    "fecha": fechas[t],
                    "posicion_sesion": int(df.loc[t, "posicion_rejilla_heredada"]),
                    "ex_div_inminente_5d": ex_inminente,
                    "div_futuro_5d": div_futuro_monto,
                    "apto_features_ajustadas": False,
                    **{col: np.nan for col in FEATURES_8},
                }
            )
            continue

        win_apto = apto_precio[t - 20 : t + 1]
        posiciones_win = df["posicion_rejilla_heredada"].iloc[t - 20 : t + 1].to_numpy()
        continua = np.all(np.diff(posiciones_win) == 1)
        try:
            validar_ventana_fechas(fechas[t - 20 : t + 1], fechas[t])
        except ValueError:
            continua = False
        if not np.all(win_apto) or not continua:
            adj_rows.append(
                {
                    "fecha": fechas[t],
                    "posicion_sesion": int(df.loc[t, "posicion_rejilla_heredada"]),
                    "ex_div_inminente_5d": ex_inminente,
                    "div_futuro_5d": div_futuro_monto,
                    "apto_features_ajustadas": False,
                    **{col: np.nan for col in FEATURES_8},
                }
            )
            continue

        win_p = prices[t - 20 : t + 1].copy()
        win_d = divs[t - 20 : t + 1].copy()

        # Ajuste retroactivo local: PPP_s^(t) = PPP_s - sum_{tau in (s, t]} D_tau
        p_tilde = win_p.copy()
        for tau_idx in range(1, 21):
            if win_d[tau_idx] > 0:
                p_tilde[:tau_idx] -= win_d[tau_idx]

        if np.any(p_tilde <= 0):
            adj_rows.append(
                {
                    "fecha": fechas[t],
                    "posicion_sesion": int(df.loc[t, "posicion_rejilla_heredada"]),
                    "ex_div_inminente_5d": ex_inminente,
                    "div_futuro_5d": div_futuro_monto,
                    "apto_features_ajustadas": False,
                    **{col: np.nan for col in FEATURES_8},
                }
            )
            continue

        feats = dict(zip(FEATURES_8, calcular_features_ppp(p_tilde)))

        adj_rows.append(
            {
                "fecha": fechas[t],
                "posicion_sesion": int(df.loc[t, "posicion_rejilla_heredada"]),
                "ex_div_inminente_5d": ex_inminente,
                "div_futuro_5d": div_futuro_monto,
                "apto_features_ajustadas": True,
                **feats,
            }
        )

    adj_df = pd.DataFrame(adj_rows)
    merged = el.merge(
        adj_df,
        on=["fecha", "posicion_sesion"],
        how="left",
        suffixes=("_orig", "_adj"),
    )
    mask_clean = merged["apto_features"] == True
    max_diff = 0.0
    for c in FEATURES_8:
        diff = np.max(np.abs(merged.loc[mask_clean, f"{c}_orig"] - merged.loc[mask_clean, f"{c}_adj"]))
        max_diff = max(max_diff, float(diff))
    print(f"Max diff entre calculo original 9D y calculo ajustado en ventanas sin evento: {max_diff:.2e}")
    return merged


def evaluate_predictions(df_preds):
    y_true = df_preds["y_real"].to_numpy(dtype=int)
    y_pred = df_preds["y_predicho"].to_numpy(dtype=int)
    prob = np.clip(df_preds["prob_alza"].to_numpy(dtype=float), 1e-15, 1.0 - 1e-15)
    ret_5d = df_preds["retorno_futuro_h5"].to_numpy(dtype=float)

    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))

    acc = (tn + tp) / len(y_true)
    rec0 = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    rec1 = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    bacc = 0.5 * (rec0 + rec1)
    ll = float(-np.mean(y_true * np.log(prob) + (1.0 - y_true) * np.log(1.0 - prob)))
    brier = float(np.mean((prob - y_true) ** 2))
    fp_caida_2pct = int(np.sum((y_pred == 1) & (y_true == 0) & (ret_5d <= -0.02)))

    return {
        "n": int(len(df_preds)),
        "aciertos": int(tn + tp),
        "errores": int(fp + fn),
        "accuracy_pct": round(acc * 100, 2),
        "balanced_accuracy_pct": round(bacc * 100, 2),
        "log_loss": round(ll, 4),
        "brier": round(brier, 4),
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "TP": tp,
        "FP_caida_ge_2pct": fp_caida_2pct,
    }


def run_9e_experiment(merged, periodos9e, mode):
    all_preds = []
    fold_metrics = []
    coefs_by_fold = {}

    for _, row in periodos9e.iterrows():
        fold = int(row["fold"])
        t_start, t_end = int(row["inicio_train_pos"]), int(row["fin_train_exclusivo_pos"])
        v_start, v_end = int(row["inicio_validacion_pos"]), int(row["fin_validacion_exclusivo_pos"])

        in_train_range = (merged["posicion_sesion"] - 20 >= t_start) & (merged["posicion_sesion"] + 5 < t_end)
        in_val_range = (merged["posicion_sesion"] - 20 >= v_start) & (merged["posicion_sesion"] + 5 < v_end)

        if mode in ("base", "ind_only_same_sample"):
            train_mask = in_train_range & (merged["apto_dataset"] == True)
            val_mask = in_val_range & (merged["apto_dataset"] == True)
        elif mode in ("adj_train_8vars_eval_495", "adj_train_9vars_eval_495"):
            train_mask = (
                in_train_range
                & (merged["apto_features_ajustadas"] == True)
                & (merged["apto_label_h5"] == True)
            )
            val_mask = in_val_range & (merged["apto_dataset"] == True)
        elif mode in ("adj_both_8vars_eval_expanded", "adj_both_9vars_eval_expanded"):
            train_mask = (
                in_train_range
                & (merged["apto_features_ajustadas"] == True)
                & (merged["apto_label_h5"] == True)
            )
            val_mask = (
                in_val_range
                & (merged["apto_features_ajustadas"] == True)
                & (merged["apto_label_h5"] == True)
            )
        else:
            raise ValueError(mode)

        df_tr = merged.loc[train_mask].copy()
        df_va = merged.loc[val_mask].copy()

        feat_cols = [f"{c}_adj" for c in FEATURES_8]
        if "9vars" in mode or mode == "ind_only_same_sample":
            feat_cols = feat_cols + ["ex_div_inminente_5d"]

        X_tr = df_tr[feat_cols].to_numpy(dtype=float)
        y_tr = df_tr["y_h5"].to_numpy(dtype=int)
        X_va = df_va[feat_cols].to_numpy(dtype=float)
        y_va = df_va["y_h5"].to_numpy(dtype=int)

        X_tr_s, X_va_s, _, _ = standard_scale(X_tr, X_va)
        coef, intercept = fit_logistic_regression_balanced(X_tr_s, y_tr, C=1.0)
        prob = predict_proba_logistic(X_va_s, coef, intercept)
        pred = (prob >= 0.5).astype(int)

        coefs_by_fold[fold] = {
            col.replace("_adj", ""): round(float(c), 6) for col, c in zip(feat_cols, coef)
        }
        coefs_by_fold[fold]["intercepto"] = round(intercept, 6)

        fold_df = pd.DataFrame(
            {
                "fold": fold,
                "fecha": df_va["fecha"].values,
                "posicion_sesion": df_va["posicion_sesion"].values,
                "y_real": y_va,
                "y_predicho": pred,
                "prob_alza": prob,
                "retorno_futuro_h5": df_va["retorno_futuro_h5"].values,
                "ex_div_inminente_5d": df_va["ex_div_inminente_5d"].values,
                "evento_en_historia": df_va["evento_en_historia"].values,
            }
        )
        all_preds.append(fold_df)
        fm = evaluate_predictions(fold_df)
        fm["fold"] = fold
        fm["n_train"] = int(len(df_tr))
        fold_metrics.append(fm)

    full_preds = pd.concat(all_preds, ignore_index=True)
    global_metrics = evaluate_predictions(full_preds)
    global_metrics["mean_fold_bacc_pct"] = round(
        float(np.mean([m["balanced_accuracy_pct"] for m in fold_metrics])), 2
    )
    return global_metrics, fold_metrics, full_preds, coefs_by_fold


def main():
    s9d, el9d, divs9d, periodos9e, pred9e, coefs9e, pred9f, s9g, sel9g, pred9g, divs9g = load_data()

    div_map = dict(zip(divs9d["fecha_ex"].astype(str), divs9d["dividendo_documentado"].astype(float)))
    for _, r in divs9g.iterrows():
        div_map[str(r["fecha_ex"])] = float(r["dividendo_documentado"])

    merged = build_adjusted_features_and_indicator(s9d, el9d, div_map)

    p9e_bal = pred9e[pred9e["modelo"] == "logistica_balanceada"].copy()
    fechas_495 = set(p9e_bal["fecha"].astype(str))

    m_495 = merged[merged["fecha"].isin(fechas_495)].copy()
    print("\n=== Eventos ex_div_inminente_5d dentro de las 495 fechas de 9E ===")
    ex_495 = m_495[m_495["ex_div_inminente_5d"] == 1][
        ["fecha", "posicion_sesion", "div_futuro_5d", "retorno_futuro_h5", "y_h5"]
    ]
    print(f"Total fechas con ex_div_inminente_5d == 1 en las 495 fechas: {len(ex_495)}")
    print(ex_495.to_string(index=False))

    m_train_1036 = merged[(merged["bloque"] == "train") & (merged["apto_dataset"] == True)]
    print(
        f"\nTotal fechas con ex_div_inminente_5d == 1 en los 1,036 ejemplos de train: "
        f"{int(m_train_1036['ex_div_inminente_5d'].sum())} de {len(m_train_1036)}"
    )
    print(
        "Distribucion de y_h5 cuando ex_div_inminente_5d == 1 en train (1036):",
        m_train_1036[m_train_1036["ex_div_inminente_5d"] == 1]["y_h5"]
        .value_counts()
        .to_dict(),
    )

    m_train_exp = merged[
        (merged["bloque"] == "train")
        & (merged["apto_features_ajustadas"] == True)
        & (merged["apto_label_h5"] == True)
        & (merged["soporte_dentro_del_bloque"] == True)
    ]
    print(
        f"Total ejemplos de train al recuperar EVENTO_EX_EN_HISTORIA mediante ajuste retroactivo: "
        f"{len(m_train_exp)} (antes 1,036; +{len(m_train_exp) - len(m_train_1036)} recuperados)"
    )

    modes = [
        ("1. Modelo Base Actual (8 vars, sin ajuste, 495 fechas)", "base"),
        ("2. Misma muestra + ex_div_inminente_5d (9 vars, 495 fechas)", "ind_only_same_sample"),
        ("3. Train con ajuste retroactivo (8 vars), evaluado en 495 fechas", "adj_train_8vars_eval_495"),
        ("4. Experimento Completo: Train con ajuste retroactivo + indicador (9 vars), evaluado en 495 fechas", "adj_train_9vars_eval_495"),
        ("5. Train y Eval expandidos con ajuste retroactivo (8 vars, 616 fechas)", "adj_both_8vars_eval_expanded"),
        ("6. Train y Eval expandidos con ajuste retroactivo + indicador (9 vars, 616 fechas)", "adj_both_9vars_eval_expanded"),
    ]

    summary_rows = []
    details = {}
    for label, mode in modes:
        gm, fm, preds, coefs = run_9e_experiment(merged, periodos9e, mode)
        gm["variante"] = label
        gm["mode"] = mode
        summary_rows.append(gm)
        details[mode] = {"global": gm, "folds": fm, "preds": preds, "coefs": coefs}

    # Verificar exactitud numerica del solver IRLS contra las probabilidades oficiales de 9E
    p_base = details["base"]["preds"].sort_values("posicion_sesion")["prob_alza"].to_numpy()
    p_orig = p9e_bal.sort_values("posicion_sesion")["prob_alza"].to_numpy()
    print(f"\nVerificacion IRLS vs sklearn original en las 495 fechas (max diff prob): {np.max(np.abs(p_base - p_orig)):.2e}")

    print("\n=== RESUMEN COMPARATIVO EN VALIDACION INTERNA (4 PERIODOS) ===")
    for r in summary_rows:
        print(f"\n>> {r['variante']}")
        print(
            f"   N={r['n']} | Aciertos={r['aciertos']} | Exactitud={r['accuracy_pct']}% | "
            f"Exactitud bal. agrupada={r['balanced_accuracy_pct']}% | Exactitud bal. media={r['mean_fold_bacc_pct']}%"
        )
        print(
            f"   Log loss={r['log_loss']} | Brier={r['brier']} | "
            f"TN={r['TN']}, FP={r['FP']} (caidas>=2%: {r['FP_caida_ge_2pct']}), FN={r['FN']}, TP={r['TP']}"
        )
        for f in details[r["mode"]]["folds"]:
            print(
                f"     Fold {f['fold']} (n_train={f['n_train']}, n_val={f['n']}): "
                f"Acc={f['accuracy_pct']}%, BalAcc={f['balanced_accuracy_pct']}%, "
                f"LogLoss={f['log_loss']}, Brier={f['brier']}, FP={f['FP']}, TP={f['TP']}"
            )
        if "9vars" in r["mode"] or r["mode"] == "ind_only_same_sample":
            print("     Coeficiente estandarizado de ex_div_inminente_5d por fold:", {
                k: v.get("ex_div_inminente_5d") for k, v in details[r["mode"]]["coefs"].items()
            })

    OUT_DIR = Path(__file__).resolve().parent
    pd.DataFrame(summary_rows).to_csv(OUT_DIR / "resultados_experimento_dividendos.csv", index=False)
    with open(OUT_DIR / "detalle_experimento_dividendos.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                k: {"global": v["global"], "folds": v["folds"], "coefs": v["coefs"]}
                for k, v in details.items()
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


if __name__ == "__main__":
    main()
