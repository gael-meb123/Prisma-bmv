"""Benchmark exploratorio PPP vs PPP + FIX + cobre, con folds purgados en Train."""

import hashlib
import json
import numpy as np
import pandas as pd

from fuentes_externas_gmexico import DIRECTORIO, descargar_series
from investigacion_profunda_gmexico import fit_predict_logistic, compute_metrics
from metodologia_ppp import ROOT, FEATURE_NAMES, VERSION_FEATURES, seleccionar_train_test, timestamp_utc

EXTERNAS = ["usd_mxn_logret_5_lag1", "cobre_logret_5_lag1"]
CS = [.01, .1, 1., 10.]
FOLDS = [("2019-01-01", "2020-12-31"), ("2021-01-01", "2022-12-31"), ("2023-01-01", "2023-12-31"), ("2024-01-01", "2025-04-29")]
PROTOCOLO = {
    "version": "GMEXICO_2_FACTORES_V1", "naturaleza": "EXPLORATORIO_TEST_PREVIAMENTE_INSPECCIONADO",
    "modelo": "Logistica L2 sin ponderacion de clases; escalado dentro de cada ajuste",
    "variantes": {"PPP_8": FEATURE_NAMES, "PPP_10": FEATURE_NAMES + EXTERNAS},
    "C_candidatos": CS, "folds_validacion_train": FOLDS,
    "seleccion": "Menor C dentro de 1 SE del menor Brier medio entre folds; misma busqueda en ambas variantes",
    "variables_externas": "Log(valor_t-1 / valor_t-6) sobre sesiones BMV; seis observaciones reales exigidas; sin arrastre",
    "disponibilidad": "HIPOTESIS_CONSERVADORA_REZAGO_1_SESION_BMV; NO_HAY_VINTAGES_HISTORICAS_VERIFICADAS",
    "cobre": "Precio diario BCCh USD/libra, difundido redondeado a dos decimales; no futuros continuos",
    "metrica_primaria": "Brier ampliada menos base sobre las mismas fechas",
    "bootstrap": {"bloque_sesiones_bmv": 20, "replicas": 5000, "semilla": 20261029},
    "criterio_evidencia": "Delta Brier <= -0.001, IC95 superior < 0, mejora en ambos subperiodos de Test; confirmacion prospectiva posterior requerida",
    "emision_prospectiva": False,
}


def construir_dataset(gm, fx, cu, rejilla):
    if not gm.version_features.eq(VERSION_FEATURES).all():
        raise ValueError("El benchmark requiere el panel PPP corregido")
    for frame in [fx, cu]:
        if frame.fecha.duplicated().any():
            raise ValueError("Fuente externa con fechas duplicadas")
    fx = fx.set_index("fecha")
    cu = cu.set_index("fecha")
    grid = list(rejilla)
    positions = {f: i for i, f in enumerate(grid)}
    rows = []
    for row in gm.to_dict("records"):
        i = positions[row["fecha"]]
        row.update({EXTERNAS[0]: np.nan, EXTERNAS[1]: np.nan, "apto_externo": False, "motivo_externo": "HISTORIA_INSUFICIENTE", "disponibilidad_externa": PROTOCOLO["disponibilidad"]})
        if i >= 6:
            dates = grid[i-6:i]
            row["fecha_fuente_inicio"] = dates[0]
            row["fecha_fuente_ultima"] = dates[-1]
            reasons = []
            for frame, col, name in [(fx, "usd_mxn_fix", EXTERNAS[0]), (cu, "cobre_usd_libra", EXTERNAS[1])]:
                win = frame.reindex(dates)
                vals = win[col].to_numpy(dtype=float)
                if not np.all(np.isfinite(vals) & (vals > 0)):
                    reasons.append(col + "_VENTANA_INCOMPLETA")
                else:
                    row[name] = float(np.log(vals[-1] / vals[0]))
                    row[name + "_sha256"] = "|".join(sorted(set(win.sha256_fuente)))
            row["apto_externo"] = not reasons
            row["motivo_externo"] = "ELEGIBLE" if not reasons else ";".join(reasons)
        rows.append(row)
    return pd.DataFrame(rows)


