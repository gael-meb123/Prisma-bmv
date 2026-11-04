from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from calibracion_simplificacion_gmexico import (
    ALPHA_GRID,
    ARCHIVOS_PROTEGIDOS,
    INICIO_EVALUACION_EXTERNA,
    REGLA_SELECCION_ALPHA,
    TOLERANCIA_EMPATE_ALPHA,
    VARIABLES_DOS,
    VARIABLES_OCHO,
    contraer_probabilidad,
    preparar_desarrollo_ppp,
)
from estabilidad_historica_gmexico import (
    BLOQUE,
    CS,
    MIN_INNER,
    MIN_TRAIN,
    MIN_VAL,
    REPLICAS,
    SEMILLA,
    incertidumbre,
    metricas,
    particion_externa,
    particiones_internas,
    periodos,
    sha,
)
from metodologia_ppp import (
    CORTE_TRAIN,
    FEATURE_NAMES,
    ROOT,
    VERSION_FEATURES,
    mascara_etiquetas_conocidas,
    timestamp_utc,
)

PANEL_PATH = ROOT / "dataset_panel_15_emisoras_features.csv"
SALIDA_DIR = ROOT / "experimentos_entrenamiento_desarrollo"
VERSION_PROTOCOLO = "EXPERIMENTOS_ENTRENAMIENTO_DESARROLLO_V1"

ARCHIVOS_PROTEGIDOS_EXTENDIDOS = tuple(
    list(ARCHIVOS_PROTEGIDOS)
    + [
        ROOT / "calibracion_simplificacion_gmexico_desarrollo" / "protocolo.json",
        ROOT / "calibracion_simplificacion_gmexico_desarrollo" / "reporte.json",
        ROOT / "calibracion_simplificacion_gmexico_desarrollo" / "predicciones.csv",
    ]
)

VARIABLES_REL_DOS = ["ret_10_rel_panel", "volatilidad_20"]
VARIABLES_REL_TRES = ["ret_10", "ret_10_rel_panel", "volatilidad_20"]

SERIES_EXP1 = (
    "E1_A_BENCHMARK_8VARS_STD_UNIF",
    "E1_C_BASE_2VARS_STD_UNIF",
    "E1_R_2VARS_ROBUST_UNIF",
    "E1_M_2VARS_STD_MAGWEIGHT",
    "E1_RM_2VARS_ROBUST_MAGWEIGHT",
    "E1_RMC_2VARS_ROBUST_MAG_CONTR05",
)

SERIES_EXP2 = (
    "E2_P1_INDIV_REL2_STD_UNIF",
    "E2_P2_INDIV_REL3_STD_UNIF",
    "E2_P3_POOLED_2VARS_STD_UNIF",
    "E2_P4_POOLED_REL3_STD_UNIF",
    "E2_P5_POOLED_REL3_ROBUST_MAG",
    "E2_P6_POOLED_REL3_CONTR05",
)

REFERENCIAS_BASE = (
    "DUMMY_PREVALENCIA",
    "REFERENCIA_CONSTANTE_05",
)

TODAS_LAS_SERIES = SERIES_EXP1 + SERIES_EXP2 + REFERENCIAS_BASE


def hashes_protegidos_actuales() -> dict[str, str]:
    return {
        str(p.relative_to(ROOT)): sha(p)
        for p in ARCHIVOS_PROTEGIDOS_EXTENDIDOS
        if p.exists()
    }


def calcular_pesos_magnitud_train(train_df: pd.DataFrame) -> np.ndarray:
    """
    Calcula pesos de muestra en TRAIN proporcionales a |ppp_t5 / ppp_t - 1|,
    acotados en [P10, P95] de ese mismo TRAIN y normalizados a media 1.0.
    Jamas observa datos de validacion.
    """
    ppp_t = train_df["ppp_t"].to_numpy(dtype=float)
    ppp_t5 = train_df["ppp_t5"].to_numpy(dtype=float)
    if (ppp_t <= 0).any() or not np.isfinite(ppp_t).all() or not np.isfinite(ppp_t5).all():
        raise ValueError("Precios PPP invalidos en calculo de pesos de magnitud en TRAIN.")
    mag = np.abs(ppp_t5 / ppp_t - 1.0)
    p10 = float(np.percentile(mag, 10.0))
    p95 = float(np.percentile(mag, 95.0))
    clipped = np.clip(mag, max(p10, 1e-6), max(p95, 1e-5))
    mean_w = float(np.mean(clipped))
    if mean_w <= 0.0 or not np.isfinite(mean_w):
        return np.ones(len(train_df), dtype=float)
    w = clipped / mean_w
    return w


