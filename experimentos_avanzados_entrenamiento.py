from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from calibracion_simplificacion_gmexico import (
    INICIO_EVALUACION_EXTERNA,
    TOLERANCIA_EMPATE_ALPHA,
    VARIABLES_DOS,
    VARIABLES_OCHO,
    preparar_desarrollo_ppp,
)
from estabilidad_historica_gmexico import (
    CS,
    MIN_INNER,
    MIN_TRAIN,
    MIN_VAL,
    incertidumbre,
    metricas,
    particion_externa,
    particiones_internas,
    periodos,
    sha,
)
from experimentos_entrenamiento_desarrollo import (
    ARCHIVOS_PROTEGIDOS_EXTENDIDOS,
    PANEL_PATH,
    VARIABLES_REL_TRES,
    ajustar_logistica_flexible,
    ajustar_logistica_pooled_panel,
    escalar_matrices,
    preparar_panel_desarrollo_ppp,
    seleccionar_c_y_alpha_anidado_generico,
)
from investigacion_profunda_gmexico import fit_predict_logistic
from metodologia_ppp import CORTE_TRAIN, ROOT, timestamp_utc

SALIDA_DIR = ROOT / "experimentos_avanzados_entrenamiento"
VERSION_PROTOCOLO = "EXPERIMENTOS_AVANZADOS_ENTRENAMIENTO_V1"

ARCHIVOS_PROTEGIDOS_AVANZADOS = tuple(
    list(ARCHIVOS_PROTEGIDOS_EXTENDIDOS)
    + [
        ROOT / "experimentos_entrenamiento_desarrollo" / "protocolo.json",
        ROOT / "experimentos_entrenamiento_desarrollo" / "reporte.json",
        ROOT / "experimentos_entrenamiento_desarrollo" / "predicciones.csv",
    ]
)

TAU_GRID = (0.0, 0.0015, 0.0025, 0.0050)
GAMMA_GRID = (0.0, 0.25, 0.50, 0.75, 1.0)
CS_FINO = (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 1.0, 10.0)

REFERENCIAS_Y_PREVIOS = (
    "REF_A_BENCHMARK_8VARS",
    "REF_C_INDIV_2VARS",
    "REF_P4_POOLED_REL3",
    "DUMMY_PREVALENCIA",
    "REFERENCIA_CONSTANTE_05",
)

SERIES_EXP3_ZONA_NEUTRAL = (
    "E3_DZ15_INDIV_2VARS",
    "E3_DZ25_INDIV_2VARS",
    "E3_DZ_ANIDADO_INDIV_2VARS",
    "E3_DZ_ANIDADO_POOLED_REL3",
)

SERIES_EXP4_JERARQUICO = (
    "E4_JERARQ_2VARS",
    "E4_JERARQ_REL3",
    "E4_JERARQ_8VARS_VS_POOLED_REL3",
)

SERIES_EXP5_REGULARIZACION_Y_BALANCEO = (
    "E5_BALANCED_8VARS_C1",
    "E5_BALANCED_8VARS_CANIDADO",
    "E5_CGRID_FINO_INDIV_8VARS",
    "E5_CGRID_FINO_INDIV_2VARS",
    "E5_CGRID_FINO_POOLED_REL3",
)

TODAS_LAS_SERIES = (
    REFERENCIAS_Y_PREVIOS
    + SERIES_EXP3_ZONA_NEUTRAL
    + SERIES_EXP4_JERARQUICO
    + SERIES_EXP5_REGULARIZACION_Y_BALANCEO
)


def hashes_protegidos_avanzados() -> dict[str, str]:
    return {
        str(p.relative_to(ROOT)): sha(p)
        for p in ARCHIVOS_PROTEGIDOS_AVANZADOS
        if p.exists()
    }


def filtrar_zona_neutral_train(
    train_df: pd.DataFrame,
    tau: float,
    min_filas_remanentes: int = 80,
) -> pd.DataFrame:
    """
    Filtra exclusivamente el conjunto de entrenamiento descartando ejemplos cuyo
    retorno absoluto a 5 sesiones |ppp_t5 / ppp_t - 1| es menor a tau.
    Si el filtrado deja menos de min_filas_remanentes o menos de 2 clases,
    conserva el train_df original por seguridad estadistica.
    Jamas se aplica al conjunto de validacion.
    """
    t_val = float(tau)
    if t_val <= 0.0:
        return train_df
    ppp_t = train_df["ppp_t"].to_numpy(dtype=float)
    ppp_t5 = train_df["ppp_t5"].to_numpy(dtype=float)
    mag = np.abs(ppp_t5 / ppp_t - 1.0)
    mask = mag >= t_val
    filtrado = train_df.loc[mask].copy()
    if len(filtrado) < min_filas_remanentes or filtrado["target_y"].nunique() < 2:
        return train_df
    return filtrado