def folds_purgados(train):
    splits = []
    for start, end in FOLDS:
        tr = train[(train.fecha < start) & (train.fecha_objetivo_h5 < start)]
        va = train[train.fecha.between(start, end) & (train.fecha_objetivo_h5 <= end)]
        if len(tr) < 100 or len(va) < 30 or tr.target_y.nunique() < 2 or va.target_y.nunique() < 2:
            raise ValueError(f"Fold insuficiente: {start}, train={len(tr)}, validacion={len(va)}")
        splits.append((tr, va))
    return splits


def seleccionar_c(train, features):
    scores = []
    for c in CS:
        losses, details = [], []
        for tr, va in folds_purgados(train):
            probs, _ = fit_predict_logistic(tr[features].to_numpy(), tr.target_y.to_numpy(), va[features].to_numpy(), C=c, balanced=False)
            brier = float(np.mean((probs - va.target_y.to_numpy()) ** 2))
            losses.append(brier)
            details.append({"n_train": len(tr), "n_val": len(va), "fin_etiquetas_train": tr.fecha_objetivo_h5.max(), "inicio_val": va.fecha.min(), "fin_etiquetas_val": va.fecha_objetivo_h5.max(), "brier": brier})
        scores.append({"C": c, "brier_cv": float(np.mean(losses)), "se_folds": float(np.std(losses, ddof=1) / np.sqrt(len(losses))), "folds": details})
    best = min(scores, key=lambda s: s["brier_cv"])
    chosen = min(s["C"] for s in scores if s["brier_cv"] <= best["brier_cv"] + best["se_folds"])
    return chosen, scores