def escalar_matrices(
    X_tr: np.ndarray,
    X_ev: np.ndarray,
    tipo_scaler: str = "STANDARD",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Ajusta el escalador exclusivamente sobre X_tr y transforma X_tr y X_ev.
    Soporta:
    - STANDARD: media y desviacion estandar de X_tr.
    - ROBUST: winsorizing [P1, P99] de X_tr + centrado por mediana y escala por IQR (P75 - P25).
    """
    X_tr = np.asarray(X_tr, dtype=float)
    X_ev = np.asarray(X_ev, dtype=float)
    if tipo_scaler == "STANDARD":
        centro = np.mean(X_tr, axis=0)
        escala = np.std(X_tr, axis=0)
        escala = np.where(escala <= 1e-12, 1.0, escala)
        X_tr_s = (X_tr - centro) / escala
        X_ev_s = (X_ev - centro) / escala
        return X_tr_s, X_ev_s, centro, escala
    elif tipo_scaler == "ROBUST":
        p01 = np.percentile(X_tr, 1.0, axis=0)
        p99 = np.percentile(X_tr, 99.0, axis=0)
        X_tr_w = np.clip(X_tr, p01, p99)
        X_ev_w = np.clip(X_ev, p01, p99)
        mediana = np.median(X_tr_w, axis=0)
        q25 = np.percentile(X_tr_w, 25.0, axis=0)
        q75 = np.percentile(X_tr_w, 75.0, axis=0)
        # Escala IQR normalizada (IQR / 1.34898 equivale a 1 sigma bajo normalidad)
        iqr_norm = (q75 - q25) / 1.3489795
        std_fallback = np.std(X_tr_w, axis=0)
        escala = np.where(iqr_norm > 1e-12, iqr_norm, np.where(std_fallback > 1e-12, std_fallback, 1.0))
        X_tr_s = (X_tr_w - mediana) / escala
        X_ev_s = (X_ev_w - mediana) / escala
        return X_tr_s, X_ev_s, mediana, escala
    else:
        raise ValueError(f"Tipo de scaler no soportado: {tipo_scaler}")


def ajustar_logistica_flexible(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    features: list[str],
    c: float,
    tipo_scaler: str = "STANDARD",
    ponderacion: str = "UNIFORME",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Ajusta regresion logistica L2 mediante Newton-Raphson IRLS en NumPy puro
    con verificacion estricta de convergencia de gradiente.
    """
    X_tr = train_df[features].to_numpy(dtype=float)
    y_tr = train_df["target_y"].to_numpy(dtype=float)
    X_ev = val_df[features].to_numpy(dtype=float)

    if ponderacion == "UNIFORME":
        sw = np.ones(len(train_df), dtype=float)
    elif ponderacion == "MAGNITUD":
        sw = calcular_pesos_magnitud_train(train_df)
    else:
        raise ValueError(f"Ponderacion desconocida: {ponderacion}")

    X_tr_s, X_ev_s, centro, escala = escalar_matrices(X_tr, X_ev, tipo_scaler=tipo_scaler)
    n_samples, n_feats = X_tr_s.shape
    X_tr_aug = np.column_stack([np.ones(n_samples), X_tr_s])
    X_ev_aug = np.column_stack([np.ones(len(X_ev_s)), X_ev_s])

    beta = np.zeros(n_feats + 1, dtype=float)
    lambda_val = 1.0 / float(c)

    for _ in range(80):
        logits = np.clip(X_tr_aug @ beta, -35.0, 35.0)
        p = 1.0 / (1.0 + np.exp(-logits))
        w_diag = np.maximum(sw * p * (1.0 - p), 1e-12)

        grad = X_tr_aug.T @ (sw * (p - y_tr))
        grad[1:] += lambda_val * beta[1:]

        H = X_tr_aug.T @ (w_diag[:, None] * X_tr_aug)
        diag_idx = np.diag_indices(len(beta))
        H[diag_idx[0][1:], diag_idx[1][1:]] += lambda_val

        try:
            step = np.linalg.solve(H + 1e-8 * np.eye(len(beta)), grad)
        except np.linalg.LinAlgError:
            break
        beta -= step
        if np.max(np.abs(step)) < 1e-8:
            break

    logits_tr = np.clip(X_tr_aug @ beta, -35.0, 35.0)
    p_tr = 1.0 / (1.0 + np.exp(-logits_tr))
    grad_final = X_tr_aug.T @ (sw * (p_tr - y_tr))
    grad_final[1:] += lambda_val * beta[1:]
    if np.max(np.abs(grad_final)) > 1e-4:
        raise RuntimeError(
            f"Logistica flexible sin convergencia verificada: max|grad|={np.max(np.abs(grad_final))}"
        )

    logits_ev = np.clip(X_ev_aug @ beta, -35.0, 35.0)
    probs_ev = 1.0 / (1.0 + np.exp(-logits_ev))
    if not np.isfinite(probs_ev).all():
        raise RuntimeError("Probabilidades no finitas en ajustar_logistica_flexible.")
    return probs_ev, beta, centro, escala


def preparar_panel_desarrollo_ppp(
    panel_dict_or_df: pd.DataFrame | Path = PANEL_PATH,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Prepara las observaciones elegibles de TRAIN (<= 2025-04-29) de todo el panel
    oficial de 15 emisoras y calcula el retorno relativo intrapanel contemporaneo
    (ret_10_rel_panel) sin usar informacion futura (> t).
    """
    if isinstance(panel_dict_or_df, Path):
        raw = pd.read_csv(panel_dict_or_df, dtype=str)
        panel_fuente = str(panel_dict_or_df.relative_to(ROOT))
        sha_fuente = sha(panel_dict_or_df)
    else:
        raw = panel_dict_or_df.copy()
        panel_fuente = "DATAFRAME_EN_MEMORIA"
        sha_fuente = "MEMORIA"

    raw["fecha"] = pd.to_datetime(raw["fecha"], errors="raise").dt.strftime("%Y-%m-%d")
    # Filtrar estrictamente TRAIN antes de convertir a float para garantizar irrelevancia del futuro
    train_raw = raw[raw["periodo_oficial"].astype(str) == "TRAIN"].copy()
    if (train_raw["fecha"] > CORTE_TRAIN).any():
        raise ValueError("Existen filas marcadas como TRAIN posteriores a CORTE_TRAIN en el panel.")

    train_raw["fecha_objetivo_h5"] = pd.to_datetime(
        train_raw["fecha_objetivo_h5"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    # Para el calculo transversal contemporaneo en fecha t dentro de TRAIN, podemos usar
    # las emisoras con ventana ret_10 valida en la fecha t (que solo depende de <= t).
    for col in VARIABLES_OCHO:
        train_raw[col] = pd.to_numeric(train_raw[col], errors="coerce")

    mask_ventana_t = np.isfinite(train_raw["ret_10"].to_numpy(dtype=float))
    sub_ventana = train_raw[mask_ventana_t].copy()
    media_fecha = (
        sub_ventana.groupby("fecha")["ret_10"]
        .agg(media_ret_10_panel="mean", n_emisoras_fecha="count")
        .reset_index()
    )
    train_raw = train_raw.merge(media_fecha, on="fecha", how="left")
    train_raw["ret_10_rel_panel"] = np.where(
        train_raw["n_emisoras_fecha"].fillna(0) >= 2,
        train_raw["ret_10"] - train_raw["media_ret_10_panel"],
        0.0,
    )

    # Ahora filtrar las observaciones con target_y conocido y vencido <= CORTE_TRAIN
    mask_elegible = (
        train_raw["target_disponible"].astype(str).isin(["True", "true", "1"])
        & mascara_etiquetas_conocidas(train_raw, CORTE_TRAIN)
    )
    panel_dev = train_raw[mask_elegible].copy()
    cols_num = ["posicion_sesion", "ppp_t", "ppp_t5", "target_y", *VARIABLES_OCHO, "ret_10_rel_panel"]
    for col in cols_num:
        panel_dev[col] = pd.to_numeric(panel_dev[col], errors="raise")

    if not np.isfinite(panel_dev[[*VARIABLES_OCHO, "ret_10_rel_panel"]].to_numpy()).all():
        raise ValueError("Valores no finitos en el panel de desarrollo.")
    if not panel_dev["target_y"].isin([0.0, 1.0]).all():
        raise ValueError("Etiquetas invalidas en el panel de desarrollo.")

    panel_dev["target_y"] = panel_dev["target_y"].astype(int)
    panel_dev["posicion_sesion"] = panel_dev["posicion_sesion"].astype(int)
    panel_dev = panel_dev.sort_values(["posicion_sesion", "emisora"]).reset_index(drop=True)

    if (panel_dev["fecha"] > CORTE_TRAIN).any() or (panel_dev["fecha_objetivo_h5"] > CORTE_TRAIN).any():
        raise ValueError("Fuga temporal detectada en panel_dev posterior a CORTE_TRAIN.")

    conteo_emisoras = {
        str(k): int(v) for k, v in panel_dev.groupby("emisora").size().to_dict().items()
    }
    resumen = {
        "panel_fuente": panel_fuente,
        "sha256_panel_fuente": sha_fuente,
        "corte_train": CORTE_TRAIN,
        "total_filas_panel_train_elegibles": int(len(panel_dev)),
        "emisoras_con_muestra_elegible": conteo_emisoras,
        "fecha_min_panel": str(panel_dev["fecha"].min()),
        "fecha_max_panel": str(panel_dev["fecha"].max()),
        "fecha_objetivo_max_panel": str(panel_dev["fecha_objetivo_h5"].max()),
        "prevalencia_global_panel": float(panel_dev["target_y"].mean()),
    }
    return panel_dev, resumen


def estandarizar_panel_por_emisora(
    train_panel: pd.DataFrame,
    val_df: pd.DataFrame,
    features: list[str],
    tipo_scaler: str = "STANDARD",
    min_obs_emisora: int = 30,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Estandariza las variables de cada emisora usando exclusivamente su pasado disponible
    en train_panel. Si una emisora tiene menos de min_obs_emisora en train_panel,
    utiliza los estadisticos globales de train_panel.
    """
    X_tr_all = train_panel[features].to_numpy(dtype=float)
    X_ev_all = val_df[features].to_numpy(dtype=float)

    # Estadisticos globales de respaldo calculados exclusivamente en train_panel
    _, _, _, _ = escalar_matrices(X_tr_all, X_ev_all, tipo_scaler=tipo_scaler)

    X_tr_out = np.zeros_like(X_tr_all, dtype=float)
    X_ev_out = np.zeros_like(X_ev_all, dtype=float)

    emisoras_tr = train_panel["emisora"].astype(str).to_numpy()
    emisoras_ev = val_df["emisora"].astype(str).to_numpy()

    # Pre-ajustar parametros por emisora con >= min_obs_emisora en train_panel
    emisoras_unicas = sorted(set(emisoras_tr) | set(emisoras_ev))
    for em in emisoras_unicas:
        mask_tr = emisoras_tr == em
        mask_ev = emisoras_ev == em
        n_tr_em = int(np.sum(mask_tr))
        if n_tr_em >= min_obs_emisora:
            X_ref = X_tr_all[mask_tr]
        else:
            X_ref = X_tr_all

        if mask_tr.any() and mask_ev.any():
            tr_s, ev_s, _, _ = escalar_matrices(
                X_ref, X_ev_all[mask_ev], tipo_scaler=tipo_scaler
            )
            if n_tr_em >= min_obs_emisora:
                X_tr_out[mask_tr] = tr_s
            else:
                _, tr_sub_s, _, _ = escalar_matrices(
                    X_ref, X_tr_all[mask_tr], tipo_scaler=tipo_scaler
                )
                X_tr_out[mask_tr] = tr_sub_s
            X_ev_out[mask_ev] = ev_s
        elif mask_tr.any():
            if n_tr_em >= min_obs_emisora:
                tr_s, _, _, _ = escalar_matrices(
                    X_ref, X_ref[:1], tipo_scaler=tipo_scaler
                )
                X_tr_out[mask_tr] = tr_s
            else:
                _, tr_sub_s, _, _ = escalar_matrices(
                    X_ref, X_tr_all[mask_tr], tipo_scaler=tipo_scaler
                )
                X_tr_out[mask_tr] = tr_sub_s
        elif mask_ev.any():
            _, ev_s, _, _ = escalar_matrices(
                X_ref, X_ev_all[mask_ev], tipo_scaler=tipo_scaler
            )
            X_ev_out[mask_ev] = ev_s

    return X_tr_out, X_ev_out


def ajustar_logistica_pooled_panel(
    train_panel: pd.DataFrame,
    val_df: pd.DataFrame,
    features: list[str],
    c: float,
    tipo_scaler: str = "STANDARD",
    ponderacion: str = "UNIFORME",
) -> tuple[np.ndarray, np.ndarray]:
    """
    Entrena un modelo logistico mancomunado (Pooled Panel) sobre todas las emisoras
    elegibles en train_panel (purgado temporalmente), estandarizando por emisora dentro
    de train_panel, y predice sobre val_df.
    """
    X_tr_s, X_ev_s = estandarizar_panel_por_emisora(
        train_panel, val_df, features, tipo_scaler=tipo_scaler
    )
    y_tr = train_panel["target_y"].to_numpy(dtype=float)

    if ponderacion == "UNIFORME":
        sw = np.ones(len(train_panel), dtype=float)
    elif ponderacion == "MAGNITUD":
        # Calcular pesos de magnitud por emisora dentro de train_panel para no sesgar hacia emisoras mas volatiles
        sw = np.ones(len(train_panel), dtype=float)
        emisoras_tr = train_panel["emisora"].astype(str).to_numpy()
        for em in sorted(set(emisoras_tr)):
            mask_em = emisoras_tr == em
            if np.sum(mask_em) >= 5:
                sw[mask_em] = calcular_pesos_magnitud_train(train_panel.loc[mask_em])
    else:
        raise ValueError(f"Ponderacion desconocida en panel: {ponderacion}")

    n_samples, n_feats = X_tr_s.shape
    X_tr_aug = np.column_stack([np.ones(n_samples), X_tr_s])
    X_ev_aug = np.column_stack([np.ones(len(X_ev_s)), X_ev_s])

    beta = np.zeros(n_feats + 1, dtype=float)
    # Escalar penalizacion proporcionalmente al tamano relativo del panel frente a una emisora (~7x)
    # o mantener 1/C sobre la suma: evaluamos C en la rejilla anidada {0.01, 0.1, 1.0, 10.0}
    lambda_val = 1.0 / float(c)

    for _ in range(80):
        logits = np.clip(X_tr_aug @ beta, -35.0, 35.0)
        p = 1.0 / (1.0 + np.exp(-logits))
        w_diag = np.maximum(sw * p * (1.0 - p), 1e-12)

        grad = X_tr_aug.T @ (sw * (p - y_tr))
        grad[1:] += lambda_val * beta[1:]

        H = X_tr_aug.T @ (w_diag[:, None] * X_tr_aug)
        diag_idx = np.diag_indices(len(beta))
        H[diag_idx[0][1:], diag_idx[1][1:]] += lambda_val

        try:
            step = np.linalg.solve(H + 1e-8 * np.eye(len(beta)), grad)
        except np.linalg.LinAlgError:
            break
        beta -= step
        if np.max(np.abs(step)) < 1e-8:
            break

    logits_tr = np.clip(X_tr_aug @ beta, -35.0, 35.0)
    p_tr = 1.0 / (1.0 + np.exp(-logits_tr))
    grad_final = X_tr_aug.T @ (sw * (p_tr - y_tr))
    grad_final[1:] += lambda_val * beta[1:]
    if np.max(np.abs(grad_final)) > 1e-4:
        raise RuntimeError(
            f"Logistica pooled panel sin convergencia verificada: max|grad|={np.max(np.abs(grad_final))}"
        )

    logits_ev = np.clip(X_ev_aug @ beta, -35.0, 35.0)
    probs_ev = 1.0 / (1.0 + np.exp(-logits_ev))
    return probs_ev, beta


def seleccionar_c_y_alpha_anidado_generico(
    train_emisora: pd.DataFrame,
    features: list[str],
    tipo_scaler: str = "STANDARD",
    ponderacion: str = "UNIFORME",
    modo_panel: bool = False,
    panel_train_disponible: pd.DataFrame | None = None,
    regimen: str = "EXPANSIVA",
) -> dict[str, Any]:
    """
    Selecciona C en {0.01, 0.1, 1.0, 10.0} (regla de 1 error estandar prefiriendo menor C)
    y alpha en {0.0, 0.25, 0.50, 0.75, 1.0} (minimo Brier medio interno hacia 0.5)
    usando exclusivamente particiones internas contenidas en el pasado del Train externo.
    """
    splits = particiones_internas(train_emisora)
    if len(splits) < MIN_INNER:
        raise ValueError(f"Splits internos insuficientes ({len(splits)} < {MIN_INNER}).")

    scores_c: list[dict[str, Any]] = []
    predicciones_por_c: dict[float, list[tuple[np.ndarray, np.ndarray]]] = {}

    for c in CS:
        losses: list[float] = []
        preds_c: list[tuple[np.ndarray, np.ndarray]] = []
        for nombre_in, tr_in, va_in in splits:
            if tr_in["fecha_objetivo_h5"].max() >= va_in["fecha"].min():
                raise ValueError(f"Fuga temporal interna en {nombre_in}")

            if not modo_panel:
                p_in, _, _, _ = ajustar_logistica_flexible(
                    tr_in,
                    va_in,
                    features,
                    float(c),
                    tipo_scaler=tipo_scaler,
                    ponderacion=ponderacion,
                )
            else:
                if panel_train_disponible is None:
                    raise ValueError("Se requiere panel_train_disponible para modo_panel=True.")
                inicio_in = str(va_in["fecha"].min())
                tr_panel_in = panel_train_disponible[
                    (panel_train_disponible["fecha"] < inicio_in)
                    & (panel_train_disponible["fecha_objetivo_h5"] < inicio_in)
                ].copy()
                if regimen == "MOVIL_3_ANIOS":
                    limite = (pd.Timestamp(inicio_in) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
                    tr_panel_in = tr_panel_in[tr_panel_in["fecha"] >= limite]
                if tr_panel_in["fecha_objetivo_h5"].max() >= inicio_in:
                    raise ValueError(f"Fuga temporal de panel en split interno {nombre_in}")
                p_in, _ = ajustar_logistica_pooled_panel(
                    tr_panel_in,
                    va_in,
                    features,
                    float(c),
                    tipo_scaler=tipo_scaler,
                    ponderacion=ponderacion,
                )

            y_in = va_in["target_y"].to_numpy(dtype=float)
            losses.append(float(np.mean((p_in - y_in) ** 2)))
            preds_c.append((p_in, y_in))

        predicciones_por_c[float(c)] = preds_c
        scores_c.append(
            {
                "C": float(c),
                "brier_medio_interno": float(np.mean(losses)),
                "se_entre_folds": float(np.std(losses, ddof=1) / np.sqrt(len(losses))),
                "n_folds_internos": int(len(losses)),
            }
        )

    best = min(scores_c, key=lambda s: s["brier_medio_interno"])
    c_sel = float(
        min(
            s["C"]
            for s in scores_c
            if s["brier_medio_interno"] <= best["brier_medio_interno"] + best["se_entre_folds"]
        )
    )

    # Seleccionar alpha para el C elegido hacia p_ref = 0.5
    preds_elegidas = predicciones_por_c[c_sel]
    curva_alpha: dict[str, float] = {}
    for alpha in ALPHA_GRID:
        losses_a = [
            float(np.mean((contraer_probabilidad(p_in, 0.5, alpha) - y_in) ** 2))
            for p_in, y_in in preds_elegidas
        ]
        curva_alpha[f"{alpha:.2f}"] = float(np.mean(losses_a))

    min_brier_a = min(curva_alpha.values())
    alpha_sel = float(
        min(
            alpha
            for alpha in ALPHA_GRID
            if curva_alpha[f"{alpha:.2f}"] <= min_brier_a + TOLERANCIA_EMPATE_ALPHA
        )
    )

    return {
        "c_seleccionado": c_sel,
        "alpha_seleccionado_05": alpha_sel,
        "scores_c": scores_c,
        "curva_alpha_05": curva_alpha,
        "n_splits_internos": int(len(splits)),
    }


def evaluar_emisora_experimentos(
    panel_dev: pd.DataFrame,
    emisora_objetivo: str = "GMEXICO",
    regimen: str = "EXPANSIVA",
) -> dict[str, Any]:
    """
    Ejecuta simultaneamente los Experimentos 1 y 2 sobre la emisora objetivo
    en los 12 semestres de validacion externa dentro de TRAIN (<= 2025-04-29).
    """
    dev_em = (
        panel_dev[panel_dev["emisora"].astype(str) == emisora_objetivo]
        .sort_values("posicion_sesion")
        .reset_index(drop=True)
    )
    bloques = periodos(INICIO_EVALUACION_EXTERNA, CORTE_TRAIN)

    filas_periodo: list[dict[str, Any]] = []
    filas_seleccion: list[dict[str, Any]] = []
    marcos_predicciones: list[pd.DataFrame] = []

    especificaciones_modelos = [
        # Experimento 1: Funcion de perdida (Magnitud) y Escalado Robusto (Individual)
        ("E1_A_BENCHMARK_8VARS_STD_UNIF", VARIABLES_OCHO, "STANDARD", "UNIFORME", False, False),
        ("E1_C_BASE_2VARS_STD_UNIF", VARIABLES_DOS, "STANDARD", "UNIFORME", False, False),
        ("E1_R_2VARS_ROBUST_UNIF", VARIABLES_DOS, "ROBUST", "UNIFORME", False, False),
        ("E1_M_2VARS_STD_MAGWEIGHT", VARIABLES_DOS, "STANDARD", "MAGNITUD", False, False),
        ("E1_RM_2VARS_ROBUST_MAGWEIGHT", VARIABLES_DOS, "ROBUST", "MAGNITUD", False, False),
        ("E1_RMC_2VARS_ROBUST_MAG_CONTR05", VARIABLES_DOS, "ROBUST", "MAGNITUD", False, True),
        # Experimento 2: Entrenamiento en Panel (Pooled) y Retorno Relativo Intrapanel
        ("E2_P1_INDIV_REL2_STD_UNIF", VARIABLES_REL_DOS, "STANDARD", "UNIFORME", False, False),
        ("E2_P2_INDIV_REL3_STD_UNIF", VARIABLES_REL_TRES, "STANDARD", "UNIFORME", False, False),
        ("E2_P3_POOLED_2VARS_STD_UNIF", VARIABLES_DOS, "STANDARD", "UNIFORME", True, False),
        ("E2_P4_POOLED_REL3_STD_UNIF", VARIABLES_REL_TRES, "STANDARD", "UNIFORME", True, False),
        ("E2_P5_POOLED_REL3_ROBUST_MAG", VARIABLES_REL_TRES, "ROBUST", "MAGNITUD", True, False),
        ("E2_P6_POOLED_REL3_CONTR05", VARIABLES_REL_TRES, "STANDARD", "UNIFORME", True, True),
    ]

    for fold_nombre, inicio_str, fin_str in bloques:
        tr_ext, va_ext = particion_externa(dev_em, inicio_str, fin_str, regimen)
        purga_final = int(
            (dev_em["fecha"].between(inicio_str, fin_str) & dev_em["fecha_objetivo_h5"].gt(fin_str)).sum()
        )

        if len(tr_ext) < MIN_TRAIN or len(va_ext) < MIN_VAL or tr_ext["target_y"].nunique() < 2:
            filas_periodo.append(
                {
                    "emisora": emisora_objetivo,
                    "regimen": regimen,
                    "variante": "TODAS",
                    "periodo": fold_nombre,
                    "estado": "INSUFICIENTE_MUESTRA",
                    "inicio_bloque": inicio_str,
                    "fin_bloque": fin_str,
                    "n_train_emisora": int(len(tr_ext)),
                    "n_val": int(len(va_ext)),
                    "purga_final_bloque": purga_final,
                }
            )
            continue

        # Purga estricta para el panel mancomunado en el corte inicio_str
        tr_panel_ext = panel_dev[
            (panel_dev["fecha"] < inicio_str) & (panel_dev["fecha_objetivo_h5"] < inicio_str)
        ].copy()
        if regimen == "MOVIL_3_ANIOS":
            limite = (pd.Timestamp(inicio_str) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
            tr_panel_ext = tr_panel_ext[tr_panel_ext["fecha"] >= limite]

        if tr_ext["fecha_objetivo_h5"].max() >= va_ext["fecha"].min():
            raise ValueError(f"Fuga temporal individual en {fold_nombre}")
        if tr_panel_ext["fecha_objetivo_h5"].max() >= va_ext["fecha"].min():
            raise ValueError(f"Fuga temporal de panel en {fold_nombre}")
        if va_ext["fecha_objetivo_h5"].max() > fin_str:
            raise ValueError(f"Violacion de purga final en {fold_nombre}")

        prevalencia_train_ext = float(tr_ext["target_y"].mean())
        y_ext = va_ext["target_y"].to_numpy(dtype=int)

        probs_fold: dict[str, np.ndarray] = {}
        meta_fold: dict[str, dict[str, Any]] = {}

        # Cachear ajustes que comparten exactamente la misma configuracion base (ej. RM y RMC, o P4 y P6)
        cache_base: dict[tuple[tuple[str, ...], str, str, bool], dict[str, Any]] = {}

        for (
            nombre_var,
            lista_vars,
            scaler_t,
            pond_t,
            es_panel,
            usa_contraccion,
        ) in especificaciones_modelos:
            clave_base = (tuple(lista_vars), scaler_t, pond_t, es_panel)
            if clave_base not in cache_base:
                sel = seleccionar_c_y_alpha_anidado_generico(
                    train_emisora=tr_ext,
                    features=lista_vars,
                    tipo_scaler=scaler_t,
                    ponderacion=pond_t,
                    modo_panel=es_panel,
                    panel_train_disponible=tr_panel_ext if es_panel else None,
                    regimen=regimen,
                )
                c_sel = float(sel["c_seleccionado"])
                alpha_sel = float(sel["alpha_seleccionado_05"])
                if not es_panel:
                    p_raw, beta, _, _ = ajustar_logistica_flexible(
                        tr_ext,
                        va_ext,
                        lista_vars,
                        c_sel,
                        tipo_scaler=scaler_t,
                        ponderacion=pond_t,
                    )
                    n_tr_usado = int(len(tr_ext))
                else:
                    p_raw, beta = ajustar_logistica_pooled_panel(
                        tr_panel_ext,
                        va_ext,
                        lista_vars,
                        c_sel,
                        tipo_scaler=scaler_t,
                        ponderacion=pond_t,
                    )
                    n_tr_usado = int(len(tr_panel_ext))

                cache_base[clave_base] = {
                    "c_seleccionado": c_sel,
                    "alpha_seleccionado_05": alpha_sel,
                    "p_raw": p_raw,
                    "beta": beta,
                    "n_train_usado": n_tr_usado,
                    "curva_alpha_05": sel["curva_alpha_05"],
                    "scores_c": sel["scores_c"],
                }

            base_info = cache_base[clave_base]
            c_val = base_info["c_seleccionado"]
            alpha_val = base_info["alpha_seleccionado_05"] if usa_contraccion else 1.0
            p_final = (
                contraer_probabilidad(base_info["p_raw"], 0.5, alpha_val)
                if usa_contraccion
                else base_info["p_raw"]
            )
            probs_fold[nombre_var] = p_final
            meta_fold[nombre_var] = {
                "c_seleccionado": c_val,
                "alpha_seleccionado": alpha_val,
                "n_train_usado": base_info["n_train_usado"],
                "scaler": scaler_t,
                "ponderacion": pond_t,
                "modo_panel": es_panel,
                "usa_contraccion": usa_contraccion,
                "variables": ",".join(lista_vars),
            }

            filas_seleccion.append(
                {
                    "emisora": emisora_objetivo,
                    "regimen": regimen,
                    "periodo": fold_nombre,
                    "variante": nombre_var,
                    "variables": ",".join(lista_vars),
                    "scaler": scaler_t,
                    "ponderacion": pond_t,
                    "modo_panel": es_panel,
                    "usa_contraccion": usa_contraccion,
                    "n_train_emisora": int(len(tr_ext)),
                    "n_train_efectivo": int(base_info["n_train_usado"]),
                    "n_val": int(len(va_ext)),
                    "c_seleccionado": c_val,
                    "alpha_seleccionado": alpha_val,
                }
            )

        p_dummy = np.full(len(va_ext), prevalencia_train_ext, dtype=float)
        p_const_05 = np.full(len(va_ext), 0.5, dtype=float)
        probs_fold["DUMMY_PREVALENCIA"] = p_dummy
        probs_fold["REFERENCIA_CONSTANTE_05"] = p_const_05
        meta_fold["DUMMY_PREVALENCIA"] = {
            "c_seleccionado": np.nan,
            "alpha_seleccionado": 0.0,
            "n_train_usado": int(len(tr_ext)),
            "scaler": "NINGUNO",
            "ponderacion": "NINGUNA",
            "modo_panel": False,
            "usa_contraccion": False,
            "variables": "0VARS",
        }
        meta_fold["REFERENCIA_CONSTANTE_05"] = {
            "c_seleccionado": np.nan,
            "alpha_seleccionado": 0.0,
            "n_train_usado": int(len(tr_ext)),
            "scaler": "NINGUNO",
            "ponderacion": "NINGUNA",
            "modo_panel": False,
            "usa_contraccion": False,
            "variables": "0VARS",
        }

        pred_cols: dict[str, Any] = {
            "emisora": emisora_objetivo,
            "regimen": regimen,
            "fold": fold_nombre,
            "periodo": fold_nombre,
            "fecha": va_ext["fecha"].to_numpy(),
            "fecha_objetivo_h5": va_ext["fecha_objetivo_h5"].to_numpy(),
            "posicion_sesion": va_ext["posicion_sesion"].to_numpy(dtype=int),
            "ppp_t": va_ext["ppp_t"].to_numpy(dtype=float),
            "ppp_t5": va_ext["ppp_t5"].to_numpy(dtype=float),
            "target_y": y_ext,
            "n_train_emisora": int(len(tr_ext)),
            "n_train_panel": int(len(tr_panel_ext)),
            "prevalencia_train": prevalencia_train_ext,
        }
        for s_name in TODAS_LAS_SERIES:
            pred_cols[f"prob_{s_name}"] = probs_fold[s_name]
        marcos_predicciones.append(pd.DataFrame(pred_cols))

        brier_bench_a = float(np.mean((probs_fold["E1_A_BENCHMARK_8VARS_STD_UNIF"] - y_ext) ** 2))
        brier_base_c = float(np.mean((probs_fold["E1_C_BASE_2VARS_STD_UNIF"] - y_ext) ** 2))
        brier_dummy = float(np.mean((p_dummy - y_ext) ** 2))

        for s_name in TODAS_LAS_SERIES:
            m = metricas(y_ext, probs_fold[s_name], p_dummy)
            info_m = meta_fold[s_name]
            filas_periodo.append(
                {
                    "emisora": emisora_objetivo,
                    "regimen": regimen,
                    "variante": s_name,
                    "variables": info_m["variables"],
                    "scaler": info_m["scaler"],
                    "ponderacion": info_m["ponderacion"],
                    "modo_panel": info_m["modo_panel"],
                    "usa_contraccion": info_m["usa_contraccion"],
                    "periodo": fold_nombre,
                    "estado": "EVALUADO",
                    "inicio_bloque": inicio_str,
                    "fin_bloque": fin_str,
                    "n_train_emisora": int(len(tr_ext)),
                    "n_train_efectivo": int(info_m["n_train_usado"]),
                    "n_val": int(len(va_ext)),
                    "purga_final_bloque": purga_final,
                    "prevalencia_train": prevalencia_train_ext,
                    "c_seleccionado": info_m["c_seleccionado"],
                    "alpha_seleccionado": info_m["alpha_seleccionado"],
                    **m,
                    "delta_brier_vs_BENCHMARK_8VARS": float(m["brier"] - brier_bench_a),
                    "delta_brier_vs_BASE_2VARS": float(m["brier"] - brier_base_c),
                    "delta_brier_vs_DUMMY": float(m["brier"] - brier_dummy),
                }
            )

    predicciones = pd.concat(marcos_predicciones, ignore_index=True)
    df_periodo = pd.DataFrame(filas_periodo)
    df_seleccion = pd.DataFrame(filas_seleccion)

    resumen = resumir_resultados_emisora(predicciones, df_periodo, emisora_objetivo, regimen)
    comparaciones = construir_comparaciones_experimentos(
        predicciones, df_periodo, emisora_objetivo, regimen
    )

    return {
        "emisora": emisora_objetivo,
        "regimen": regimen,
        "predicciones": predicciones,
        "metricas_por_periodo": df_periodo,
        "seleccion_hiperparametros": df_seleccion,
        "resumen_variantes": resumen,
        "comparaciones_pareadas": comparaciones,
    }


def resumir_resultados_emisora(
    predicciones: pd.DataFrame,
    df_periodo: pd.DataFrame,
    emisora: str,
    regimen: str,
) -> dict[str, dict[str, Any]]:
    y_all = predicciones["target_y"].to_numpy(dtype=int)
    p_a_all = predicciones["prob_E1_A_BENCHMARK_8VARS_STD_UNIF"].to_numpy(dtype=float)
    p_c_all = predicciones["prob_E1_C_BASE_2VARS_STD_UNIF"].to_numpy(dtype=float)
    p_d_all = predicciones["prob_DUMMY_PREVALENCIA"].to_numpy(dtype=float)
    p_05_all = predicciones["prob_REFERENCIA_CONSTANTE_05"].to_numpy(dtype=float)

    brier_a_all = float(np.mean((p_a_all - y_all) ** 2))
    brier_c_all = float(np.mean((p_c_all - y_all) ** 2))
    brier_d_all = float(np.mean((p_d_all - y_all) ** 2))
    brier_05_all = float(np.mean((p_05_all - y_all) ** 2))

    eval_df = df_periodo[df_periodo["estado"] == "EVALUADO"].copy()
    sub_a = eval_df[eval_df["variante"] == "E1_A_BENCHMARK_8VARS_STD_UNIF"].sort_values("inicio_bloque")
    sub_c = eval_df[eval_df["variante"] == "E1_C_BASE_2VARS_STD_UNIF"].sort_values("inicio_bloque")
    sub_d = eval_df[eval_df["variante"] == "DUMMY_PREVALENCIA"].sort_values("inicio_bloque")

    b_a_per = sub_a["brier"].to_numpy(dtype=float)
    b_c_per = sub_c["brier"].to_numpy(dtype=float)
    b_d_per = sub_d["brier"].to_numpy(dtype=float)

    resumen: dict[str, dict[str, Any]] = {}
    for var in TODAS_LAS_SERIES:
        p_all = predicciones[f"prob_{var}"].to_numpy(dtype=float)
        m_global = metricas(y_all, p_all, p_d_all)

        sub_per = eval_df[eval_df["variante"] == var].sort_values("inicio_bloque")
        b_per = sub_per["brier"].to_numpy(dtype=float)
        idx_peor = int(np.argmax(b_per))
        peor_fila = sub_per.iloc[idx_peor]

        resumen[var] = {
            "emisora": emisora,
            "regimen": regimen,
            "variante": var,
            "periodos_evaluados": int(len(sub_per)),
            "periodos_insuficientes": int((df_periodo["estado"] == "INSUFICIENTE_MUESTRA").sum()),
            **m_global,
            "delta_brier_global_vs_BENCHMARK_8VARS": float(m_global["brier"] - brier_a_all),
            "delta_brier_global_vs_BASE_2VARS": float(m_global["brier"] - brier_c_all),
            "delta_brier_global_vs_DUMMY": float(m_global["brier"] - brier_d_all),
            "delta_brier_global_vs_CONSTANTE_05": float(m_global["brier"] - brier_05_all),
            "brier_media_simple_semestral": float(np.mean(b_per)),
            "brier_desv_estandar_semestral": float(np.std(b_per, ddof=1)),
            "peor_periodo": str(peor_fila["periodo"]),
            "peor_periodo_brier": float(peor_fila["brier"]),
            "periodos_mejora_vs_BENCHMARK_8VARS": int(np.sum(b_per < b_a_per - 1e-15)),
            "periodos_mejora_vs_BASE_2VARS": int(np.sum(b_per < b_c_per - 1e-15)),
            "periodos_mejora_vs_DUMMY": int(np.sum(b_per < b_d_per - 1e-15)),
        }
    return resumen


def construir_comparaciones_experimentos(
    predicciones: pd.DataFrame,
    df_periodo: pd.DataFrame,
    emisora: str,
    regimen: str,
) -> pd.DataFrame:
    y = predicciones["target_y"].to_numpy(dtype=float)
    eval_df = df_periodo[df_periodo["estado"] == "EVALUADO"].copy()

    pares = [
        # Experimento 1 vs Benchmark 8 variables y vs Base 2 variables
        ("EXP1_ESCALADO_Y_PESOS", "E1_R_2VARS_ROBUST_UNIF", "E1_C_BASE_2VARS_STD_UNIF", "Efecto del RobustScaler frente a StandardScaler en 2 variables"),
        ("EXP1_ESCALADO_Y_PESOS", "E1_M_2VARS_STD_MAGWEIGHT", "E1_C_BASE_2VARS_STD_UNIF", "Efecto de ponderar muestras por magnitud de retorno en 2 variables"),
        ("EXP1_ESCALADO_Y_PESOS", "E1_RM_2VARS_ROBUST_MAGWEIGHT", "E1_C_BASE_2VARS_STD_UNIF", "Efecto combinado de RobustScaler + ponderacion por magnitud frente a 2 variables base"),
        ("EXP1_ESCALADO_Y_PESOS", "E1_RM_2VARS_ROBUST_MAGWEIGHT", "E1_A_BENCHMARK_8VARS_STD_UNIF", "RobustScaler + ponderacion por magnitud (2 vars) frente al Benchmark de 8 variables"),
        ("EXP1_ESCALADO_Y_PESOS", "E1_RMC_2VARS_ROBUST_MAG_CONTR05", "E1_A_BENCHMARK_8VARS_STD_UNIF", "RobustScaler + magnitud + contraccion 0.5 frente al Benchmark de 8 variables"),
        # Experimento 2: Panel Mancomunado y Retorno Relativo Intrapanel
        ("EXP2_PANEL_Y_RELATIVO", "E2_P1_INDIV_REL2_STD_UNIF", "E1_C_BASE_2VARS_STD_UNIF", "Sustituir ret_10 por retorno relativo intrapanel (entrenamiento individual)"),
        ("EXP2_PANEL_Y_RELATIVO", "E2_P2_INDIV_REL3_STD_UNIF", "E1_C_BASE_2VARS_STD_UNIF", "Anadir retorno relativo intrapanel (3 vars, entrenamiento individual)"),
        ("EXP2_PANEL_Y_RELATIVO", "E2_P3_POOLED_2VARS_STD_UNIF", "E1_C_BASE_2VARS_STD_UNIF", "Entrenamiento en panel mancomunado (Pooled Panel) frente a individual en 2 variables"),
        ("EXP2_PANEL_Y_RELATIVO", "E2_P3_POOLED_2VARS_STD_UNIF", "E1_A_BENCHMARK_8VARS_STD_UNIF", "Pooled Panel (2 vars) frente al Benchmark individual de 8 variables"),
        ("EXP2_PANEL_Y_RELATIVO", "E2_P4_POOLED_REL3_STD_UNIF", "E1_C_BASE_2VARS_STD_UNIF", "Pooled Panel con retorno relativo intrapanel frente a 2 variables individual"),
        ("EXP2_PANEL_Y_RELATIVO", "E2_P4_POOLED_REL3_STD_UNIF", "E1_A_BENCHMARK_8VARS_STD_UNIF", "Pooled Panel con retorno relativo intrapanel frente al Benchmark de 8 variables"),
        ("EXP2_PANEL_Y_RELATIVO", "E2_P5_POOLED_REL3_ROBUST_MAG", "E1_A_BENCHMARK_8VARS_STD_UNIF", "Fusion Exp1+Exp2 (Pooled + Relativo + Robust + Magnitud) frente al Benchmark 8 vars"),
        ("EXP2_PANEL_Y_RELATIVO", "E2_P6_POOLED_REL3_CONTR05", "E1_A_BENCHMARK_8VARS_STD_UNIF", "Pooled Panel + Relativo + Contraccion 0.5 frente al Benchmark 8 vars"),
    ]

    filas: list[dict[str, Any]] = []
    for familia, cand, ref, desc in pares:
        p_cand = predicciones[f"prob_{cand}"].to_numpy(dtype=float)
        p_ref = predicciones[f"prob_{ref}"].to_numpy(dtype=float)
        loss_cand = (p_cand - y) ** 2
        loss_ref = (p_ref - y) ** 2
        diff_vec = loss_cand - loss_ref

        info_b = incertidumbre(predicciones, diff_vec)
        ic_low, ic_high = float(info_b["IC95_bloques"][0]), float(info_b["IC95_bloques"][1])

        sub_cand = eval_df[eval_df["variante"] == cand].sort_values("inicio_bloque")
        sub_ref = eval_df[eval_df["variante"] == ref].sort_values("inicio_bloque")
        b_c_per = sub_cand["brier"].to_numpy(dtype=float)
        b_r_per = sub_ref["brier"].to_numpy(dtype=float)

        filas.append(
            {
                "emisora": emisora,
                "regimen": regimen,
                "familia_experimento": familia,
                "comparacion": f"{cand}_vs_{ref}",
                "variante_candidata": cand,
                "variante_referencia": ref,
                "descripcion": desc,
                "brier_candidata": float(np.mean(loss_cand)),
                "brier_referencia": float(np.mean(loss_ref)),
                "delta_brier_observado": float(info_b["media"]),
                "ic95_bajo": ic_low,
                "ic95_alto": ic_high,
                "ic95_incluye_cero": bool(ic_low <= 0.0 <= ic_high),
                "periodos_mejora_estricta": int(np.sum(b_c_per < b_r_per - 1e-15)),
                "periodos_empate": int(np.sum(np.isclose(b_c_per, b_r_per, atol=1e-15))),
                "periodos_empeora": int(np.sum(b_c_per > b_r_per + 1e-15)),
                "total_periodos_evaluados": int(len(b_c_per)),
            }
        )
    return pd.DataFrame(filas)


def ejecutar_experimentos_aislados(salida_dir: Path = SALIDA_DIR) -> dict[str, Any]:
    hashes_antes = hashes_protegidos_actuales()
    salida_dir.mkdir(parents=True, exist_ok=True)

    protocolo = {
        "version_protocolo": VERSION_PROTOCOLO,
        "timestamp_registro_utc": timestamp_utc(),
        "alcance": "Exclusivamente TRAIN (<= 2025-04-29); cero uso de TEST o PROSPECTIVA.",
        "experimento_1": {
            "nombre": "Ponderacion por Magnitud de Retorno + Escalado Robusto (RobustScaler)",
            "series": list(SERIES_EXP1),
            "regla_pesos": "w_i proporcional a |PPP_{t+5}/PPP_t - 1| acotado en [P10, P95] de Train y normalizado a media 1.0.",
            "regla_scaler_robusto": "Winsorizing [P1, P99] de Train + centrado por mediana y escala por IQR normalizado de Train.",
        },
        "experimento_2": {
            "nombre": "Entrenamiento en Panel Mancomunado (Pooled Panel) + Retorno Relativo Intrapanel",
            "series": list(SERIES_EXP2),
            "regla_retorno_relativo": "ret_10_rel_panel = ret_10_{i,t} - media_transversal(ret_10_{panel,t}) usando solo emisoras publicadas en la misma fecha t.",
            "regla_purga_panel": "Toda observacion del panel en Train cumple fecha < inicio_val y fecha_objetivo_h5 < inicio_val.",
            "regla_estandarizacion_panel": "Estandarizacion por emisora dentro de cada ventana de Train (con respaldo global si n_emisora < 30).",
        },
    }
    protocolo_path = salida_dir / "protocolo.json"
    protocolo_path.write_text(
        json.dumps(protocolo, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    panel_dev, resumen_panel = preparar_panel_desarrollo_ppp(PANEL_PATH)
    _, resumen_gmex = preparar_desarrollo_ppp(PANEL_PATH)

    # Evaluacion principal sobre GMEXICO (EXPANSIVA y sensibilidad MOVIL_3_ANIOS)
    res_gmex_exp = evaluar_emisora_experimentos(panel_dev, "GMEXICO", "EXPANSIVA")
    res_gmex_mov = evaluar_emisora_experimentos(panel_dev, "GMEXICO", "MOVIL_3_ANIOS")

    # Evaluacion cruzada adicional en desarrollo sobre WALMEX (EXPANSIVA) para verificar consistencia multiemisora
    res_walmex_exp = evaluar_emisora_experimentos(panel_dev, "WALMEX", "EXPANSIVA")

    predicciones_df = pd.concat(
        [
            res_gmex_exp["predicciones"],
            res_gmex_mov["predicciones"],
            res_walmex_exp["predicciones"],
        ],
        ignore_index=True,
    )
    metricas_df = pd.concat(
        [
            res_gmex_exp["metricas_por_periodo"],
            res_gmex_mov["metricas_por_periodo"],
            res_walmex_exp["metricas_por_periodo"],
        ],
        ignore_index=True,
    )
    seleccion_df = pd.concat(
        [
            res_gmex_exp["seleccion_hiperparametros"],
            res_gmex_mov["seleccion_hiperparametros"],
            res_walmex_exp["seleccion_hiperparametros"],
        ],
        ignore_index=True,
    )
    comparaciones_df = pd.concat(
        [
            res_gmex_exp["comparaciones_pareadas"],
            res_gmex_mov["comparaciones_pareadas"],
            res_walmex_exp["comparaciones_pareadas"],
        ],
        ignore_index=True,
    )

    predicciones_path = salida_dir / "predicciones.csv"
    metricas_path = salida_dir / "metricas_por_periodo.csv"
    seleccion_path = salida_dir / "seleccion_hiperparametros.csv"
    comparaciones_path = salida_dir / "comparaciones_pareadas.csv"

    predicciones_df.to_csv(predicciones_path, index=False)
    metricas_df.to_csv(metricas_path, index=False)
    seleccion_df.to_csv(seleccion_path, index=False)
    comparaciones_df.to_csv(comparaciones_path, index=False)

    hashes_despues = hashes_protegidos_actuales()
    if hashes_antes != hashes_despues:
        raise RuntimeError(
            "Se detecto una modificacion en archivos protegidos durante experimentos_entrenamiento_desarrollo."
        )

    reporte = {
        "version_protocolo": VERSION_PROTOCOLO,
        "timestamp_ejecucion_utc": timestamp_utc(),
        "sha256_protocolo": sha(protocolo_path),
        "datos_panel_desarrollo": resumen_panel,
        "datos_gmexico_desarrollo": resumen_gmex,
        "gmexico_expansiva": {
            "resumen_variantes": res_gmex_exp["resumen_variantes"],
            "comparaciones_pareadas": res_gmex_exp["comparaciones_pareadas"].to_dict(orient="records"),
        },
        "gmexico_movil_3_anios": {
            "resumen_variantes": res_gmex_mov["resumen_variantes"],
            "comparaciones_pareadas": res_gmex_mov["comparaciones_pareadas"].to_dict(orient="records"),
        },
        "walmex_expansiva_validacion_cruzada": {
            "resumen_variantes": res_walmex_exp["resumen_variantes"],
            "comparaciones_pareadas": res_walmex_exp["comparaciones_pareadas"].to_dict(orient="records"),
        },
        "hashes_archivos_generados": {
            "protocolo.json": sha(protocolo_path),
            "predicciones.csv": sha(predicciones_path),
            "metricas_por_periodo.csv": sha(metricas_path),
            "seleccion_hiperparametros.csv": sha(seleccion_path),
            "comparaciones_pareadas.csv": sha(comparaciones_path),
        },
        "hashes_archivos_protegidos_verificados": hashes_despues,
        "integridad_archivos_protegidos_intacta": True,
    }
    reporte_path = salida_dir / "reporte.json"
    reporte_path.write_text(
        json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return reporte


if __name__ == "__main__":
    rep = ejecutar_experimentos_aislados()
    print(
        json.dumps(
            {
                "version_protocolo": rep["version_protocolo"],
                "gmexico_expansiva_brier": {
                    k: {
                        "brier": round(v["brier"], 6),
                        "balanced_accuracy_pct": round(v["balanced_accuracy_pct"], 2),
                        "roc_auc": round(v["roc_auc"], 6),
                    }
                    for k, v in rep["gmexico_expansiva"]["resumen_variantes"].items()
                },
                "walmex_expansiva_brier": {
                    k: {
                        "brier": round(v["brier"], 6),
                        "balanced_accuracy_pct": round(v["balanced_accuracy_pct"], 2),
                        "roc_auc": round(v["roc_auc"], 6),
                    }
                    for k, v in rep["walmex_expansiva_validacion_cruzada"]["resumen_variantes"].items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