def ajustar_logistica_con_zona_neutral(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    features: list[str],
    c: float,
    tau: float,
    modo_panel: bool = False,
) -> np.ndarray:
    tr_filtrado = filtrar_zona_neutral_train(train_df, tau=tau)
    if not modo_panel:
        p, _, _, _ = ajustar_logistica_flexible(
            tr_filtrado, val_df, features, float(c), tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        return p
    else:
        p, _ = ajustar_logistica_pooled_panel(
            tr_filtrado, val_df, features, float(c), tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        return p


def seleccionar_tau_anidado(
    train_emisora: pd.DataFrame,
    features: list[str],
    c_fijo: float,
    modo_panel: bool = False,
    panel_train_disponible: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Selecciona el umbral de zona neutral tau en {0.0, 0.0015, 0.0025, 0.0050}
    usando exclusivamente validacion interna purgada dentro de Train.
    En caso de empate dentro de 1e-12, prefiere tau = 0.0 (no descartar datos).
    """
    splits = particiones_internas(train_emisora)
    if len(splits) < MIN_INNER:
        raise ValueError("Splits internos insuficientes para seleccionar tau.")

    curva_tau: dict[str, float] = {}
    for tau in TAU_GRID:
        losses: list[float] = []
        for nombre_in, tr_in, va_in in splits:
            if tr_in["fecha_objetivo_h5"].max() >= va_in["fecha"].min():
                raise ValueError(f"Fuga interna en {nombre_in}")
            if not modo_panel:
                p_in = ajustar_logistica_con_zona_neutral(
                    tr_in, va_in, features, c=float(c_fijo), tau=float(tau), modo_panel=False
                )
            else:
                if panel_train_disponible is None:
                    raise ValueError("Se requiere panel_train_disponible para modo_panel=True")
                inicio_in = str(va_in["fecha"].min())
                tr_panel_in = panel_train_disponible[
                    (panel_train_disponible["fecha"] < inicio_in)
                    & (panel_train_disponible["fecha_objetivo_h5"] < inicio_in)
                ].copy()
                p_in = ajustar_logistica_con_zona_neutral(
                    tr_panel_in, va_in, features, c=float(c_fijo), tau=float(tau), modo_panel=True
                )
            y_in = va_in["target_y"].to_numpy(dtype=float)
            losses.append(float(np.mean((p_in - y_in) ** 2)))
        curva_tau[f"{tau:.4f}"] = float(np.mean(losses))

    min_brier = min(curva_tau.values())
    tau_elegido = float(
        min(
            tau
            for tau in TAU_GRID
            if curva_tau[f"{tau:.4f}"] <= min_brier + TOLERANCIA_EMPATE_ALPHA
        )
    )
    return {
        "tau_seleccionado": tau_elegido,
        "curva_brier_tau": curva_tau,
    }


def seleccionar_gamma_jerarquico_anidado(
    train_emisora: pd.DataFrame,
    panel_train_disponible: pd.DataFrame,
    features_indiv: list[str],
    features_panel: list[str],
    c_indiv: float,
    c_panel: float,
) -> dict[str, Any]:
    """
    Selecciona el peso jerarquico gamma en p_mix = gamma * p_indiv + (1 - gamma) * p_panel
    exclusivamente en las particiones internas del pasado de Train externo.
    En caso de empate dentro de 1e-12, prefiere menor gamma (mayor peso al panel de menor varianza).
    """
    splits = particiones_internas(train_emisora)
    if len(splits) < MIN_INNER:
        raise ValueError("Splits internos insuficientes para seleccionar gamma jerarquico.")

    pares_internos: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for nombre_in, tr_in, va_in in splits:
        if tr_in["fecha_objetivo_h5"].max() >= va_in["fecha"].min():
            raise ValueError(f"Fuga interna en {nombre_in}")
        inicio_in = str(va_in["fecha"].min())
        tr_panel_in = panel_train_disponible[
            (panel_train_disponible["fecha"] < inicio_in)
            & (panel_train_disponible["fecha_objetivo_h5"] < inicio_in)
        ].copy()

        p_ind_in, _, _, _ = ajustar_logistica_flexible(
            tr_in, va_in, features_indiv, float(c_indiv), tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        p_pan_in, _ = ajustar_logistica_pooled_panel(
            tr_panel_in, va_in, features_panel, float(c_panel), tipo_scaler="STANDARD", ponderacion="UNIFORME"
        )
        y_in = va_in["target_y"].to_numpy(dtype=float)
        pares_internos.append((p_ind_in, p_pan_in, y_in))

    curva_gamma: dict[str, float] = {}
    for gamma in GAMMA_GRID:
        g = float(gamma)
        losses = [
            float(np.mean(((g * p_i + (1.0 - g) * p_p) - y_i) ** 2))
            for p_i, p_p, y_i in pares_internos
        ]
        curva_gamma[f"{g:.2f}"] = float(np.mean(losses))

    min_brier = min(curva_gamma.values())
    gamma_sel = float(
        min(
            g
            for g in GAMMA_GRID
            if curva_gamma[f"{g:.2f}"] <= min_brier + TOLERANCIA_EMPATE_ALPHA
        )
    )
    return {
        "gamma_seleccionado": gamma_sel,
        "curva_brier_gamma": curva_gamma,
    }


def seleccionar_c_anidado_rejilla_personalizada(
    train_emisora: pd.DataFrame,
    features: list[str],
    rejilla_c: tuple[float, ...] = CS_FINO,
    balanced: bool = False,
    modo_panel: bool = False,
    panel_train_disponible: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Selecciona C en una rejilla personalizada (ej. CS_FINO desde 0.001 hasta 10.0)
    mediante la regla de 1 error estandar en validacion interna purgada.
    Soporta tanto balanced=False como balanced=True.
    """
    splits = particiones_internas(train_emisora)
    if len(splits) < MIN_INNER:
        raise ValueError("Splits internos insuficientes en seleccionar_c_anidado_rejilla_personalizada.")

    scores: list[dict[str, Any]] = []
    for c in rejilla_c:
        losses: list[float] = []
        for nombre_in, tr_in, va_in in splits:
            if tr_in["fecha_objetivo_h5"].max() >= va_in["fecha"].min():
                raise ValueError(f"Fuga interna en {nombre_in}")
            if modo_panel:
                if panel_train_disponible is None:
                    raise ValueError("panel_train_disponible requerido para modo_panel=True")
                inicio_in = str(va_in["fecha"].min())
                tr_panel_in = panel_train_disponible[
                    (panel_train_disponible["fecha"] < inicio_in)
                    & (panel_train_disponible["fecha_objetivo_h5"] < inicio_in)
                ].copy()
                p_in, _ = ajustar_logistica_pooled_panel(
                    tr_panel_in, va_in, features, float(c), tipo_scaler="STANDARD", ponderacion="UNIFORME"
                )
            else:
                X_tr = tr_in[features].to_numpy(dtype=float)
                y_tr = tr_in["target_y"].to_numpy(dtype=float)
                X_ev = va_in[features].to_numpy(dtype=float)
                p_in, _ = fit_predict_logistic(X_tr, y_tr, X_ev, C=float(c), balanced=balanced)
            y_in = va_in["target_y"].to_numpy(dtype=float)
            losses.append(float(np.mean((p_in - y_in) ** 2)))

        scores.append(
            {
                "C": float(c),
                "brier_medio_interno": float(np.mean(losses)),
                "se_entre_folds": float(np.std(losses, ddof=1) / np.sqrt(len(losses))),
            }
        )

    best = min(scores, key=lambda s: s["brier_medio_interno"])
    c_sel = float(
        min(
            s["C"]
            for s in scores
            if s["brier_medio_interno"] <= best["brier_medio_interno"] + best["se_entre_folds"]
        )
    )
    return {
        "c_seleccionado": c_sel,
        "scores_c": scores,
    }


def evaluar_emisora_experimentos_avanzados(
    panel_dev: pd.DataFrame,
    emisora_objetivo: str = "GMEXICO",
) -> dict[str, Any]:
    regimen = "EXPANSIVA"
    dev_em = (
        panel_dev[panel_dev["emisora"].astype(str) == emisora_objetivo]
        .sort_values("posicion_sesion")
        .reset_index(drop=True)
    )
    bloques = periodos(INICIO_EVALUACION_EXTERNA, CORTE_TRAIN)

    filas_periodo: list[dict[str, Any]] = []
    filas_hiperparametros: list[dict[str, Any]] = []
    marcos_predicciones: list[pd.DataFrame] = []

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

        tr_panel_ext = panel_dev[
            (panel_dev["fecha"] < inicio_str) & (panel_dev["fecha_objetivo_h5"] < inicio_str)
        ].copy()

        if tr_ext["fecha_objetivo_h5"].max() >= va_ext["fecha"].min():
            raise ValueError(f"Fuga temporal individual en {fold_nombre}")
        if tr_panel_ext["fecha_objetivo_h5"].max() >= va_ext["fecha"].min():
            raise ValueError(f"Fuga temporal de panel en {fold_nombre}")

        prevalencia_train_ext = float(tr_ext["target_y"].mean())
        y_ext = va_ext["target_y"].to_numpy(dtype=int)

        # ------------------------------------------------------------------
        # 1. Modelos de referencia y base del estudio previo (rejilla estandar CS)
        # ------------------------------------------------------------------
        sel_8_indiv = seleccionar_c_y_alpha_anidado_generico(
            tr_ext, VARIABLES_OCHO, "STANDARD", "UNIFORME", modo_panel=False
        )
        c_8_indiv = float(sel_8_indiv["c_seleccionado"])
        p_ref_a, _, _, _ = ajustar_logistica_flexible(
            tr_ext, va_ext, VARIABLES_OCHO, c_8_indiv, "STANDARD", "UNIFORME"
        )

        sel_2_indiv = seleccionar_c_y_alpha_anidado_generico(
            tr_ext, VARIABLES_DOS, "STANDARD", "UNIFORME", modo_panel=False
        )
        c_2_indiv = float(sel_2_indiv["c_seleccionado"])
        p_ref_c, _, _, _ = ajustar_logistica_flexible(
            tr_ext, va_ext, VARIABLES_DOS, c_2_indiv, "STANDARD", "UNIFORME"
        )

        sel_rel3_indiv = seleccionar_c_y_alpha_anidado_generico(
            tr_ext, VARIABLES_REL_TRES, "STANDARD", "UNIFORME", modo_panel=False
        )
        c_rel3_indiv = float(sel_rel3_indiv["c_seleccionado"])
        p_indiv_rel3, _, _, _ = ajustar_logistica_flexible(
            tr_ext, va_ext, VARIABLES_REL_TRES, c_rel3_indiv, "STANDARD", "UNIFORME"
        )

        sel_2_pool = seleccionar_c_y_alpha_anidado_generico(
            tr_ext, VARIABLES_DOS, "STANDARD", "UNIFORME", modo_panel=True, panel_train_disponible=tr_panel_ext
        )
        c_2_pool = float(sel_2_pool["c_seleccionado"])
        p_pool_2, _ = ajustar_logistica_pooled_panel(
            tr_panel_ext, va_ext, VARIABLES_DOS, c_2_pool, "STANDARD", "UNIFORME"
        )

        sel_rel3_pool = seleccionar_c_y_alpha_anidado_generico(
            tr_ext, VARIABLES_REL_TRES, "STANDARD", "UNIFORME", modo_panel=True, panel_train_disponible=tr_panel_ext
        )
        c_rel3_pool = float(sel_rel3_pool["c_seleccionado"])
        p_ref_p4, _ = ajustar_logistica_pooled_panel(
            tr_panel_ext, va_ext, VARIABLES_REL_TRES, c_rel3_pool, "STANDARD", "UNIFORME"
        )

        # ------------------------------------------------------------------
        # 2. Experimento 3: Zona Neutral (Dead-Zone Training) con pesos uniformes
        # ------------------------------------------------------------------
        p_dz15_2 = ajustar_logistica_con_zona_neutral(
            tr_ext, va_ext, VARIABLES_DOS, c=c_2_indiv, tau=0.0015, modo_panel=False
        )
        p_dz25_2 = ajustar_logistica_con_zona_neutral(
            tr_ext, va_ext, VARIABLES_DOS, c=c_2_indiv, tau=0.0025, modo_panel=False
        )

        info_tau_indiv = seleccionar_tau_anidado(
            tr_ext, VARIABLES_DOS, c_fijo=c_2_indiv, modo_panel=False
        )
        tau_indiv_sel = float(info_tau_indiv["tau_seleccionado"])
        p_dz_anid_2 = ajustar_logistica_con_zona_neutral(
            tr_ext, va_ext, VARIABLES_DOS, c=c_2_indiv, tau=tau_indiv_sel, modo_panel=False
        )

        info_tau_pool = seleccionar_tau_anidado(
            tr_ext, VARIABLES_REL_TRES, c_fijo=c_rel3_pool, modo_panel=True, panel_train_disponible=tr_panel_ext
        )
        tau_pool_sel = float(info_tau_pool["tau_seleccionado"])
        p_dz_anid_pool = ajustar_logistica_con_zona_neutral(
            tr_panel_ext, va_ext, VARIABLES_REL_TRES, c=c_rel3_pool, tau=tau_pool_sel, modo_panel=True
        )

        # ------------------------------------------------------------------
        # 3. Experimento 4: Regularizacion Jerarquica Emisora + Panel
        # ------------------------------------------------------------------
        info_g_2 = seleccionar_gamma_jerarquico_anidado(
            tr_ext, tr_panel_ext, VARIABLES_DOS, VARIABLES_DOS, c_2_indiv, c_2_pool
        )
        g_2_sel = float(info_g_2["gamma_seleccionado"])
        p_jerarq_2 = np.clip(g_2_sel * p_ref_c + (1.0 - g_2_sel) * p_pool_2, 0.0, 1.0)

        info_g_rel3 = seleccionar_gamma_jerarquico_anidado(
            tr_ext, tr_panel_ext, VARIABLES_REL_TRES, VARIABLES_REL_TRES, c_rel3_indiv, c_rel3_pool
        )
        g_rel3_sel = float(info_g_rel3["gamma_seleccionado"])
        p_jerarq_rel3 = np.clip(g_rel3_sel * p_indiv_rel3 + (1.0 - g_rel3_sel) * p_ref_p4, 0.0, 1.0)

        info_g_8_vs_pool = seleccionar_gamma_jerarquico_anidado(
            tr_ext, tr_panel_ext, VARIABLES_OCHO, VARIABLES_REL_TRES, c_8_indiv, c_rel3_pool
        )
        g_8_pool_sel = float(info_g_8_vs_pool["gamma_seleccionado"])
        p_jerarq_8_pool = np.clip(g_8_pool_sel * p_ref_a + (1.0 - g_8_pool_sel) * p_ref_p4, 0.0, 1.0)

        # ------------------------------------------------------------------
        # 4. Experimento 5: Frontera de Regularizacion (CS_FINO) y class_weight='balanced'
        # ------------------------------------------------------------------
        X_tr_8 = tr_ext[VARIABLES_OCHO].to_numpy(dtype=float)
        y_tr_vec = tr_ext["target_y"].to_numpy(dtype=float)
        X_ev_8 = va_ext[VARIABLES_OCHO].to_numpy(dtype=float)

        p_bal_c1, _ = fit_predict_logistic(X_tr_8, y_tr_vec, X_ev_8, C=1.0, balanced=True)

        sel_bal_anid = seleccionar_c_anidado_rejilla_personalizada(
            tr_ext, VARIABLES_OCHO, rejilla_c=tuple(CS), balanced=True, modo_panel=False
        )
        c_bal_sel = float(sel_bal_anid["c_seleccionado"])
        p_bal_canid, _ = fit_predict_logistic(X_tr_8, y_tr_vec, X_ev_8, C=c_bal_sel, balanced=True)

        sel_fino_8 = seleccionar_c_anidado_rejilla_personalizada(
            tr_ext, VARIABLES_OCHO, rejilla_c=CS_FINO, balanced=False, modo_panel=False
        )
        c_fino_8 = float(sel_fino_8["c_seleccionado"])
        p_fino_8, _, _, _ = ajustar_logistica_flexible(
            tr_ext, va_ext, VARIABLES_OCHO, c_fino_8, "STANDARD", "UNIFORME"
        )

        sel_fino_2 = seleccionar_c_anidado_rejilla_personalizada(
            tr_ext, VARIABLES_DOS, rejilla_c=CS_FINO, balanced=False, modo_panel=False
        )
        c_fino_2 = float(sel_fino_2["c_seleccionado"])
        p_fino_2, _, _, _ = ajustar_logistica_flexible(
            tr_ext, va_ext, VARIABLES_DOS, c_fino_2, "STANDARD", "UNIFORME"
        )

        sel_fino_pool = seleccionar_c_anidado_rejilla_personalizada(
            tr_ext, VARIABLES_REL_TRES, rejilla_c=CS_FINO, balanced=False, modo_panel=True, panel_train_disponible=tr_panel_ext
        )
        c_fino_pool = float(sel_fino_pool["c_seleccionado"])
        p_fino_pool, _ = ajustar_logistica_pooled_panel(
            tr_panel_ext, va_ext, VARIABLES_REL_TRES, c_fino_pool, "STANDARD", "UNIFORME"
        )

        p_dummy = np.full(len(va_ext), prevalencia_train_ext, dtype=float)
        p_const_05 = np.full(len(va_ext), 0.5, dtype=float)

        probs_fold: dict[str, np.ndarray] = {
            "REF_A_BENCHMARK_8VARS": p_ref_a,
            "REF_C_INDIV_2VARS": p_ref_c,
            "REF_P4_POOLED_REL3": p_ref_p4,
            "DUMMY_PREVALENCIA": p_dummy,
            "REFERENCIA_CONSTANTE_05": p_const_05,
            "E3_DZ15_INDIV_2VARS": p_dz15_2,
            "E3_DZ25_INDIV_2VARS": p_dz25_2,
            "E3_DZ_ANIDADO_INDIV_2VARS": p_dz_anid_2,
            "E3_DZ_ANIDADO_POOLED_REL3": p_dz_anid_pool,
            "E4_JERARQ_2VARS": p_jerarq_2,
            "E4_JERARQ_REL3": p_jerarq_rel3,
            "E4_JERARQ_8VARS_VS_POOLED_REL3": p_jerarq_8_pool,
            "E5_BALANCED_8VARS_C1": p_bal_c1,
            "E5_BALANCED_8VARS_CANIDADO": p_bal_canid,
            "E5_CGRID_FINO_INDIV_8VARS": p_fino_8,
            "E5_CGRID_FINO_INDIV_2VARS": p_fino_2,
            "E5_CGRID_FINO_POOLED_REL3": p_fino_pool,
        }

        filas_hiperparametros.append(
            {
                "emisora": emisora_objetivo,
                "periodo": fold_nombre,
                "n_train_emisora": int(len(tr_ext)),
                "n_train_panel": int(len(tr_panel_ext)),
                "n_val": int(len(va_ext)),
                "c_estandar_8vars": c_8_indiv,
                "c_estandar_2vars": c_2_indiv,
                "c_estandar_pooled_rel3": c_rel3_pool,
                "tau_anidado_indiv_2vars": tau_indiv_sel,
                "tau_anidado_pooled_rel3": tau_pool_sel,
                "gamma_jerarq_2vars": g_2_sel,
                "gamma_jerarq_rel3": g_rel3_sel,
                "gamma_jerarq_8vars_vs_pooled": g_8_pool_sel,
                "c_balanced_8vars": c_bal_sel,
                "c_fino_indiv_8vars": c_fino_8,
                "c_fino_indiv_2vars": c_fino_2,
                "c_fino_pooled_rel3": c_fino_pool,
            }
        )

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

        brier_a = float(np.mean((p_ref_a - y_ext) ** 2))
        brier_c = float(np.mean((p_ref_c - y_ext) ** 2))
        brier_p4 = float(np.mean((p_ref_p4 - y_ext) ** 2))
        brier_d = float(np.mean((p_dummy - y_ext) ** 2))

        for s_name in TODAS_LAS_SERIES:
            m = metricas(y_ext, probs_fold[s_name], p_dummy)
            filas_periodo.append(
                {
                    "emisora": emisora_objetivo,
                    "regimen": regimen,
                    "variante": s_name,
                    "periodo": fold_nombre,
                    "estado": "EVALUADO",
                    "inicio_bloque": inicio_str,
                    "fin_bloque": fin_str,
                    "n_train_emisora": int(len(tr_ext)),
                    "n_train_panel": int(len(tr_panel_ext)),
                    "n_val": int(len(va_ext)),
                    "purga_final_bloque": purga_final,
                    "prevalencia_train": prevalencia_train_ext,
                    **m,
                    "delta_brier_vs_REF_A_8VARS": float(m["brier"] - brier_a),
                    "delta_brier_vs_REF_C_2VARS": float(m["brier"] - brier_c),
                    "delta_brier_vs_REF_P4_POOLED": float(m["brier"] - brier_p4),
                    "delta_brier_vs_DUMMY": float(m["brier"] - brier_d),
                }
            )

    predicciones = pd.concat(marcos_predicciones, ignore_index=True)
    df_periodo = pd.DataFrame(filas_periodo)
    df_hiper = pd.DataFrame(filas_hiperparametros)

    resumen = resumir_avanzados(predicciones, df_periodo, df_hiper, emisora_objetivo)
    comparaciones = construir_comparaciones_avanzadas(predicciones, df_periodo, emisora_objetivo)

    return {
        "emisora": emisora_objetivo,
        "predicciones": predicciones,
        "metricas_por_periodo": df_periodo,
        "seleccion_hiperparametros": df_hiper,
        "resumen_variantes": resumen,
        "comparaciones_pareadas": comparaciones,
    }


def resumir_avanzados(
    predicciones: pd.DataFrame,
    df_periodo: pd.DataFrame,
    df_hiper: pd.DataFrame,
    emisora: str,
) -> dict[str, dict[str, Any]]:
    y_all = predicciones["target_y"].to_numpy(dtype=int)
    p_a_all = predicciones["prob_REF_A_BENCHMARK_8VARS"].to_numpy(dtype=float)
    p_c_all = predicciones["prob_REF_C_INDIV_2VARS"].to_numpy(dtype=float)
    p_p4_all = predicciones["prob_REF_P4_POOLED_REL3"].to_numpy(dtype=float)
    p_d_all = predicciones["prob_DUMMY_PREVALENCIA"].to_numpy(dtype=float)

    brier_a_all = float(np.mean((p_a_all - y_all) ** 2))
    brier_c_all = float(np.mean((p_c_all - y_all) ** 2))
    brier_p4_all = float(np.mean((p_p4_all - y_all) ** 2))
    brier_d_all = float(np.mean((p_d_all - y_all) ** 2))

    eval_df = df_periodo[df_periodo["estado"] == "EVALUADO"].copy()
    sub_a = eval_df[eval_df["variante"] == "REF_A_BENCHMARK_8VARS"].sort_values("inicio_bloque")
    sub_c = eval_df[eval_df["variante"] == "REF_C_INDIV_2VARS"].sort_values("inicio_bloque")
    sub_p4 = eval_df[eval_df["variante"] == "REF_P4_POOLED_REL3"].sort_values("inicio_bloque")
    sub_d = eval_df[eval_df["variante"] == "DUMMY_PREVALENCIA"].sort_values("inicio_bloque")

    b_a_per = sub_a["brier"].to_numpy(dtype=float)
    b_c_per = sub_c["brier"].to_numpy(dtype=float)
    b_p4_per = sub_p4["brier"].to_numpy(dtype=float)
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
            "variante": var,
            "periodos_evaluados": int(len(sub_per)),
            **m_global,
            "delta_brier_global_vs_REF_A_8VARS": float(m_global["brier"] - brier_a_all),
            "delta_brier_global_vs_REF_C_2VARS": float(m_global["brier"] - brier_c_all),
            "delta_brier_global_vs_REF_P4_POOLED": float(m_global["brier"] - brier_p4_all),
            "delta_brier_global_vs_DUMMY": float(m_global["brier"] - brier_d_all),
            "brier_media_simple_semestral": float(np.mean(b_per)),
            "brier_desv_estandar_semestral": float(np.std(b_per, ddof=1)),
            "peor_periodo": str(peor_fila["periodo"]),
            "peor_periodo_brier": float(peor_fila["brier"]),
            "periodos_mejora_vs_REF_A_8VARS": int(np.sum(b_per < b_a_per - 1e-15)),
            "periodos_mejora_vs_REF_C_2VARS": int(np.sum(b_per < b_c_per - 1e-15)),
            "periodos_mejora_vs_REF_P4_POOLED": int(np.sum(b_per < b_p4_per - 1e-15)),
            "periodos_mejora_vs_DUMMY": int(np.sum(b_per < b_d_per - 1e-15)),
        }

    return resumen


def construir_comparaciones_avanzadas(
    predicciones: pd.DataFrame,
    df_periodo: pd.DataFrame,
    emisora: str,
) -> pd.DataFrame:
    y = predicciones["target_y"].to_numpy(dtype=float)
    eval_df = df_periodo[df_periodo["estado"] == "EVALUADO"].copy()

    pares = [
        # Experimento 3: Zona Neutral
        ("EXP3_ZONA_NEUTRAL", "E3_DZ15_INDIV_2VARS", "REF_C_INDIV_2VARS", "Zona neutral |ret_h5| >= 0.15% frente a 2 variables sin filtrar"),
        ("EXP3_ZONA_NEUTRAL", "E3_DZ25_INDIV_2VARS", "REF_C_INDIV_2VARS", "Zona neutral |ret_h5| >= 0.25% frente a 2 variables sin filtrar"),
        ("EXP3_ZONA_NEUTRAL", "E3_DZ_ANIDADO_INDIV_2VARS", "REF_C_INDIV_2VARS", "Zona neutral con umbral tau anidado frente a 2 variables sin filtrar"),
        ("EXP3_ZONA_NEUTRAL", "E3_DZ_ANIDADO_POOLED_REL3", "REF_P4_POOLED_REL3", "Zona neutral anidada en Pooled Panel frente a Pooled Panel completo"),
        # Experimento 4: Regularizacion Jerarquica Emisora + Panel
        ("EXP4_JERARQUICO", "E4_JERARQ_2VARS", "REF_C_INDIV_2VARS", "Combinacion jerarquica anidada (Indiv + Panel 2 vars) frente a Individual 2 vars"),
        ("EXP4_JERARQUICO", "E4_JERARQ_2VARS", "REF_A_BENCHMARK_8VARS", "Combinacion jerarquica anidada (Indiv + Panel 2 vars) frente a Benchmark 8 vars"),
        ("EXP4_JERARQUICO", "E4_JERARQ_REL3", "REF_C_INDIV_2VARS", "Combinacion jerarquica anidada (Indiv + Panel Rel3) frente a Individual 2 vars"),
        ("EXP4_JERARQUICO", "E4_JERARQ_REL3", "REF_A_BENCHMARK_8VARS", "Combinacion jerarquica anidada (Indiv + Panel Rel3) frente a Benchmark 8 vars"),
        ("EXP4_JERARQUICO", "E4_JERARQ_8VARS_VS_POOLED_REL3", "REF_A_BENCHMARK_8VARS", "Combinacion jerarquica (Benchmark 8 vars + Pooled Rel3) frente a Benchmark 8 vars"),
        ("EXP4_JERARQUICO", "E4_JERARQ_8VARS_VS_POOLED_REL3", "REF_P4_POOLED_REL3", "Combinacion jerarquica (Benchmark 8 vars + Pooled Rel3) frente a Pooled Rel3 puro"),
        # Experimento 5: Frontera de Regularizacion C < 0.01 y class_weight='balanced'
        ("EXP5_REGULARIZACION_Y_BALANCEO", "REF_A_BENCHMARK_8VARS", "E5_BALANCED_8VARS_C1", "Ganancia por eliminar class_weight='balanced' y regularizar frente a V1 clasica (C=1, balanced)"),
        ("EXP5_REGULARIZACION_Y_BALANCEO", "REF_A_BENCHMARK_8VARS", "E5_BALANCED_8VARS_CANIDADO", "Ganancia por eliminar class_weight='balanced' manteniendo C anidado"),
        ("EXP5_REGULARIZACION_Y_BALANCEO", "E5_CGRID_FINO_INDIV_8VARS", "REF_A_BENCHMARK_8VARS", "Desbloqueo de frontera C < 0.01 en 8 variables individuales"),
        ("EXP5_REGULARIZACION_Y_BALANCEO", "E5_CGRID_FINO_INDIV_2VARS", "REF_C_INDIV_2VARS", "Desbloqueo de frontera C < 0.01 en 2 variables individuales"),
        ("EXP5_REGULARIZACION_Y_BALANCEO", "E5_CGRID_FINO_POOLED_REL3", "REF_P4_POOLED_REL3", "Desbloqueo de frontera C < 0.01 en Pooled Panel Rel3"),
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


def ejecutar_experimentos_avanzados(salida_dir: Path = SALIDA_DIR) -> dict[str, Any]:
    hashes_antes = hashes_protegidos_avanzados()
    salida_dir.mkdir(parents=True, exist_ok=True)

    protocolo = {
        "version_protocolo": VERSION_PROTOCOLO,
        "timestamp_registro_utc": timestamp_utc(),
        "alcance": "Exclusivamente TRAIN (<= 2025-04-29); cero uso de TEST o PROSPECTIVA.",
        "experimento_3_zona_neutral": {
            "tau_grid": list(TAU_GRID),
            "regla": "Excluir de Train sesiones con |PPP_{t+5}/PPP_t - 1| < tau manteniendo pesos uniformes w_i=1 y evaluando el 100% de la validacion.",
        },
        "experimento_4_jerarquico": {
            "gamma_grid": list(GAMMA_GRID),
            "regla": "p_mix = gamma * p_indiv + (1 - gamma) * p_panel seleccionado en validacion interna anidada.",
        },
        "experimento_5_regularizacion_y_balanceo": {
            "cs_fino": list(CS_FINO),
            "regla": "Desbloquear C < 0.01 mediante regla 1-SE interna y auditar la penalizacion en Brier de class_weight='balanced'.",
        },
    }
    protocolo_path = salida_dir / "protocolo.json"
    protocolo_path.write_text(
        json.dumps(protocolo, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    panel_dev, resumen_panel = preparar_panel_desarrollo_ppp(PANEL_PATH)

    res_gmex = evaluar_emisora_experimentos_avanzados(panel_dev, "GMEXICO")
    res_walmex = evaluar_emisora_experimentos_avanzados(panel_dev, "WALMEX")

    predicciones_df = pd.concat(
        [res_gmex["predicciones"], res_walmex["predicciones"]], ignore_index=True
    )
    metricas_df = pd.concat(
        [res_gmex["metricas_por_periodo"], res_walmex["metricas_por_periodo"]], ignore_index=True
    )
    hiper_df = pd.concat(
        [res_gmex["seleccion_hiperparametros"], res_walmex["seleccion_hiperparametros"]],
        ignore_index=True,
    )
    comparaciones_df = pd.concat(
        [res_gmex["comparaciones_pareadas"], res_walmex["comparaciones_pareadas"]],
        ignore_index=True,
    )

    predicciones_path = salida_dir / "predicciones.csv"
    metricas_path = salida_dir / "metricas_por_periodo.csv"
    hiper_path = salida_dir / "seleccion_hiperparametros.csv"
    comparaciones_path = salida_dir / "comparaciones_pareadas.csv"

    predicciones_df.to_csv(predicciones_path, index=False)
    metricas_df.to_csv(metricas_path, index=False)
    hiper_df.to_csv(hiper_path, index=False)
    comparaciones_df.to_csv(comparaciones_path, index=False)

    hashes_despues = hashes_protegidos_avanzados()
    if hashes_antes != hashes_despues:
        raise RuntimeError("Se detecto modificacion en archivos protegidos.")

    reporte = {
        "version_protocolo": VERSION_PROTOCOLO,
        "timestamp_ejecucion_utc": timestamp_utc(),
        "sha256_protocolo": sha(protocolo_path),
        "datos_panel_desarrollo": resumen_panel,
        "gmexico_expansiva": {
            "resumen_variantes": res_gmex["resumen_variantes"],
            "comparaciones_pareadas": res_gmex["comparaciones_pareadas"].to_dict(orient="records"),
            "seleccion_hiperparametros": res_gmex["seleccion_hiperparametros"].to_dict(orient="records"),
        },
        "walmex_expansiva": {
            "resumen_variantes": res_walmex["resumen_variantes"],
            "comparaciones_pareadas": res_walmex["comparaciones_pareadas"].to_dict(orient="records"),
            "seleccion_hiperparametros": res_walmex["seleccion_hiperparametros"].to_dict(orient="records"),
        },
        "hashes_archivos_generados": {
            "protocolo.json": sha(protocolo_path),
            "predicciones.csv": sha(predicciones_path),
            "metricas_por_periodo.csv": sha(metricas_path),
            "seleccion_hiperparametros.csv": sha(hiper_path),
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
    rep = ejecutar_experimentos_avanzados()
    print(
        json.dumps(
            {
                "version_protocolo": rep["version_protocolo"],
                "gmexico": {
                    k: {
                        "brier": round(v["brier"], 6),
                        "balanced_accuracy_pct": round(v["balanced_accuracy_pct"], 2),
                        "roc_auc": round(v["roc_auc"], 6),
                    }
                    for k, v in rep["gmexico_expansiva"]["resumen_variantes"].items()
                },
                "walmex": {
                    k: {
                        "brier": round(v["brier"], 6),
                        "balanced_accuracy_pct": round(v["balanced_accuracy_pct"], 2),
                        "roc_auc": round(v["roc_auc"], 6),
                    }
                    for k, v in rep["walmex_expansiva"]["resumen_variantes"].items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