def bootstrap_pareado(test, p8, p10):
    y = test.target_y.to_numpy()
    diff = (p10-y)**2 - (p8-y)**2
    positions = test.posicion_sesion.to_numpy(dtype=int)
    dense = np.full(positions.max() - positions.min() + 1, np.nan)
    dense[positions - positions.min()] = diff
    n, length = len(dense), 20
    rng = np.random.default_rng(20261029)
    starts = rng.integers(0, n, size=(5000, (n+length-1)//length))
    indices = ((starts[:, :, None] + np.arange(length)) % n).reshape(5000, -1)[:, :n]
    samples = np.nanmean(dense[indices], axis=1)
    return {"delta_brier_10_menos_8": float(diff.mean()), "IC95_bloques": np.quantile(samples, [.025, .975]).tolist(), "replicas": 5000, "longitud_bloque": 20}


def main():
    DIRECTORIO.mkdir(exist_ok=True)
    protocol_path = DIRECTORIO / "protocolo.json"
    if protocol_path.exists():
        saved = json.loads(protocol_path.read_text(encoding="utf-8"))
        if saved["protocolo"] != json.loads(json.dumps(PROTOCOLO)):
            raise ValueError("El protocolo existente difiere; use una nueva version experimental")
    else:
        protocol_path.write_text(json.dumps({"timestamp_registro_utc": timestamp_utc(), "protocolo": PROTOCOLO}, indent=2, ensure_ascii=False), encoding="utf-8")
    protected = [ROOT / n for n in ["serie_ppp_historica_15_emisoras_bmv.csv", "dataset_panel_15_emisoras_features.csv", "registro_senales_prospectivas_walmex.csv", "registro_senales_prospectivas_gmexico.csv"]]
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    fx, cu = descargar_series()
    panel = pd.read_csv(ROOT / "dataset_panel_15_emisoras_features.csv")
    gm = panel[panel.emisora.eq("GMEXICO")].sort_values("posicion_sesion")
    grid = pd.read_csv(ROOT / "serie_ppp_historica_15_emisoras_bmv.csv", usecols=["fecha", "posicion_sesion"]).drop_duplicates().sort_values("posicion_sesion").fecha.tolist()
    dataset = construir_dataset(gm, fx, cu, grid)
    dataset.to_csv(DIRECTORIO / "dataset_experimento.csv", index=False, encoding="utf-8-sig")
    full_train, full_test = seleccionar_train_test(dataset)
    train = full_train[full_train.apto_externo]
    test = full_test[full_test.apto_externo]
    if len(test) < 50:
        raise ValueError("Cobertura Test insuficiente para comparar; no se publican metricas")
    report = {"protocolo": PROTOCOLO, "timestamp_ejecucion_utc": timestamp_utc(), "cobertura": {"train_ppp": len(full_train), "train_pareado": len(train), "test_ppp": len(full_test), "test_pareado": len(test), "exclusiones_train": full_train[~full_train.apto_externo].motivo_externo.value_counts().to_dict(), "exclusiones_test": full_test[~full_test.apto_externo].motivo_externo.value_counts().to_dict()}, "modelos": {}}
    predictions = test[["fecha", "posicion_sesion", "fecha_objetivo_h5", "target_y", "fecha_fuente_ultima"]].copy()
    for name, features in PROTOCOLO["variantes"].items():
        c, cv = seleccionar_c(train, features)
        X, y = train[features].to_numpy(), train.target_y.to_numpy()
        probs, beta = fit_predict_logistic(X, y, test[features].to_numpy(), C=c, balanced=False)
        report["modelos"][name] = {"C_seleccionado": c, "cv_train": cv, "metricas_test": compute_metrics(test.target_y.to_numpy(), probs, float(y.mean())), "parametros_congelados": {"features": features, "coeficientes_con_intercepto": beta.tolist(), "media_train": X.mean(axis=0).tolist(), "escala_train": np.where(X.std(axis=0)==0, 1., X.std(axis=0)).tolist(), "ultima_etiqueta_train": train.fecha_objetivo_h5.max()}}
        predictions[name] = probs
    report["comparacion_pareada"] = bootstrap_pareado(test, predictions.PPP_8.to_numpy(), predictions.PPP_10.to_numpy())
    subperiods = {}
    for name, mask in [("2025", test.fecha < "2026-01-01"), ("2026", test.fecha >= "2026-01-01")]:
        diff = (predictions.PPP_10.to_numpy()-test.target_y.to_numpy())**2 - (predictions.PPP_8.to_numpy()-test.target_y.to_numpy())**2
        subperiods[name] = {"n": int(mask.sum()), "delta_brier": float(diff[mask].mean()) if mask.any() else None}
    report["subperiodos_test"] = subperiods
    comp = report["comparacion_pareada"]
    report["cumple_criterio_exploratorio"] = bool(comp["delta_brier_10_menos_8"] <= -.001 and comp["IC95_bloques"][1] < 0 and all(s["delta_brier"] is not None and s["delta_brier"] < 0 for s in subperiods.values()))
    report["promocion_a_produccion"] = False
    report["decision"] = "REQUIERE_CONFIRMACION_PROSPECTIVA" if report["cumple_criterio_exploratorio"] else "CONSERVAR_BENCHMARK_PPP_NO_PROMOVER_FACTORES"
    report["limitacion_disponibilidad"] = "Rezago conservador aplicado; las tablas actuales no acreditan vintages ni todas las horas historicas de publicacion. Resultado condicionado a esa hipotesis, no validacion point-in-time certificada."
    for p in protected:
        if hashlib.sha256(p.read_bytes()).hexdigest() != hashes[p.name]:
            raise AssertionError(f"El experimento altero el archivo protegido {p.name}")
    report["archivos_protegidos_sha256"] = hashes
    predictions.to_csv(DIRECTORIO / "predicciones_test_pareadas.csv", index=False, encoding="utf-8-sig")
    (DIRECTORIO / "reporte.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"cobertura": report["cobertura"], "modelos": {k: {"C": v["C_seleccionado"], **v["metricas_test"]} for k, v in report["modelos"].items()}, "comparacion": comp, "subperiodos": subperiods}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
