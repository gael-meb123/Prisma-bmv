import json
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd

from experimento_ajuste_dividendos import (
    FEATURES_8,
    evaluate_predictions,
    fit_logistic_regression_balanced,
    predict_proba_logistic,
    standard_scale,
)
from experimento_integral_ia_boletines_noticias import (
    fit_elasticnet_logistic_balanced,
    fit_predict_gbdt,
    fit_predict_mlp,
    fit_predict_random_forest,
)

DOWNLOADS = Path(r"C:\Users\GAELMENDOZABALLARDO\Downloads")
OUT_DIR = Path(r"D:\Universidad\7mo Semestre\Big Data\Proyecto final")
Z8 = DOWNLOADS / "etapa8_20261028T043637850012Z.zip"


def run_multicompany_model_selector():
    """
    Modulo Comparativo Separado (Opcion 1 - Nivel 2):
    Evalua el catalogo cerrado de algoritmos sobre las tres emisoras de arquetipos sectoriales distintos:
      - WALMEX (Consumo Frecuente / Minorista Defensivo)
      - GMEXICO (Materiales / Mineria y Cobre - Ciclico Tendencial)
      - GFNORTE (Financiero / Banca - Sensible a Tasas)
    Utiliza la particion temporal de validacion (validation_h5.csv de Silver v0.4) para seleccionar
    el algoritmo optimo de cada empresa (menor Log Loss y mayor Exactitud Balanceada) y documenta
    la matriz comparativa completa sin contaminar la serie PPP maestra de WALMEX.
    """
    with zipfile.ZipFile(Z8) as zf:
        tr = pd.read_csv(zf.open("gold_v0_4/train_h5.csv"))
        va = pd.read_csv(zf.open("gold_v0_4/validation_h5.csv"))
        te = pd.read_csv(zf.open("gold_v0_4/test_h5.csv"))

    sector_map = {
        "WALMEX": "Consumo Defensivo / Minorista (Reversion a la media con filtro de volatilidad)",
        "GMEXICO": "Materiales / Mineria Cobre (Ciclico con tendencias persistentes)",
        "GFNORTE": "Financiero / Banca (Sensible al ciclo monetario y tasas)",
    }

    rows = []
    selected_by_ticker = {}

    for ticker in ["WALMEX", "GMEXICO", "GFNORTE"]:
        tr_t = tr[tr["emisora"] == ticker].dropna(subset=FEATURES_8 + ["y_h5"]).copy()
        va_t = va[va["emisora"] == ticker].dropna(subset=FEATURES_8 + ["y_h5"]).copy()
        te_t = te[te["emisora"] == ticker].dropna(subset=FEATURES_8 + ["y_h5"]).copy()

        X_tr, X_va, _, _ = standard_scale(
            tr_t[FEATURES_8].to_numpy(dtype=float), va_t[FEATURES_8].to_numpy(dtype=float)
        )
        y_tr = tr_t["y_h5"].to_numpy(dtype=int)
        y_va = va_t["y_h5"].to_numpy(dtype=int)

        tr_plus_va = pd.concat([tr_t, va_t], ignore_index=True)
        X_tr_full, X_te, _, _ = standard_scale(
            tr_plus_va[FEATURES_8].to_numpy(dtype=float), te_t[FEATURES_8].to_numpy(dtype=float)
        )
        y_tr_full = tr_plus_va["y_h5"].to_numpy(dtype=int)
        y_te = te_t["y_h5"].to_numpy(dtype=int)

        candidates = [
            (
                "Regresion Logistica L2 Balanceada (Lineal)",
                lambda X_a, y_a, X_b: predict_proba_logistic(
                    X_b, *fit_logistic_regression_balanced(X_a, y_a, C=1.0)
                ),
            ),
            (
                "ElasticNet L1+L2 Balanceado (Lineal Disperso)",
                lambda X_a, y_a, X_b: predict_proba_logistic(
                    X_b, *fit_elasticnet_logistic_balanced(X_a, y_a, C=0.10)
                ),
            ),
            (
                "Random Forest Balanceado (max_depth=3, No Lineal Conservador)",
                lambda X_a, y_a, X_b: fit_predict_random_forest(
                    X_a, y_a, X_b, n_estimators=80, max_depth=3, min_samples_leaf=25, seed=42
                ),
            ),
            (
                "Gradient Boosting GBDT (max_depth=2, Boosting Suave)",
                lambda X_a, y_a, X_b: fit_predict_gbdt(
                    X_a, y_a, X_b, n_estimators=50, learning_rate=0.05, max_depth=2, seed=42
                ),
            ),
            (
                "Red Neuronal MLP (16x8, tanh + L2)",
                lambda X_a, y_a, X_b: fit_predict_mlp(
                    X_a, y_a, X_b, hidden=(16, 8), lr=0.008, l2_reg=0.03, epochs=220, seed=42
                ),
            ),
        ]

        ticker_candidates = []
        for mname, fn in candidates:
            prob_va = fn(X_tr, y_tr, X_va)
            df_va_pred = pd.DataFrame(
                {
                    "y_real": y_va,
                    "y_predicho": (prob_va >= 0.5).astype(int),
                    "prob_alza": prob_va,
                    "retorno_futuro_h5": va_t["retorno_futuro_h5"].values,
                }
            )
            m_va = evaluate_predictions(df_va_pred)

            prob_te = fn(X_tr_full, y_tr_full, X_te)
            df_te_pred = pd.DataFrame(
                {
                    "y_real": y_te,
                    "y_predicho": (prob_te >= 0.5).astype(int),
                    "prob_alza": prob_te,
                    "retorno_futuro_h5": te_t["retorno_futuro_h5"].values,
                }
            )
            m_te = evaluate_predictions(df_te_pred)

            rec = {
                "emisora": ticker,
                "arquetipo_sectorial": sector_map[ticker],
                "algoritmo": mname,
                "n_train": int(len(tr_t)),
                "n_val": int(len(va_t)),
                "val_aciertos": m_va["aciertos"],
                "val_accuracy_pct": m_va["accuracy_pct"],
                "val_balanced_accuracy_pct": m_va["balanced_accuracy_pct"],
                "val_log_loss": m_va["log_loss"],
                "val_brier": m_va["brier"],
                "val_FP": m_va["FP"],
                "n_test_historico": int(len(te_t)),
                "test_aciertos": m_te["aciertos"],
                "test_accuracy_pct": m_te["accuracy_pct"],
                "test_balanced_accuracy_pct": m_te["balanced_accuracy_pct"],
                "test_log_loss": m_te["log_loss"],
                "test_brier": m_te["brier"],
            }
            rows.append(rec)
            ticker_candidates.append(rec)

        # Regla de seleccion ciega en validacion: menor Log Loss entre los que tienen Balanced Accuracy > 50%
        valid_cands = [c for c in ticker_candidates if c["val_balanced_accuracy_pct"] > 50.0]
        best_cand = sorted(
            valid_cands if valid_cands else ticker_candidates,
            key=lambda c: (c["val_log_loss"], -c["val_balanced_accuracy_pct"]),
        )[0]
        selected_by_ticker[ticker] = best_cand

    df_out = pd.DataFrame(rows)
    df_out.to_csv(
        OUT_DIR / "seleccion_modelo_por_emisora_resultados.csv", index=False, encoding="utf-8-sig"
    )
    with open(OUT_DIR / "reporte_seleccion_multiemisora.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "nota_metodologica": (
                    "Modulo comparativo separado (Silver v0.4). No mezcla precios con la serie maestra "
                    "PPP estricta de WALMEX de las Etapas 9C-9I. La seleccion del algoritmo por emisora "
                    "se realiza exclusivamente con las metricas de validacion."
                ),
                "seleccion_optima_por_emisora": selected_by_ticker,
                "todos_los_resultados": rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("=== MODULO DE SELECCION DE MODELO MULTI-EMISORA EJECUTADO ===")
    for tk, sel in selected_by_ticker.items():
        print(f"\nEmisora: {tk} ({sel['arquetipo_sectorial']})")
        print(f" -> Modelo Seleccionado en Validacion: {sel['algoritmo']}")
        print(
            f" -> Metricas Validacion (n={sel['n_val']}): BalAcc={sel['val_balanced_accuracy_pct']}%, "
            f"Acc={sel['val_accuracy_pct']}%, LogLoss={sel['val_log_loss']}, Brier={sel['val_brier']}"
        )


if __name__ == "__main__":
    run_multicompany_model_selector()
