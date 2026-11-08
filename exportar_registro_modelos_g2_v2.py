"""
Prisma BMV — Fase 6: Exportación de Registro de Modelos G2 v2 (Doble Precisión)
===============================================================================
Genera `registro_modelos_g2_v2.json` con precisión doble completa (`float64`),
incluyendo:
1. Los 5 modelos congelados oficiales (`G2_V1` a `G2_V5`) con sus parámetros
   exactos y hashes SHA-256 canónicos de `registro_modelos_g2_oficial.json`.
2. `G2_V4_ADJ_FASE1` entrenado sobre el panel ajustado por dividendos/splits
   de Fase 1 (`dataset_panel_15_emisoras_features_ajustado_fase1.csv`).
3. `G2_V4_F1_GAP` entrenado sobre el panel enriquecido de Fase 3
   (`dataset_panel_15_emisoras_features_fase3.csv`) incorporando
   `gap_uh_ppp = (ultimo_bmv_mxn - ppp_bmv_mxn) / ppp_bmv_mxn`.
4. `politica_asignacion_capital_fase5` con los hiperparámetros pre-registrados
   de ¼-Kelly y los pesos sugeridos más recientes del portafolio de 5 emisoras.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from experimentos_entrenamiento_desarrollo import escalar_matrices
from higiene_etiquetas_dividendos import _preparar_vista_panel
from metodologia_ppp import CORTE_TRAIN, ROOT, mascara_etiquetas_conocidas
from monitor_prospectivo_segunda_generacion import (
    FECHA_CONGELAMIENTO_G2,
    PANEL_PATH,
    REGISTRO_MODELOS_OFICIAL_PATH,
    VARIABLES_DM5_REL_CUATRO,
    VARIABLES_REL_TRES,
    calcular_sha256_config_modelo,
    hashes_protegidos_g2,
    preparar_panel_entrenamiento_para_corte,
)

REGISTRO_MODELOS_V2_PATH = ROOT / "registro_modelos_g2_v2.json"
PANEL_FASE1_PATH = ROOT / "dataset_panel_15_emisoras_features_ajustado_fase1.csv"
PANEL_FASE3_PATH = ROOT / "dataset_panel_15_emisoras_features_fase3.csv"
REPORTE_FASE5_PATH = ROOT / "reporte_fase5_portafolio.json"

VARIABLES_V4_F1_GAP = [*VARIABLES_DM5_REL_CUATRO, "gap_uh_ppp"]


def extraer_config_pooled_doble_precision(
    tr_df: pd.DataFrame,
    features: list[str],
    c_val: float = 0.01,
    tau_val: float = 0.0,
    estado: str = "SHADOW",
    min_obs_emisora: int = 30,
) -> dict[str, Any]:
    """
    Ajusta el modelo logístico agrupado (Pooled Logit IRLS) con escalamiento
    por emisora en doble precisión y devuelve el diccionario auditable con
    `beta`, `scalers_por_emisora`, `scalers`, `fecha_congelamiento`, `estado`
    y `sha256_config`.
    """
    df_fit = tr_df.copy()
    if tau_val > 0.0 and "ppp_t" in df_fit.columns and "ppp_t5" in df_fit.columns:
        ret_h5 = np.abs(
            df_fit["ppp_t5"].to_numpy(dtype=float) / df_fit["ppp_t"].to_numpy(dtype=float) - 1.0
        )
        df_fit = df_fit[ret_h5 >= float(tau_val)].reset_index(drop=True)

    X_tr_all = df_fit[features].to_numpy(dtype=float)
    y_tr = df_fit["target_y"].to_numpy(dtype=float)
    emisoras_tr = df_fit["emisora"].astype(str).to_numpy()

    _, _, centro_global, escala_global = escalar_matrices(
        X_tr_all, X_tr_all[:1], tipo_scaler="STANDARD"
    )

    X_tr_out = np.zeros_like(X_tr_all, dtype=float)
    scalers_por_emisora: dict[str, dict[str, list[float]]] = {}

    for em in sorted(set(emisoras_tr)):
        mask_em = emisoras_tr == em
        n_em = int(np.sum(mask_em))
        if n_em >= min_obs_emisora:
            X_ref = X_tr_all[mask_em]
            tr_s, _, centro_em, escala_em = escalar_matrices(
                X_ref, X_ref[:1], tipo_scaler="STANDARD"
            )
            X_tr_out[mask_em] = tr_s
            scalers_por_emisora[em] = {
                "mean": [float(x) for x in centro_em],
                "scale": [float(x) for x in escala_em],
            }
        else:
            _, tr_sub_s, _, _ = escalar_matrices(
                X_tr_all, X_tr_all[mask_em], tipo_scaler="STANDARD"
            )
            X_tr_out[mask_em] = tr_sub_s

    n_samples, n_feats = X_tr_out.shape
    X_tr_aug = np.column_stack([np.ones(n_samples), X_tr_out])
    beta = np.zeros(n_feats + 1, dtype=float)
    lambda_val = 1.0 / float(c_val)

    for _ in range(80):
        logits = np.clip(X_tr_aug @ beta, -35.0, 35.0)
        p = 1.0 / (1.0 + np.exp(-logits))
        w_diag = np.maximum(p * (1.0 - p), 1e-12)
        grad = X_tr_aug.T @ (p - y_tr)
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

    cfg: dict[str, Any] = {
        "variables": list(features),
        "c_val": float(c_val),
        "tau_val": float(tau_val),
        "n_train_panel": int(len(df_fit)),
        "fin_etiquetas_train_panel": str(df_fit["fecha_objetivo_h5"].max()),
        "beta": [float(x) for x in beta],
        "scalers_por_emisora": scalers_por_emisora,
        "scaler_global_respaldo": {
            "mean": [float(x) for x in centro_global],
            "scale": [float(x) for x in escala_global],
        },
        "fecha_congelamiento": FECHA_CONGELAMIENTO_G2,
        "estado": estado,
    }
    cfg["sha256_config"] = calcular_sha256_config_modelo(cfg)
    return cfg


def exportar_registro_modelos_g2_v2(
    output_path: Path = REGISTRO_MODELOS_V2_PATH,
) -> dict[str, Any]:
    """
    Exporta `registro_modelos_g2_v2.json` combinando los 5 modelos oficiales
    congelados (`G2_V1`–`G2_V5`) con `G2_V4_ADJ_FASE1`, `G2_V4_F1_GAP` y la
    política de asignación de capital de Fase 5.
    """
    hashes_antes = hashes_protegidos_g2()
    reg_oficial = json.loads(REGISTRO_MODELOS_OFICIAL_PATH.read_text(encoding="utf-8"))

    # Paridad exacta (float64) para V1 y V2 con preparar_panel_entrenamiento_para_corte (N=8122, fin_etiquetas=2025-04-11)
    tr_v1_v2 = preparar_panel_entrenamiento_para_corte(
        PANEL_PATH, "2026-11-05", "TRAIN_CONGELADO"
    )
    reg_oficial["G2_V1_POOLED_REL3_CALIBRADO"] = extraer_config_pooled_doble_precision(
        tr_v1_v2, VARIABLES_REL_TRES, c_val=0.01, tau_val=0.0, estado="SHADOW"
    )
    reg_oficial["G2_V2_POOLED_REL3_ZONA_NEUTRAL"] = extraer_config_pooled_doble_precision(
        tr_v1_v2, VARIABLES_REL_TRES, c_val=0.01, tau_val=0.0025, estado="SHADOW"
    )

    # Preparar vistas ajustadas de Fase 1 y Fase 3
    raw_f3 = pd.read_csv(PANEL_FASE3_PATH, dtype=str)
    vista_f3 = _preparar_vista_panel(raw_f3, usar_ajustado=True)
    vista_f3["gap_uh_ppp"] = pd.to_numeric(raw_f3["gap_uh_ppp"], errors="coerce")

    # 1. Corte TRAIN congelado (<= 2025-04-29) para evaluación estricta en TEST
    mask_tr_congelado = (
        (vista_f3["periodo_oficial"].astype(str) == "TRAIN")
        & (vista_f3["fecha"] <= CORTE_TRAIN)
        & mascara_etiquetas_conocidas(vista_f3, CORTE_TRAIN)
        & (vista_f3["fecha_objetivo_h5"] <= CORTE_TRAIN)
    )
    tr_congelado_f3 = (
        vista_f3[mask_tr_congelado]
        .dropna(subset=[*VARIABLES_V4_F1_GAP, "target_y"])
        .sort_values(["posicion_sesion", "emisora"])
        .reset_index(drop=True)
    )

    # 2. Corte Historia Purgada hasta 2026-10-28 para inferencia prospectiva en vivo
    fecha_corte_prosp = "2026-10-28"
    mask_tr_prosp = (
        (vista_f3["fecha"] < fecha_corte_prosp)
        & mascara_etiquetas_conocidas(vista_f3, fecha_corte_prosp)
        & (vista_f3["fecha_objetivo_h5"] <= fecha_corte_prosp)
    )
    tr_prosp_f3 = (
        vista_f3[mask_tr_prosp]
        .dropna(subset=[*VARIABLES_V4_F1_GAP, "target_y"])
        .sort_values(["posicion_sesion", "emisora"])
        .reset_index(drop=True)
    )

    cfg_v4_adj_prosp = extraer_config_pooled_doble_precision(
        tr_prosp_f3,
        VARIABLES_DM5_REL_CUATRO,
        c_val=0.01,
        tau_val=0.0,
        estado="ACTIVO_CAMPEON_BASE_FASE1",
    )
    cfg_v4_adj_train = extraer_config_pooled_doble_precision(
        tr_congelado_f3,
        VARIABLES_DM5_REL_CUATRO,
        c_val=0.01,
        tau_val=0.0,
        estado="CONGELADO_CORTE_TRAIN_20250429",
    )

    cfg_v4_f1_prosp = extraer_config_pooled_doble_precision(
        tr_prosp_f3,
        VARIABLES_V4_F1_GAP,
        c_val=0.01,
        tau_val=0.0,
        estado="ACTIVO_CAMPEON_FASE3_FASE5",
    )
    cfg_v4_f1_train = extraer_config_pooled_doble_precision(
        tr_congelado_f3,
        VARIABLES_V4_F1_GAP,
        c_val=0.01,
        tau_val=0.0,
        estado="CONGELADO_CORTE_TRAIN_20250429",
    )

    politica_f5: dict[str, Any] = {}
    if REPORTE_FASE5_PATH.exists():
        rep_f5 = json.loads(REPORTE_FASE5_PATH.read_text(encoding="utf-8"))
        est_f1 = rep_f5.get("estrategias", {}).get("G2_V4_F1_GAP_KELLY_250D", {})
        pesos_medios = est_f1.get("peso_medio_por_emisora_pct", {})
        curva_path = ROOT / "curva_equity_fase5_portafolio.csv"
        pesos_ultimo_corte: dict[str, float] = {}
        if curva_path.exists():
            df_curva = pd.read_csv(curva_path)
            if not df_curva.empty:
                ult_c = df_curva.iloc[-1]
                w_sum = 0.0
                for em_k in ["AMX", "FEMSA", "GFNORTE", "GMEXICO", "WALMEX"]:
                    col_w = f"w_f1_{em_k}"
                    val_w = float(ult_c[col_w]) if col_w in ult_c else 0.0
                    pesos_ultimo_corte[em_k] = round(val_w * 100.0, 2)
                    w_sum += val_w
                pesos_ultimo_corte["EFECTIVO"] = round(max(0.0, 1.0 - w_sum) * 100.0, 2)
                pesos_ultimo_corte["fecha_corte"] = str(ult_c.get("fecha", ""))
        politica_f5 = {
            "parametros_pre_registrados": rep_f5.get("parametros_politica", {}),
            "metricas_estrategia_campeona": est_f1,
            "peso_medio_por_emisora_pct": pesos_medios,
            "ultimos_pesos_sugeridos_pct": pesos_ultimo_corte,
        }

    registro_v2: dict[str, Any] = {
        "version_registro": "REGISTRO_MODELOS_G2_V2_DOBLE_PRECISION",
        "fecha_congelamiento_oficial": FECHA_CONGELAMIENTO_G2,
        "modelos_congelados_oficiales": reg_oficial,
        "modelos_fase1_fase3": {
            "G2_V4_ADJ_FASE1": cfg_v4_adj_prosp,
            "G2_V4_ADJ_FASE1_CORTE_TRAIN": cfg_v4_adj_train,
            "G2_V4_F1_GAP": cfg_v4_f1_prosp,
            "G2_V4_F1_GAP_CORTE_TRAIN": cfg_v4_f1_train,
        },
        "politica_asignacion_capital_fase5": politica_f5,
    }

    output_path.write_text(
        json.dumps(registro_v2, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if hashes_antes != hashes_protegidos_g2():
        raise RuntimeError(
            "Se alteró algún archivo protegido durante exportar_registro_modelos_g2_v2."
        )
    return registro_v2


if __name__ == "__main__":
    reg = exportar_registro_modelos_g2_v2()
    print(
        f"Exportado {REGISTRO_MODELOS_V2_PATH.name} con "
        f"{len(reg['modelos_congelados_oficiales'])} modelos oficiales y "
        f"{len(reg['modelos_fase1_fase3'])} configuraciones Fase 1 / Fase 3."
    )
