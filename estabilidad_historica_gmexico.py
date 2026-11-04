"""Estabilidad cronologica anidada de GMEXICO exclusivamente dentro de desarrollo."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from investigacion_profunda_gmexico import fit_predict_logistic
from metodologia_ppp import ROOT, CORTE_TRAIN, FEATURE_NAMES, VERSION_FEATURES, mascara_etiquetas_conocidas, timestamp_utc

SALIDA = ROOT / "estabilidad_gmexico_desarrollo"
ENTRADA = ROOT / "experimento_gmexico_macro" / "dataset_experimento.csv"
EXTERNAS = ["usd_mxn_logret_5_lag1", "cobre_logret_5_lag1"]
CS = [.01, .1, 1., 10.]
REGIMENES = ["EXPANSIVA", "MOVIL_3_ANIOS"]
MODELOS = {
    "PPP_COMPLETO": FEATURE_NAMES,
    "PPP_PAREADO": FEATURE_NAMES,
    "PPP_MAS_FACTORES": FEATURE_NAMES + EXTERNAS,
}
MIN_TRAIN, MIN_VAL, MIN_INNER = 100, 20, 2
REPLICAS, BLOQUE, SEMILLA = 5000, 20, 20261029
PROTOCOLO = {
    "version": "ESTABILIDAD_DESARROLLO_GMEXICO_V1",
    "corte_desarrollo": CORTE_TRAIN,
    "alcance": "Solo TRAIN; ni ajuste ni evaluacion sobre TEST o PROSPECTIVA",
    "validacion_externa": "Semestres calendario 2019-H1 a 2025-H1 parcial, etiquetas dentro de cada bloque",
    "regimenes": REGIMENES,
    "modelos": MODELOS,
    "min_train": MIN_TRAIN, "min_validacion": MIN_VAL,
    "seleccion_C": {"candidatos": CS, "validacion_interna": "Semestres anteriores, purgados, contenidos en el Train externo", "min_folds_internos": MIN_INNER, "regla": "Menor C dentro de 1 SE del menor Brier medio interno"},
    "ponderacion_clases": False,
    "regularizacion": "L2; scaler ajustado exclusivamente en cada Train interno/externo",
    "comparacion_factores": "PPP_PAREADO y PPP_MAS_FACTORES utilizan exactamente las mismas fechas Train y validacion",
    "bootstrap": {"replicas": REPLICAS, "bloque_sesiones": BLOQUE, "semilla": SEMILLA, "global": "Estratificado por fold externo, pesos fijos proporcionales a n; sin cruzar fronteras de reentrenamiento"},
    "periodos_insuficientes": "Se reportan sin metricas ni imputacion; la exclusion depende de tamano y elegibilidad, no del resultado",
    "disponibilidad_externa": "Hipotesis de rezago 1 sesion; vintages historicos no certificados",
    "naturaleza": "Diagnostico exploratorio interno; no nueva evidencia prospectiva ni seleccion de ganador en TEST",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preparar_desarrollo(df):
    """Filtra por bloque/origen antes de convertir objetivos o variables: futuro irrelevante."""
    df = df.loc[df.periodo_oficial.eq("TRAIN") & df.fecha.le(CORTE_TRAIN)].copy()
    mask = df.target_disponible.eq(True) & mascara_etiquetas_conocidas(df, CORTE_TRAIN)
    df = df.loc[mask].sort_values("posicion_sesion").reset_index(drop=True)
    if df.empty or df.fecha.duplicated().any():
        raise ValueError("Desarrollo vacio o con fechas duplicadas")
    if not df.version_features.eq(VERSION_FEATURES).all():
        raise ValueError("Se requieren variables PPP canonicas v2")
    for c in FEATURE_NAMES + EXTERNAS + ["target_y", "posicion_sesion"]:
        df[c] = pd.to_numeric(df[c], errors="raise")
    if not df.target_y.isin([0., 1.]).all() or not np.isfinite(df[FEATURE_NAMES].to_numpy()).all():
        raise ValueError("Objetivo o variables PPP invalidos")
    paired = df.apto_externo.eq(True)
    if not np.isfinite(df.loc[paired, EXTERNAS].to_numpy()).all():
        raise ValueError("Factor externo declarado elegible pero ausente")
    if not (df.loc[paired, "fecha_fuente_ultima"] < df.loc[paired, "fecha"]).all():
        raise ValueError("Factor externo contemporaneo o futuro")
    return df


def periodos(inicio, fin):
    """Bloques semestrales fijos, incluso si no existen observaciones en alguno."""
    final = pd.Timestamp(fin)
    starts = pd.date_range(inicio, final, freq="2QS-JAN")
    return [
        (f"{s.year}-H{1 if s.month == 1 else 2}", s.strftime("%Y-%m-%d"), min(s + pd.DateOffset(months=6) - pd.Timedelta(days=1), final).strftime("%Y-%m-%d"))
        for s in starts
    ]


def particion_externa(df, inicio, fin, regimen):
    train = df[(df.fecha < inicio) & (df.fecha_objetivo_h5 < inicio)].copy()
    if regimen == "MOVIL_3_ANIOS":
        limite = (pd.Timestamp(inicio) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
        train = train[train.fecha >= limite]
    elif regimen != "EXPANSIVA":
        raise ValueError("Regimen desconocido")
    val = df[df.fecha.between(inicio, fin) & df.fecha_objetivo_h5.le(fin)].copy()
    return train, val


def particiones_internas(train):
    splits = []
    for name, start, end in periodos("2017-01-01", str(train.fecha_objetivo_h5.max())):
        tr = train[(train.fecha < start) & (train.fecha_objetivo_h5 < start)]
        va = train[train.fecha.between(start, end) & train.fecha_objetivo_h5.le(end)]
        if len(tr) >= MIN_TRAIN and len(va) >= MIN_VAL and tr.target_y.nunique() == 2:
            splits.append((name, tr, va))
    return splits


def ajustar(train, val, features, c):
    X = train[features].to_numpy(dtype=float)
    y = train.target_y.to_numpy(dtype=float)
    ev = val[features].to_numpy(dtype=float)
    probs, beta = fit_predict_logistic(X, y, ev, C=c, balanced=False)
    mu, sig = X.mean(axis=0), X.std(axis=0)
    sig = np.where(sig == 0, 1., sig)
    xs = np.column_stack([np.ones(len(X)), (X-mu)/sig])
    ptr = 1/(1+np.exp(-np.clip(xs@beta, -35, 35)))
    grad = xs.T @ (ptr-y)
    grad[1:] += beta[1:]/c
    if np.max(np.abs(grad)) > 1e-5 or not np.isfinite(probs).all():
        raise RuntimeError("Logistica sin convergencia verificada")
    return probs, beta, mu, sig


def seleccionar_c_anidado(train, features):
    splits = particiones_internas(train)
    if len(splits) < MIN_INNER:
        return None, [], []
    scores = []
    for c in CS:
        losses = []
        for _, tr, va in splits:
            p, _, _, _ = ajustar(tr, va, features, c)
            losses.append(float(np.mean((p-va.target_y.to_numpy())**2)))
        scores.append({"C": c, "brier_medio_interno": float(np.mean(losses)), "se_entre_folds": float(np.std(losses, ddof=1)/np.sqrt(len(losses))), "n_folds_internos": len(losses), "brier_por_fold": losses})
    best = min(scores, key=lambda s: s["brier_medio_interno"])
    selected = min(s["C"] for s in scores if s["brier_medio_interno"] <= best["brier_medio_interno"] + best["se_entre_folds"])
    audit = [{"fold_interno": name, "n_train": len(tr), "n_val": len(va), "fin_etiquetas_train": tr.fecha_objetivo_h5.max(), "inicio_val": va.fecha.min(), "fin_origen_val": va.fecha.max(), "fin_etiquetas_val": va.fecha_objetivo_h5.max()} for name, tr, va in splits]
    return selected, scores, audit


def metricas(y, p, dummy):
    y, p, dummy = np.asarray(y, float), np.asarray(p, float), np.asarray(dummy, float)
    pred = p >= .5
    pos, neg = y == 1, y == 0
    ba = float(.5*(pred[pos].mean() + (~pred[neg]).mean())) if pos.any() and neg.any() else None
    auc = float(((p[pos, None] > p[neg]).sum() + .5*(p[pos, None] == p[neg]).sum())/(pos.sum()*neg.sum())) if pos.any() and neg.any() else None
    loss = (p-y)**2
    dloss = (dummy-y)**2
    pc = np.clip(p, 1e-15, 1-1e-15)
    return {"n": len(y), "n_subida": int(pos.sum()), "n_no_subida": int(neg.sum()), "brier": float(loss.mean()), "brier_dummy": float(dloss.mean()), "brier_constante_05": .25, "delta_brier_vs_dummy": float((loss-dloss).mean()), "brier_skill_vs_dummy": float(1-loss.mean()/dloss.mean()) if dloss.mean() else None, "log_loss": float(-np.mean(y*np.log(pc)+(1-y)*np.log(1-pc))), "balanced_accuracy_pct": ba*100 if ba is not None else None, "accuracy_pct": float(np.mean(pred==y)*100), "roc_auc": auc, "prevalencia_val": float(y.mean()), "prob_media": float(p.mean()), "sesgo_probabilidad": float(p.mean()-y.mean()), "predice_subida_pct": float(pred.mean()*100)}


def muestras_bootstrap(posiciones, diferencias, rng):
    posiciones = np.asarray(posiciones, int)
    dense = np.full(posiciones.max()-posiciones.min()+1, np.nan)
    dense[posiciones-posiciones.min()] = diferencias
    n = len(dense)
    samples, rejected = [], 0
    while sum(len(s) for s in samples) < REPLICAS:
        remaining = REPLICAS - sum(len(s) for s in samples)
        starts = rng.integers(0, n, size=(remaining, (n+BLOQUE-1)//BLOQUE))
        idx = ((starts[:, :, None]+np.arange(BLOQUE)) % n).reshape(remaining, -1)[:, :n]
        sampled = dense[idx]
        counts = np.isfinite(sampled).sum(axis=1)
        valid = counts > 0
        rejected += int((~valid).sum())
        samples.append(np.nansum(sampled[valid], axis=1)/counts[valid])
    return np.concatenate(samples)[:REPLICAS], rejected


def incertidumbre(df, diferencias):
    rng = np.random.default_rng(SEMILLA)
    means = np.zeros(REPLICAS)
    rejected = 0
    diferencias = pd.Series(np.asarray(diferencias), index=df.index)
    for _, group in df.groupby("fold", sort=True):
        boot, discarded = muestras_bootstrap(group.posicion_sesion, diferencias.loc[group.index].to_numpy(), rng)
        means += len(group)/len(df)*boot
        rejected += discarded
    return {"media": float(np.mean(diferencias)), "IC95_bloques": np.quantile(means, [.025, .975]).tolist(), "replicas": REPLICAS, "longitud_bloque_sesiones": BLOQUE, "remuestreos_vacios_descartados": rejected, "condicionamiento": "Predicciones y ajustes congelados; bloques dentro de cada fold; no corrige multiplicidad exploratoria"}


def ejecutar(desarrollo):
    """Recibe solo desarrollo validado; no admite columnas/filas futuras para modelar."""
    if desarrollo.fecha.gt(CORTE_TRAIN).any() or desarrollo.fecha_objetivo_h5.gt(CORTE_TRAIN).any() or not desarrollo.periodo_oficial.eq("TRAIN").all():
        raise ValueError("El analisis solo admite desarrollo con etiquetas conocidas")
    predictions, records, coverage, coefs, searches, inner_audit = [], [], [], [], [], []
    for regime in REGIMENES:
        for fold, start, end in periodos("2019-01-01", CORTE_TRAIN):
            base_tr, base_va = particion_externa(desarrollo, start, end, regime)
            for name, features in MODELOS.items():
                tr, va = base_tr, base_va
                if name != "PPP_COMPLETO":
                    tr, va = tr[tr.apto_externo.eq(True)], va[va.apto_externo.eq(True)]
                header = {"regimen": regime, "fold": fold, "modelo": name, "inicio_bloque": start, "fin_bloque": end}
                cov = {**header, "n_train": len(tr), "n_val": len(va), "n_val_ppp": len(base_va), "exclusiones_externas_val": len(base_va)-len(va), "purga_final_val_ppp": int((desarrollo.fecha.between(start, end) & desarrollo.fecha_objetivo_h5.gt(end)).sum())}
                if len(tr) < MIN_TRAIN or len(va) < MIN_VAL or tr.target_y.nunique() < 2:
                    coverage.append({**cov, "estado": "INSUFICIENTE_MUESTRA"})
                    continue
                c, tuning, audit = seleccionar_c_anidado(tr, features)
                if c is None:
                    coverage.append({**cov, "estado": "INSUFICIENTE_VALIDACION_INTERNA"})
                    continue
                coverage.append({**cov, "estado": "EVALUADO"})
                for score in tuning:
                    searches.append({**header, **score, "seleccionado": score["C"] == c})
                inner_audit.extend({**header, **a} for a in audit)
                p, beta, mu, sig = ajustar(tr, va, features, c)
                prior = float(tr.target_y.mean())
                out = va[["fecha", "posicion_sesion", "fecha_objetivo_h5", "target_y", "fecha_fuente_ultima"]].copy()
                for key, value in header.items():
                    out[key] = value
                out["prob_subida"], out["prob_dummy"], out["C"] = p, prior, c
                out["ultima_etiqueta_train"] = tr.fecha_objetivo_h5.max()
                predictions.append(out)
                stats = metricas(va.target_y.to_numpy(), p, np.full(len(va), prior))
                corr_train = tr.ret_10.corr(tr.target_y)
                corr_val = va.ret_10.corr(va.target_y)
                drift = (va[features].mean().to_numpy()-mu)/sig
                records.append({**header, "C": c, "intercepto": float(beta[0]), "n_train": len(tr), "n_folds_internos": len(audit), "ultima_etiqueta_train": tr.fecha_objetivo_h5.max(), "primera_senal_val": va.fecha.min(), "ultima_senal_val": va.fecha.max(), "ultima_etiqueta_val": va.fecha_objetivo_h5.max(), "prevalencia_train": prior, "corr_ret10_train": float(corr_train) if pd.notna(corr_train) else None, "corr_ret10_val": float(corr_val) if pd.notna(corr_val) else None, "deriva_media_abs_z": float(np.abs(drift).mean()), "deriva_max_abs_z": float(np.abs(drift).max()), **stats})
                for f, b, mean, scale in zip(features, beta[1:], mu, sig):
                    coefs.append({**header, "C": c, "feature": f, "coef_estandarizado": float(b), "media_train": float(mean), "escala_train": float(scale)})
    if not predictions:
        raise ValueError("No hay periodos evaluables")
    pred = pd.concat(predictions, ignore_index=True)
    stats = pd.DataFrame(records)
    comparisons = []
    summaries = []
    for (regime, model), group in pred.groupby(["regimen", "modelo"], sort=False):
        y, p, dummy = group.target_y.to_numpy(), group.prob_subida.to_numpy(), group.prob_dummy.to_numpy()
        lossdiff = (p-y)**2-(dummy-y)**2
        folds = stats[stats.regimen.eq(regime) & stats.modelo.eq(model)]
        summaries.append({"regimen": regime, "modelo": model, **metricas(y, p, dummy), "n_folds": len(folds), "folds_supera_dummy": int(folds.delta_brier_vs_dummy.lt(0).sum()), "folds_ba_mayor_50": int(folds.balanced_accuracy_pct.gt(50).sum()), "brier_medio_no_ponderado_folds": float(folds.brier.mean()), "desviacion_brier_entre_folds": float(folds.brier.std(ddof=1)), "peor_fold": str(folds.loc[folds.brier.idxmax(), "fold"]), "brier_peor_fold": float(folds.brier.max()), "mejor_fold": str(folds.loc[folds.brier.idxmin(), "fold"]), "brier_mejor_fold": float(folds.brier.min()), "C_por_fold": dict(zip(folds.fold, folds.C)), "delta_dummy_incertidumbre": incertidumbre(group, lossdiff)})
    for regime in REGIMENES:
        p8 = pred[pred.regimen.eq(regime) & pred.modelo.eq("PPP_PAREADO")]
        p10 = pred[pred.regimen.eq(regime) & pred.modelo.eq("PPP_MAS_FACTORES")]
        paired = p8.merge(p10, on=["fold", "fecha", "posicion_sesion", "fecha_objetivo_h5", "target_y"], suffixes=("_8", "_10"), validate="one_to_one")
        if len(paired) != len(p8) or len(paired) != len(p10):
            raise AssertionError("Los modelos pareados no tienen las mismas fechas externas")
        if not np.allclose(paired.prob_dummy_8, paired.prob_dummy_10):
            raise AssertionError("Los modelos pareados no usan el mismo entrenamiento")
        for fold, group in [("GLOBAL", paired), *list(paired.groupby("fold", sort=True))]:
            y = group.target_y.to_numpy()
            diff = (group.prob_subida_10.to_numpy()-y)**2-(group.prob_subida_8.to_numpy()-y)**2
            comparisons.append({"regimen": regime, "fold": fold, "n": len(group), "delta_brier_factores_menos_ppp": float(diff.mean()), **incertidumbre(group, diff)})
    return {"predicciones": pred, "metricas_por_periodo": stats, "cobertura_periodos": pd.DataFrame(coverage), "coeficientes": pd.DataFrame(coefs), "busqueda_C_interna": pd.DataFrame(searches), "particiones_internas": pd.DataFrame(inner_audit), "resumen_modelos": summaries, "comparacion_factores": comparisons}


def main():
    SALIDA.mkdir(exist_ok=True)
    proto_path = SALIDA / "protocolo.json"
    if proto_path.exists():
        if json.loads(proto_path.read_text(encoding="utf-8"))["protocolo"] != PROTOCOLO:
            raise ValueError("Cambie de version antes de modificar el protocolo registrado")
    else:
        proto_path.write_text(json.dumps({"timestamp_registro_utc": timestamp_utc(), "protocolo": PROTOCOLO}, indent=2, ensure_ascii=False), encoding="utf-8")
    protected = [ROOT / name for name in ["serie_ppp_historica_15_emisoras_bmv.csv", "dataset_panel_15_emisoras_features.csv", "registro_senales_prospectivas_walmex.csv", "registro_senales_prospectivas_gmexico.csv", "experimento_gmexico_macro/dataset_experimento.csv", "experimento_gmexico_macro/reporte.json", "experimento_gmexico_macro/predicciones_test_pareadas.csv"]]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    dev = preparar_desarrollo(pd.read_csv(ENTRADA))
    dev.to_csv(SALIDA / "desarrollo_utilizado.csv", index=False, encoding="utf-8-sig")
    result = ejecutar(dev)
    for name, frame in result.items():
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(SALIDA / f"{name}.csv", index=False, encoding="utf-8-sig")
    report = {
        "protocolo": PROTOCOLO, "timestamp_ejecucion_utc": timestamp_utc(),
        "desarrollo": {"n_ppp": len(dev), "n_pareado": int(dev.apto_externo.eq(True).sum()), "primera_fecha": dev.fecha.min(), "ultima_fecha_origen": dev.fecha.max(), "ultima_etiqueta": dev.fecha_objetivo_h5.max(), "sha256_subconjunto_desarrollo": hashlib.sha256(dev.to_csv(index=False).encode()).hexdigest()},
        "resumen_modelos": result["resumen_modelos"], "comparacion_factores": result["comparacion_factores"],
        "periodos_insuficientes": result["cobertura_periodos"].loc[lambda d: d.estado.ne("EVALUADO")].to_dict("records"),
        "coeficientes_estabilidad": result["coeficientes"].groupby(["regimen", "modelo", "feature"]).coef_estandarizado.agg(["mean", "std", "min", "max", "count"]).reset_index().to_dict("records"),
        "limitaciones": ["La validacion es anidada pero sigue siendo diagnostico de desarrollo; el diseno general se investigo previamente", "Intervalos condicionados a ajustes, sin correccion por multiples comparaciones", "Huecos y seleccion por presencia en boletin condicionan las sesiones elegibles", "Factores externos conservan la hipotesis de disponibilidad rezagada, sin vintages certificados", "Estabilidad de coeficientes marginales no implica causalidad; hay entradas correlacionadas"],
        "archivos_protegidos_sha256": before,
    }
    for p in protected:
        if sha(p) != before[str(p.relative_to(ROOT))]:
            raise AssertionError(f"Se modifico un archivo protegido: {p.name}")
    (SALIDA / "reporte.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps({"desarrollo": report["desarrollo"], "resumen": [{k: r[k] for k in ["regimen", "modelo", "n", "n_folds", "brier", "brier_dummy", "balanced_accuracy_pct", "folds_supera_dummy", "brier_peor_fold", "peor_fold"]} for r in report["resumen_modelos"]], "comparaciones_globales": [r for r in report["comparacion_factores"] if r["fold"] == "GLOBAL"], "n_periodos_insuficientes": len(report["periodos_insuficientes"])}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
