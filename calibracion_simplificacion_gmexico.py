from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from estabilidad_historica_gmexico import (
    BLOQUE,
    CS,
    MIN_INNER,
    MIN_TRAIN,
    MIN_VAL,
    REPLICAS,
    SEMILLA,
    ajustar,
    incertidumbre,
    metricas,
    particion_externa,
    particiones_internas,
    periodos,
    seleccionar_c_anidado,
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
SALIDA_DIR = ROOT / "calibracion_simplificacion_gmexico_desarrollo"

VERSION_PROTOCOLO = "CALIBRACION_SIMPLIFICACION_GMEXICO_V1"
INICIO_EVALUACION_EXTERNA = "2019-01-01"
INICIO_VALIDACION_INTERNA = "2017-01-01"

VARIABLES_OCHO = list(FEATURE_NAMES)
VARIABLES_DOS = ["ret_10", "volatilidad_20"]

ALPHA_GRID = (0.0, 0.25, 0.50, 0.75, 1.0)
TOLERANCIA_EMPATE_ALPHA = 1e-12
REGLA_SELECCION_ALPHA = (
    "MIN_BRIER_MEDIO_INTERNO_CON_DESEMPATE_ALPHA_MENOR_MAS_CONSERVADOR"
)

VARIANTES_PRINCIPALES = (
    "A_8VARS_ORIG",
    "B_8VARS_CONTR_05",
    "C_2VARS_ORIG",
    "D_2VARS_CONTR_05",
)
VARIANTES_SENSIBILIDAD_REF = (
    "B_SENS_8VARS_CONTR_PREV",
    "D_SENS_2VARS_CONTR_PREV",
)
REFERENCIAS_BASE = (
    "DUMMY_PREVALENCIA",
    "REFERENCIA_CONSTANTE_05",
)
TODAS_LAS_SERIES = (
    VARIANTES_PRINCIPALES + VARIANTES_SENSIBILIDAD_REF + REFERENCIAS_BASE
)

INTERVALOS_CALIBRACION_5 = (
    ("B1_MENOR_045", 0.0, 0.45, False),
    ("B2_045_A_0485", 0.45, 0.485, False),
    ("B3_0485_A_0515", 0.485, 0.515, False),
    ("B4_0515_A_055", 0.515, 0.55, False),
    ("B5_055_A_100", 0.55, 1.0, True),
)
INTERVALOS_CALIBRACION_3 = (
    ("T1_BAJA_MENOR_048", 0.0, 0.48, False),
    ("T2_NEUTRA_048_A_052", 0.48, 0.52, True),
    ("T3_ALTA_MAYOR_052", 0.52, 1.0, True),
)
MIN_N_CELDA_CONFIABLE = 30

ARCHIVOS_PROTEGIDOS = (
    ROOT / "serie_ppp_historica_15_emisoras_bmv.csv",
    ROOT / "dataset_panel_15_emisoras_features.csv",
    ROOT / "registro_senales_prospectivas_walmex.csv",
    ROOT / "registro_senales_prospectivas_gmexico.csv",
    ROOT / "experimento_gmexico_macro" / "dataset_experimento.csv",
    ROOT / "experimento_gmexico_macro" / "reporte.json",
    ROOT / "experimento_gmexico_macro" / "predicciones_test_pareadas.csv",
    ROOT / "estabilidad_gmexico_desarrollo" / "protocolo.json",
    ROOT / "estabilidad_gmexico_desarrollo" / "reporte.json",
    ROOT / "estabilidad_gmexico_desarrollo" / "predicciones.csv",
    ROOT / "estabilidad_gmexico_desarrollo" / "metricas_por_periodo.csv",
)


def hashes_protegidos() -> dict[str, str]:
    return {
        str(p.relative_to(ROOT)): sha(p)
        for p in ARCHIVOS_PROTEGIDOS
        if p.exists()
    }


def contraer_probabilidad(
    p_modelo: np.ndarray | float,
    p_referencia: np.ndarray | float,
    alpha: float,
) -> np.ndarray:
    a = float(alpha)
    if a < 0.0 or a > 1.0:
        raise ValueError(f"alpha fuera de [0, 1]: {alpha}")
    pm = np.asarray(p_modelo, dtype=float)
    pr = np.asarray(p_referencia, dtype=float)
    pf = a * pm + (1.0 - a) * pr
    return np.clip(pf, 0.0, 1.0)


def preparar_desarrollo_ppp(panel_dict_or_df: pd.DataFrame | Path = PANEL_PATH) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Filtra exclusivamente GMEXICO y TRAIN antes de convertir variables/objetivo a float."""
    if isinstance(panel_dict_or_df, Path):
        raw = pd.read_csv(panel_dict_or_df, dtype=str)
        panel_fuente = str(panel_dict_or_df.relative_to(ROOT))
        sha_fuente = sha(panel_dict_or_df)
    else:
        raw = panel_dict_or_df.copy()
        panel_fuente = "DATAFRAME_EN_MEMORIA"
        sha_fuente = "MEMORIA"

    gmex = raw[raw["emisora"].astype(str) == "GMEXICO"].copy()
    gmex["fecha"] = pd.to_datetime(gmex["fecha"], errors="raise").dt.strftime("%Y-%m-%d")
    gmex = gmex.sort_values("fecha").reset_index(drop=True)

    # Aislar exclusivamente TRAIN antes de convertir features o etiquetas a float
    train_raw = gmex[gmex["periodo_oficial"].astype(str) == "TRAIN"].copy()
    if (train_raw["fecha"] > CORTE_TRAIN).any():
        raise ValueError("Existen filas marcadas como TRAIN posteriores a CORTE_TRAIN.")

    train_raw["fecha_objetivo_h5"] = pd.to_datetime(
        train_raw["fecha_objetivo_h5"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    mask_elegible = (
        train_raw["target_disponible"].astype(str).isin(["True", "true", "1"])
        & mascara_etiquetas_conocidas(train_raw, CORTE_TRAIN)
    )
    dev = train_raw[mask_elegible].copy()
    if dev.empty or dev["fecha"].duplicated().any():
        raise ValueError("Desarrollo vacio o con fechas duplicadas.")
    if not dev["version_features"].astype(str).eq(VERSION_FEATURES).all():
        raise ValueError("Se requieren variables PPP canonicas v2.")

    cols_num = ["posicion_sesion", "ppp_t", "ppp_t5", "target_y", *VARIABLES_OCHO]
    for col in cols_num:
        dev[col] = pd.to_numeric(dev[col], errors="raise")

    if not np.isfinite(dev[VARIABLES_OCHO].to_numpy()).all():
        raise ValueError("Existen valores no finitos en las 8 variables PPP de desarrollo.")
    if not dev["target_y"].isin([0.0, 1.0]).all():
        raise ValueError("Etiquetas target_y invalidas en el subconjunto de desarrollo.")

    dev["target_y"] = dev["target_y"].astype(int)
    dev["posicion_sesion"] = dev["posicion_sesion"].astype(int)
    dev = dev.sort_values("posicion_sesion").reset_index(drop=True)

    if (dev["fecha"] > CORTE_TRAIN).any():
        raise ValueError("Fuga detectada: fecha > CORTE_TRAIN en desarrollo.")
    if (dev["fecha_objetivo_h5"] > CORTE_TRAIN).any():
        raise ValueError("Fuga detectada: fecha_objetivo_h5 > CORTE_TRAIN en desarrollo.")

    cols_canonicas = [
        "fecha",
        "posicion_sesion",
        "emisora",
        "serie",
        "sector_economico",
        "anillo_madurez",
        "ppp_t",
        *VARIABLES_OCHO,
        "fecha_objetivo_h5",
        "ppp_t5",
        "target_disponible",
        "target_y",
        "periodo_oficial",
        "version_features",
    ]
    canon = dev[cols_canonicas].copy()
    sha_canon = hashlib.sha256(
        canon.to_csv(index=False, lineterminator="\n").encode("utf-8")
    ).hexdigest()

    resumen = {
        "panel_fuente": panel_fuente,
        "sha256_panel_fuente": sha_fuente,
        "sha256_desarrollo_ppp_canonico": sha_canon,
        "version_features": VERSION_FEATURES,
        "corte_train": CORTE_TRAIN,
        "total_sesiones_gmexico_panel": int(len(gmex)),
        "total_sesiones_train_gmexico": int(len(train_raw)),
        "filas_desarrollo_ppp_elegibles": int(len(dev)),
        "fecha_min_desarrollo": str(dev["fecha"].min()),
        "fecha_max_desarrollo": str(dev["fecha"].max()),
        "fecha_objetivo_max_desarrollo": str(dev["fecha_objetivo_h5"].max()),
        "prevalencia_global_desarrollo": float(dev["target_y"].mean()),
        "total_subidas_desarrollo": int((dev["target_y"] == 1).sum()),
        "total_bajadas_o_igual_desarrollo": int((dev["target_y"] == 0).sum()),
    }
    return dev, resumen


def construir_protocolo_preregistrado() -> dict[str, Any]:
    return {
        "version_protocolo": VERSION_PROTOCOLO,
        "naturaleza_estudio": (
            "Investigacion exploratoria controlada post-hoc sobre el periodo de desarrollo "
            "TRAIN (<= 2025-04-29), utilizando exactamente la cobertura PPP completa "
            "(1,167 ejemplos elegibles y 803 predicciones externas en 12 semestres evaluables)."
        ),
        "reglas_estrictas": {
            "corte_train": CORTE_TRAIN,
            "uso_test_o_prospectiva": False,
            "incorporacion_variables_externas": False,
            "cobertura_ppp_completa": True,
            "calibradores_post_hoc_adicionales": False,
        },
        "conjuntos_variables": {
            "OCHO_VARIABLES": VARIABLES_OCHO,
            "DOS_VARIABLES_PREDEFINIDAS": VARIABLES_DOS,
        },
        "variantes_principales": {
            "A_8VARS_ORIG": {
                "variables": VARIABLES_OCHO,
                "tratamiento_probabilistico": "ORIGINAL_ALPHA_1",
                "referencia_contraccion": None,
            },
            "B_8VARS_CONTR_05": {
                "variables": VARIABLES_OCHO,
                "tratamiento_probabilistico": "CONTRACCION_LINEAL_ANIDADA",
                "referencia_contraccion": "CONSTANTE_05",
            },
            "C_2VARS_ORIG": {
                "variables": VARIABLES_DOS,
                "tratamiento_probabilistico": "ORIGINAL_ALPHA_1",
                "referencia_contraccion": None,
            },
            "D_2VARS_CONTR_05": {
                "variables": VARIABLES_DOS,
                "tratamiento_probabilistico": "CONTRACCION_LINEAL_ANIDADA",
                "referencia_contraccion": "CONSTANTE_05",
            },
        },
        "sensibilidades_secundarias_predefinidas": {
            "referencia_contraccion_prevalencia_train": [
                "B_SENS_8VARS_CONTR_PREV",
                "D_SENS_2VARS_CONTR_PREV",
            ],
            "regimen_entrenamiento_secundario": "MOVIL_3_ANIOS",
        },
        "procedimiento_anidado_por_fold_externo": {
            "paso_1": "Construir particiones semestrales internas purgadas exclusivamente con el pasado de Train externo (inicio >= 2017-01-01, n_train >= 100, n_val >= 20).",
            "paso_2": "Seleccionar C en {0.01, 0.1, 1.0, 10.0} mediante regla de 1 error estandar sobre el Brier medio interno (prefiriendo menor C / mayor regularizacion).",
            "paso_3": "Obtener las probabilidades de validacion interna fuera de muestra correspondientes exactamente al C seleccionado.",
            "paso_4": "Evaluar la rejilla fija alpha en {0.0, 0.25, 0.50, 0.75, 1.0} sobre esas probabilidades internas y seleccionar alpha que minimice el Brier medio de validacion interna; en caso de empate dentro de 1e-12, elegir el menor alpha (mas conservador).",
            "paso_5": "Reentrenar una sola vez el modelo logistico L2 sin ponderacion de clases sobre el Train externo completo con el C seleccionado.",
            "paso_6": "Aplicar el alpha seleccionado a las probabilidades del bloque externo sin observar sus etiquetas, compartiendo exactamente el mismo modelo base y C entre la version original y la contraida.",
        },
        "rejilla_c": list(CS),
        "rejilla_alpha": list(ALPHA_GRID),
        "regla_seleccion_alpha": REGLA_SELECCION_ALPHA,
        "tolerancia_empate_alpha": TOLERANCIA_EMPATE_ALPHA,
        "bootstrap_bloques": {
            "semilla": SEMILLA,
            "total_replicas": REPLICAS,
            "tamano_bloque_sesiones_bmv": BLOQUE,
            "estratificado_por_periodo_externo": True,
        },
        "intervalos_diagnostico_calibracion": {
            "esquema_5_bandas": [
                {"banda": nombre, "min": lo, "max": hi, "incluye_derecha": inc}
                for nombre, lo, hi, inc in INTERVALOS_CALIBRACION_5
            ],
            "esquema_3_bandas": [
                {"banda": nombre, "min": lo, "max": hi, "incluye_derecha": inc}
                for nombre, lo, hi, inc in INTERVALOS_CALIBRACION_3
            ],
            "min_n_celda_confiable": MIN_N_CELDA_CONFIABLE,
        },
    }


def seleccionar_alpha_anidado(
    train_ext: pd.DataFrame,
    features: list[str],
    c_seleccionado: float,
    splits_internos: list[tuple[str, pd.DataFrame, pd.DataFrame]] | None = None,
) -> dict[str, Any]:
    splits = (
        splits_internos
        if splits_internos is not None
        else particiones_internas(train_ext)
    )
    if len(splits) < MIN_INNER:
        raise ValueError(f"Splits internos insuficientes ({len(splits)} < {MIN_INNER}).")

    predicciones_por_split: list[dict[str, Any]] = []
    for nombre_split, tr_in, va_in in splits:
        if tr_in["fecha_objetivo_h5"].max() >= va_in["fecha"].min():
            raise ValueError(
                f"Fuga temporal interna detectada en {nombre_split}: "
                f"{tr_in['fecha_objetivo_h5'].max()} >= {va_in['fecha'].min()}"
            )
        p_in, _, _, _ = ajustar(tr_in, va_in, features, float(c_seleccionado))
        y_in = va_in["target_y"].to_numpy(dtype=float)
        prev_in = float(tr_in["target_y"].mean())
        predicciones_por_split.append(
            {
                "periodo_interno": nombre_split,
                "n_train_interno": int(len(tr_in)),
                "n_val_interno": int(len(va_in)),
                "inicio_train_interno": str(tr_in["fecha"].min()),
                "fin_etiquetas_train_interno": str(tr_in["fecha_objetivo_h5"].max()),
                "inicio_val_interno": str(va_in["fecha"].min()),
                "fin_etiquetas_val_interno": str(va_in["fecha_objetivo_h5"].max()),
                "prevalencia_train_interno": prev_in,
                "p_modelo": p_in,
                "y_val": y_in,
            }
        )

    resultado_por_ref: dict[str, Any] = {}
    for tipo_ref in ("CONSTANTE_05", "PREVALENCIA_TRAIN"):
        curva_media: dict[str, float] = {}
        curva_agregada: dict[str, float] = {}
        curva_se: dict[str, float] = {}
        detalle_splits_ref: list[dict[str, Any]] = []

        for item in predicciones_por_split:
            p_ref = 0.5 if tipo_ref == "CONSTANTE_05" else item["prevalencia_train_interno"]
            fila_split = {
                "periodo_interno": item["periodo_interno"],
                "n_train_interno": item["n_train_interno"],
                "n_val_interno": item["n_val_interno"],
                "inicio_train_interno": item["inicio_train_interno"],
                "fin_etiquetas_train_interno": item["fin_etiquetas_train_interno"],
                "inicio_val_interno": item["inicio_val_interno"],
                "fin_etiquetas_val_interno": item["fin_etiquetas_val_interno"],
                "prevalencia_train_interno": item["prevalencia_train_interno"],
                "p_referencia_interna": float(p_ref),
            }
            for alpha in ALPHA_GRID:
                pf = contraer_probabilidad(item["p_modelo"], p_ref, alpha)
                brier_split = float(np.mean((pf - item["y_val"]) ** 2))
                fila_split[f"brier_alpha_{alpha:.2f}"] = brier_split
            detalle_splits_ref.append(fila_split)

        n_obs_total = sum(x["n_val_interno"] for x in predicciones_por_split)
        for alpha in ALPHA_GRID:
            key = f"{alpha:.2f}"
            losses_split = [
                f[f"brier_alpha_{alpha:.2f}"] for f in detalle_splits_ref
            ]
            pesos_split = [f["n_val_interno"] for f in detalle_splits_ref]
            curva_media[key] = float(np.mean(losses_split))
            curva_agregada[key] = float(
                np.sum(np.asarray(losses_split) * np.asarray(pesos_split)) / n_obs_total
            )
            curva_se[key] = (
                float(np.std(losses_split, ddof=1) / np.sqrt(len(losses_split)))
                if len(losses_split) > 1
                else 0.0
            )

        min_brier_medio = min(curva_media.values())
        candidatos_empate = [
            alpha
            for alpha in ALPHA_GRID
            if curva_media[f"{alpha:.2f}"] <= min_brier_medio + TOLERANCIA_EMPATE_ALPHA
        ]
        alpha_elegido = float(min(candidatos_empate))

        min_brier_agregado = min(curva_agregada.values())
        alpha_min_agregado = float(
            min(
                alpha
                for alpha in ALPHA_GRID
                if curva_agregada[f"{alpha:.2f}"]
                <= min_brier_agregado + TOLERANCIA_EMPATE_ALPHA
            )
        )

        resultado_por_ref[tipo_ref] = {
            "alpha_seleccionado": alpha_elegido,
            "alpha_min_brier_agregado": alpha_min_agregado,
            "coincide_medio_y_agregado": bool(alpha_elegido == alpha_min_agregado),
            "regla": REGLA_SELECCION_ALPHA,
            "n_splits_internos": int(len(splits)),
            "n_obs_internas": int(n_obs_total),
            "brier_medio_interno_alpha_seleccionado": float(
                curva_media[f"{alpha_elegido:.2f}"]
            ),
            "brier_medio_interno_alpha_1": float(curva_media["1.00"]),
            "brier_medio_interno_alpha_0": float(curva_media["0.00"]),
            "curva_brier_medio_interno": curva_media,
            "curva_brier_agregado_interno": curva_agregada,
            "curva_se_interno": curva_se,
            "detalle_splits": detalle_splits_ref,
        }

    return resultado_por_ref


def ejecutar_regimen(
    dev: pd.DataFrame,
    regimen: str,
) -> dict[str, Any]:
    bloques = periodos(INICIO_EVALUACION_EXTERNA, CORTE_TRAIN)
    filas_periodo: list[dict[str, Any]] = []
    filas_seleccion: list[dict[str, Any]] = []
    filas_internas_alpha: list[dict[str, Any]] = []
    filas_coeficientes: list[dict[str, Any]] = []
    marcos_predicciones: list[pd.DataFrame] = []

    for fold_nombre, inicio_str, fin_str in bloques:
        tr_ext, va_ext = particion_externa(dev, inicio_str, fin_str, regimen)
        purga_final = int(
            (dev["fecha"].between(inicio_str, fin_str) & dev["fecha_objetivo_h5"].gt(fin_str)).sum()
        )

        if len(tr_ext) < MIN_TRAIN or len(va_ext) < MIN_VAL or tr_ext["target_y"].nunique() < 2:
            filas_periodo.append(
                {
                    "regimen": regimen,
                    "variante": "TODAS",
                    "conjunto_variables": "TODOS",
                    "tratamiento_probabilistico": "NO_EVALUADO",
                    "referencia_contraccion": "NO_EVALUADO",
                    "periodo": fold_nombre,
                    "estado": "INSUFICIENTE_MUESTRA",
                    "inicio_bloque": inicio_str,
                    "fin_bloque": fin_str,
                    "n_train": int(len(tr_ext)),
                    "n_val": int(len(va_ext)),
                    "purga_final_bloque": purga_final,
                    "motivo": (
                        f"Bloque no evaluado: n_train={len(tr_ext)} "
                        f"(min={MIN_TRAIN}), n_val={len(va_ext)} "
                        f"(min={MIN_VAL}); hueco real de boletines BMV en 2023."
                    ),
                }
            )
            continue

        # Verificacion explicita de controles temporales obligatorios
        if tr_ext["fecha_objetivo_h5"].max() >= va_ext["fecha"].min():
            raise ValueError(
                f"Violacion temporal en {fold_nombre}: etiqueta de train vence en "
                f"{tr_ext['fecha_objetivo_h5'].max()} >= inicio val {va_ext['fecha'].min()}"
            )
        if va_ext["fecha_objetivo_h5"].max() > fin_str:
            raise ValueError(
                f"Violacion de purga al final del bloque en {fold_nombre}: "
                f"{va_ext['fecha_objetivo_h5'].max()} > {fin_str}"
            )

        splits_internos = particiones_internas(tr_ext)
        for nombre_in, tr_in, va_in in splits_internos:
            if tr_in["fecha_objetivo_h5"].max() >= va_in["fecha"].min():
                raise ValueError(f"Violacion temporal interna en {fold_nombre}/{nombre_in}")
            if va_in["fecha_objetivo_h5"].max() >= va_ext["fecha"].min():
                raise ValueError(
                    f"Seleccion interna usa informacion fuera de Train externo en {fold_nombre}/{nombre_in}"
                )

        prevalencia_train_ext = float(tr_ext["target_y"].mean())
        y_ext = va_ext["target_y"].to_numpy(dtype=int)

        resultados_base: dict[str, dict[str, Any]] = {}
        for etiqueta_vars, lista_vars in (
            ("8VARS", VARIABLES_OCHO),
            ("2VARS", VARIABLES_DOS),
        ):
            c_sel, scores_c, _ = seleccionar_c_anidado(tr_ext, lista_vars)
            if c_sel is None:
                raise RuntimeError(f"No se pudo seleccionar C en {fold_nombre} ({etiqueta_vars}).")

            info_alpha = seleccionar_alpha_anidado(
                tr_ext, lista_vars, float(c_sel), splits_internos=splits_internos
            )
            p_raw_ext, beta, mu, sig = ajustar(
                tr_ext, va_ext, lista_vars, float(c_sel)
            )
            intercepto = float(beta[0])
            coefs = beta[1:]

            resultados_base[etiqueta_vars] = {
                "features": lista_vars,
                "c_seleccionado": float(c_sel),
                "scores_c": scores_c,
                "info_alpha": info_alpha,
                "p_raw_ext": p_raw_ext,
                "intercepto": intercepto,
                "coefs": coefs,
                "mu": mu,
                "sig": sig,
            }

            row_coef = {
                "regimen": regimen,
                "conjunto_variables": etiqueta_vars,
                "periodo": fold_nombre,
                "c_seleccionado": float(c_sel),
                "alpha_constante_05": float(
                    info_alpha["CONSTANTE_05"]["alpha_seleccionado"]
                ),
                "alpha_prevalencia_train": float(
                    info_alpha["PREVALENCIA_TRAIN"]["alpha_seleccionado"]
                ),
                "n_train": int(len(tr_ext)),
                "n_val": int(len(va_ext)),
                "prevalencia_train": prevalencia_train_ext,
                "intercepto": intercepto,
            }
            for feat in VARIABLES_OCHO:
                if feat in lista_vars:
                    idx_f = lista_vars.index(feat)
                    row_coef[f"coef_{feat}"] = float(coefs[idx_f])
                else:
                    row_coef[f"coef_{feat}"] = np.nan
            filas_coeficientes.append(row_coef)

            mapa_c = {float(s["C"]): float(s["brier_medio_interno"]) for s in scores_c}
            for tipo_ref in ("CONSTANTE_05", "PREVALENCIA_TRAIN"):
                ia = info_alpha[tipo_ref]
                fila_sel = {
                    "regimen": regimen,
                    "periodo": fold_nombre,
                    "conjunto_variables": etiqueta_vars,
                    "referencia_contraccion": tipo_ref,
                    "n_train_externo": int(len(tr_ext)),
                    "n_val_externo": int(len(va_ext)),
                    "inicio_train_externo": str(tr_ext["fecha"].min()),
                    "fin_etiquetas_train_externo": str(
                        tr_ext["fecha_objetivo_h5"].max()
                    ),
                    "inicio_val_externo": str(va_ext["fecha"].min()),
                    "fin_etiquetas_val_externo": str(
                        va_ext["fecha_objetivo_h5"].max()
                    ),
                    "prevalencia_train_externo": prevalencia_train_ext,
                    "n_splits_internos": int(ia["n_splits_internos"]),
                    "n_obs_internas": int(ia["n_obs_internas"]),
                    "c_seleccionado": float(c_sel),
                    "brier_interno_c_001": mapa_c.get(0.01, np.nan),
                    "brier_interno_c_010": mapa_c.get(0.1, np.nan),
                    "brier_interno_c_100": mapa_c.get(1.0, np.nan),
                    "brier_interno_c_1000": mapa_c.get(10.0, np.nan),
                    "alpha_seleccionado": float(ia["alpha_seleccionado"]),
                    "alpha_min_brier_agregado": float(ia["alpha_min_brier_agregado"]),
                    "coincide_medio_y_agregado": bool(ia["coincide_medio_y_agregado"]),
                    "regla_alpha": ia["regla"],
                    "brier_interno_alpha_000": float(
                        ia["curva_brier_medio_interno"]["0.00"]
                    ),
                    "brier_interno_alpha_025": float(
                        ia["curva_brier_medio_interno"]["0.25"]
                    ),
                    "brier_interno_alpha_050": float(
                        ia["curva_brier_medio_interno"]["0.50"]
                    ),
                    "brier_interno_alpha_075": float(
                        ia["curva_brier_medio_interno"]["0.75"]
                    ),
                    "brier_interno_alpha_100": float(
                        ia["curva_brier_medio_interno"]["1.00"]
                    ),
                }
                filas_seleccion.append(fila_sel)

                for det in ia["detalle_splits"]:
                    filas_internas_alpha.append(
                        {
                            "regimen": regimen,
                            "periodo_externo": fold_nombre,
                            "conjunto_variables": etiqueta_vars,
                            "referencia_contraccion": tipo_ref,
                            "c_seleccionado": float(c_sel),
                            "alpha_seleccionado_externo": float(
                                ia["alpha_seleccionado"]
                            ),
                            **det,
                        }
                    )

        # Construir las probabilidades externas de todas las variantes sobre las mismas fechas
        p_8_orig = resultados_base["8VARS"]["p_raw_ext"]
        c_8 = resultados_base["8VARS"]["c_seleccionado"]
        alpha_8_05 = resultados_base["8VARS"]["info_alpha"]["CONSTANTE_05"][
            "alpha_seleccionado"
        ]
        alpha_8_prev = resultados_base["8VARS"]["info_alpha"]["PREVALENCIA_TRAIN"][
            "alpha_seleccionado"
        ]
        p_8_contr_05 = contraer_probabilidad(p_8_orig, 0.5, alpha_8_05)
        p_8_contr_prev = contraer_probabilidad(
            p_8_orig, prevalencia_train_ext, alpha_8_prev
        )

        p_2_orig = resultados_base["2VARS"]["p_raw_ext"]
        c_2 = resultados_base["2VARS"]["c_seleccionado"]
        alpha_2_05 = resultados_base["2VARS"]["info_alpha"]["CONSTANTE_05"][
            "alpha_seleccionado"
        ]
        alpha_2_prev = resultados_base["2VARS"]["info_alpha"]["PREVALENCIA_TRAIN"][
            "alpha_seleccionado"
        ]
        p_2_contr_05 = contraer_probabilidad(p_2_orig, 0.5, alpha_2_05)
        p_2_contr_prev = contraer_probabilidad(
            p_2_orig, prevalencia_train_ext, alpha_2_prev
        )

        p_dummy = np.full(len(va_ext), prevalencia_train_ext, dtype=float)
        p_const_05 = np.full(len(va_ext), 0.5, dtype=float)

        pred_df = pd.DataFrame(
            {
                "regimen": regimen,
                "fold": fold_nombre,
                "periodo": fold_nombre,
                "fecha": va_ext["fecha"].to_numpy(),
                "fecha_objetivo_h5": va_ext["fecha_objetivo_h5"].to_numpy(),
                "posicion_sesion": va_ext["posicion_sesion"].to_numpy(dtype=int),
                "ppp_t": va_ext["ppp_t"].to_numpy(dtype=float),
                "ppp_t5": va_ext["ppp_t5"].to_numpy(dtype=float),
                "target_y": y_ext,
                "n_train": int(len(tr_ext)),
                "prevalencia_train": prevalencia_train_ext,
                "c_8vars": float(c_8),
                "alpha_8vars_05": float(alpha_8_05),
                "alpha_8vars_prev": float(alpha_8_prev),
                "c_2vars": float(c_2),
                "alpha_2vars_05": float(alpha_2_05),
                "alpha_2vars_prev": float(alpha_2_prev),
                "prob_A_8VARS_ORIG": p_8_orig,
                "prob_B_8VARS_CONTR_05": p_8_contr_05,
                "prob_C_2VARS_ORIG": p_2_orig,
                "prob_D_2VARS_CONTR_05": p_2_contr_05,
                "prob_B_SENS_8VARS_CONTR_PREV": p_8_contr_prev,
                "prob_D_SENS_2VARS_CONTR_PREV": p_2_contr_prev,
                "prob_DUMMY_PREVALENCIA": p_dummy,
                "prob_REFERENCIA_CONSTANTE_05": p_const_05,
            }
        )
        marcos_predicciones.append(pred_df)

        especificaciones_fold = [
            ("A_8VARS_ORIG", "8VARS", "ORIGINAL", "NINGUNA", c_8, 1.0, p_8_orig),
            ("B_8VARS_CONTR_05", "8VARS", "CONTRAIDA", "CONSTANTE_05", c_8, alpha_8_05, p_8_contr_05),
            ("C_2VARS_ORIG", "2VARS", "ORIGINAL", "NINGUNA", c_2, 1.0, p_2_orig),
            ("D_2VARS_CONTR_05", "2VARS", "CONTRAIDA", "CONSTANTE_05", c_2, alpha_2_05, p_2_contr_05),
            ("B_SENS_8VARS_CONTR_PREV", "8VARS", "CONTRAIDA", "PREVALENCIA_TRAIN", c_8, alpha_8_prev, p_8_contr_prev),
            ("D_SENS_2VARS_CONTR_PREV", "2VARS", "CONTRAIDA", "PREVALENCIA_TRAIN", c_2, alpha_2_prev, p_2_contr_prev),
            ("DUMMY_PREVALENCIA", "0VARS", "REFERENCIA", "PREVALENCIA_TRAIN", np.nan, 0.0, p_dummy),
            ("REFERENCIA_CONSTANTE_05", "0VARS", "REFERENCIA", "CONSTANTE_05", np.nan, 0.0, p_const_05),
        ]

        brier_a = float(np.mean((p_8_orig - y_ext) ** 2))
        brier_dummy = float(np.mean((p_dummy - y_ext) ** 2))
        brier_05 = float(np.mean((p_const_05 - y_ext) ** 2))

        for (
            var_nombre,
            conj_vars,
            trat_prob,
            ref_contr,
            c_val,
            alpha_val,
            p_vec,
        ) in especificaciones_fold:
            m = metricas(y_ext, p_vec, p_dummy)
            filas_periodo.append(
                {
                    "regimen": regimen,
                    "variante": var_nombre,
                    "conjunto_variables": conj_vars,
                    "tratamiento_probabilistico": trat_prob,
                    "referencia_contraccion": ref_contr,
                    "periodo": fold_nombre,
                    "estado": "EVALUADO",
                    "inicio_bloque": inicio_str,
                    "fin_bloque": fin_str,
                    "inicio_train": str(tr_ext["fecha"].min()),
                    "fin_train": str(tr_ext["fecha"].max()),
                    "fin_etiquetas_train": str(tr_ext["fecha_objetivo_h5"].max()),
                    "inicio_val": str(va_ext["fecha"].min()),
                    "fin_val": str(va_ext["fecha"].max()),
                    "fin_etiquetas_val": str(va_ext["fecha_objetivo_h5"].max()),
                    "n_train": int(len(tr_ext)),
                    "n_val": int(len(va_ext)),
                    "purga_final_bloque": purga_final,
                    "prevalencia_train": prevalencia_train_ext,
                    "c_seleccionado": float(c_val) if not np.isnan(c_val) else np.nan,
                    "alpha_seleccionado": float(alpha_val),
                    **m,
                    "delta_brier_vs_A_8VARS_ORIG": float(m["brier"] - brier_a),
                    "mejora_brier_vs_A_8VARS_ORIG": bool(m["brier"] < brier_a - 1e-15),
                    "empata_brier_vs_A_8VARS_ORIG": bool(
                        np.isclose(m["brier"], brier_a, atol=1e-15)
                    ),
                    "delta_brier_vs_DUMMY_PREVALENCIA": float(m["brier"] - brier_dummy),
                    "mejora_brier_vs_DUMMY_PREVALENCIA": bool(
                        m["brier"] < brier_dummy - 1e-15
                    ),
                    "delta_brier_vs_CONSTANTE_05": float(m["brier"] - brier_05),
                    "mejora_brier_vs_CONSTANTE_05": bool(m["brier"] < brier_05 - 1e-15),
                }
            )

    predicciones = pd.concat(marcos_predicciones, ignore_index=True)
    df_periodo = pd.DataFrame(filas_periodo)
    df_seleccion = pd.DataFrame(filas_seleccion)
    df_internas_alpha = pd.DataFrame(filas_internas_alpha)
    df_coeficientes = pd.DataFrame(filas_coeficientes)

    resumen_variantes = resumir_variantes(predicciones, df_periodo, regimen)
    comparaciones = construir_comparaciones_pareadas(predicciones, df_periodo, regimen)
    diagnosticos_cal = construir_diagnosticos_calibracion(predicciones, regimen)

    return {
        "regimen": regimen,
        "predicciones": predicciones,
        "metricas_por_periodo": df_periodo,
        "seleccion_hiperparametros": df_seleccion,
        "particiones_internas_alpha": df_internas_alpha,
        "coeficientes": df_coeficientes,
        "resumen_variantes": resumen_variantes,
        "comparaciones_pareadas": comparaciones,
        "diagnosticos_calibracion": diagnosticos_cal,
    }


def resumir_variantes(
    predicciones: pd.DataFrame,
    df_periodo: pd.DataFrame,
    regimen: str,
) -> dict[str, dict[str, Any]]:
    y_all = predicciones["target_y"].to_numpy(dtype=int)
    p_a_all = predicciones["prob_A_8VARS_ORIG"].to_numpy(dtype=float)
    p_dummy_all = predicciones["prob_DUMMY_PREVALENCIA"].to_numpy(dtype=float)
    p_05_all = predicciones["prob_REFERENCIA_CONSTANTE_05"].to_numpy(dtype=float)

    brier_a_all = float(np.mean((p_a_all - y_all) ** 2))
    brier_dummy_all = float(np.mean((p_dummy_all - y_all) ** 2))
    brier_05_all = float(np.mean((p_05_all - y_all) ** 2))

    eval_df = df_periodo[df_periodo["estado"] == "EVALUADO"].copy()
    resumen: dict[str, dict[str, Any]] = {}

    sub_a = eval_df[eval_df["variante"] == "A_8VARS_ORIG"].sort_values("inicio_bloque")
    sub_d = eval_df[eval_df["variante"] == "DUMMY_PREVALENCIA"].sort_values("inicio_bloque")
    sub_c05 = eval_df[eval_df["variante"] == "REFERENCIA_CONSTANTE_05"].sort_values("inicio_bloque")

    brier_a_per = sub_a["brier"].to_numpy(dtype=float)
    brier_d_per = sub_d["brier"].to_numpy(dtype=float)
    brier_c05_per = sub_c05["brier"].to_numpy(dtype=float)

    for var in TODAS_LAS_SERIES:
        col_prob = f"prob_{var}"
        p_all = predicciones[col_prob].to_numpy(dtype=float)
        m_global = metricas(y_all, p_all, p_dummy_all)

        sub_per = eval_df[eval_df["variante"] == var].sort_values("inicio_bloque")
        briers_per = sub_per["brier"].to_numpy(dtype=float)
        idx_peor = int(np.argmax(briers_per))
        peor_fila = sub_per.iloc[idx_peor]

        alphas_per = sub_per["alpha_seleccionado"].to_numpy(dtype=float)
        cs_per = sub_per["c_seleccionado"].dropna().to_numpy(dtype=float)

        mejora_estricta_vs_a = int(np.sum(briers_per < brier_a_per - 1e-15))
        empata_vs_a = int(np.sum(np.isclose(briers_per, brier_a_per, atol=1e-15)))
        empeora_vs_a = int(np.sum(briers_per > brier_a_per + 1e-15))

        mejora_estricta_vs_dummy = int(np.sum(briers_per < brier_d_per - 1e-15))
        mejora_estricta_vs_05 = int(np.sum(briers_per < brier_c05_per - 1e-15))

        resumen[var] = {
            "regimen": regimen,
            "variante": var,
            "periodos_evaluados": int(len(sub_per)),
            "periodos_insuficientes": int(
                (df_periodo["estado"] == "INSUFICIENTE_MUESTRA").sum()
            ),
            **m_global,
            "delta_brier_global_vs_A_8VARS_ORIG": float(
                m_global["brier"] - brier_a_all
            ),
            "delta_brier_global_vs_DUMMY_PREVALENCIA": float(
                m_global["brier"] - brier_dummy_all
            ),
            "delta_brier_global_vs_CONSTANTE_05": float(
                m_global["brier"] - brier_05_all
            ),
            "brier_media_simple_semestral": float(np.mean(briers_per)),
            "brier_desv_estandar_semestral": float(np.std(briers_per, ddof=1)),
            "brier_min_semestral": float(np.min(briers_per)),
            "brier_max_semestral": float(np.max(briers_per)),
            "peor_periodo": str(peor_fila["periodo"]),
            "peor_periodo_brier": float(peor_fila["brier"]),
            "periodos_mejora_estricta_vs_A_8VARS_ORIG": mejora_estricta_vs_a,
            "periodos_empata_vs_A_8VARS_ORIG": empata_vs_a,
            "periodos_empeora_vs_A_8VARS_ORIG": empeora_vs_a,
            "periodos_mejora_estricta_vs_DUMMY_PREVALENCIA": mejora_estricta_vs_dummy,
            "periodos_mejora_estricta_vs_CONSTANTE_05": mejora_estricta_vs_05,
            "frecuencia_alpha_igual_0": int(np.sum(np.isclose(alphas_per, 0.0))),
            "frecuencia_alpha_igual_025": int(np.sum(np.isclose(alphas_per, 0.25))),
            "frecuencia_alpha_igual_050": int(np.sum(np.isclose(alphas_per, 0.50))),
            "frecuencia_alpha_igual_075": int(np.sum(np.isclose(alphas_per, 0.75))),
            "frecuencia_alpha_igual_1": int(np.sum(np.isclose(alphas_per, 1.0))),
            "conteo_alpha_por_valor": {
                f"{a:.2f}": int(np.sum(np.isclose(alphas_per, a)))
                for a in ALPHA_GRID
            },
            "conteo_c_por_valor": (
                {
                    str(c): int(np.sum(np.isclose(cs_per, c)))
                    for c in CS
                }
                if len(cs_per) > 0
                else {}
            ),
            "alphas_por_periodo": {
                str(r["periodo"]): float(r["alpha_seleccionado"])
                for _, r in sub_per.iterrows()
            },
            "cs_por_periodo": (
                {
                    str(r["periodo"]): float(r["c_seleccionado"])
                    for _, r in sub_per.iterrows()
                    if not np.isnan(r["c_seleccionado"])
                }
                if len(cs_per) > 0
                else {}
            ),
        }

    return resumen


def construir_comparaciones_pareadas(
    predicciones: pd.DataFrame,
    df_periodo: pd.DataFrame,
    regimen: str,
) -> pd.DataFrame:
    y = predicciones["target_y"].to_numpy(dtype=float)
    eval_df = df_periodo[df_periodo["estado"] == "EVALUADO"].copy()

    definiciones = [
        # 1. Contraccion frente a probabilidades originales, manteniendo variables
        (
            "CONTRACCION_VS_ORIGINAL_MANTENIENDO_VARIABLES",
            "B_8VARS_CONTR_05_vs_A_8VARS_ORIG",
            "B_8VARS_CONTR_05",
            "A_8VARS_ORIG",
            "Efecto de contraccion hacia 0.5 manteniendo 8 variables y el mismo modelo base",
        ),
        (
            "CONTRACCION_VS_ORIGINAL_MANTENIENDO_VARIABLES",
            "D_2VARS_CONTR_05_vs_C_2VARS_ORIG",
            "D_2VARS_CONTR_05",
            "C_2VARS_ORIG",
            "Efecto de contraccion hacia 0.5 manteniendo 2 variables y el mismo modelo base",
        ),
        (
            "CONTRACCION_VS_ORIGINAL_MANTENIENDO_VARIABLES",
            "B_SENS_8VARS_CONTR_PREV_vs_A_8VARS_ORIG",
            "B_SENS_8VARS_CONTR_PREV",
            "A_8VARS_ORIG",
            "Sensibilidad secundaria: contraccion hacia prevalencia de Train manteniendo 8 variables",
        ),
        (
            "CONTRACCION_VS_ORIGINAL_MANTENIENDO_VARIABLES",
            "D_SENS_2VARS_CONTR_PREV_vs_C_2VARS_ORIG",
            "D_SENS_2VARS_CONTR_PREV",
            "C_2VARS_ORIG",
            "Sensibilidad secundaria: contraccion hacia prevalencia de Train manteniendo 2 variables",
        ),
        # 2. Dos variables frente a ocho, manteniendo el tratamiento probabilistico
        (
            "DOS_VARS_VS_OCHO_VARS_MANTENIENDO_TRATAMIENTO",
            "C_2VARS_ORIG_vs_A_8VARS_ORIG",
            "C_2VARS_ORIG",
            "A_8VARS_ORIG",
            "Efecto de simplificar de 8 a 2 variables manteniendo probabilidades originales (alpha=1)",
        ),
        (
            "DOS_VARS_VS_OCHO_VARS_MANTENIENDO_TRATAMIENTO",
            "D_2VARS_CONTR_05_vs_B_8VARS_CONTR_05",
            "D_2VARS_CONTR_05",
            "B_8VARS_CONTR_05",
            "Efecto de simplificar de 8 a 2 variables manteniendo contraccion hacia 0.5",
        ),
        (
            "DOS_VARS_VS_OCHO_VARS_MANTENIENDO_TRATAMIENTO",
            "D_SENS_2VARS_CONTR_PREV_vs_B_SENS_8VARS_CONTR_PREV",
            "D_SENS_2VARS_CONTR_PREV",
            "B_SENS_8VARS_CONTR_PREV",
            "Sensibilidad secundaria: simplificar de 8 a 2 variables manteniendo contraccion hacia prevalencia",
        ),
        # 3. Variante simplificada y contraida frente al benchmark principal
        (
            "SIMPLIFICADA_Y_CONTRAIDA_VS_BENCHMARK_PRINCIPAL",
            "D_2VARS_CONTR_05_vs_A_8VARS_ORIG",
            "D_2VARS_CONTR_05",
            "A_8VARS_ORIG",
            "Efecto conjunto de simplificacion (2 variables) + contraccion hacia 0.5 frente al benchmark A",
        ),
        (
            "SIMPLIFICADA_Y_CONTRAIDA_VS_BENCHMARK_PRINCIPAL",
            "D_SENS_2VARS_CONTR_PREV_vs_A_8VARS_ORIG",
            "D_SENS_2VARS_CONTR_PREV",
            "A_8VARS_ORIG",
            "Sensibilidad secundaria: simplificacion (2 variables) + contraccion hacia prevalencia frente al benchmark A",
        ),
        # 4. Comparaciones contra referencias sin senal (Dummy prevalencia y Constante 0.5)
        (
            "VARIANTES_VS_REFERENCIAS_SIN_SENAL",
            "A_8VARS_ORIG_vs_DUMMY_PREVALENCIA",
            "A_8VARS_ORIG",
            "DUMMY_PREVALENCIA",
            "Benchmark A (8 vars original) frente al Dummy de prevalencia historica",
        ),
        (
            "VARIANTES_VS_REFERENCIAS_SIN_SENAL",
            "B_8VARS_CONTR_05_vs_DUMMY_PREVALENCIA",
            "B_8VARS_CONTR_05",
            "DUMMY_PREVALENCIA",
            "Variante B (8 vars contraida 0.5) frente al Dummy de prevalencia historica",
        ),
        (
            "VARIANTES_VS_REFERENCIAS_SIN_SENAL",
            "C_2VARS_ORIG_vs_DUMMY_PREVALENCIA",
            "C_2VARS_ORIG",
            "DUMMY_PREVALENCIA",
            "Variante C (2 vars original) frente al Dummy de prevalencia historica",
        ),
        (
            "VARIANTES_VS_REFERENCIAS_SIN_SENAL",
            "D_2VARS_CONTR_05_vs_DUMMY_PREVALENCIA",
            "D_2VARS_CONTR_05",
            "DUMMY_PREVALENCIA",
            "Variante D (2 vars contraida 0.5) frente al Dummy de prevalencia historica",
        ),
        (
            "VARIANTES_VS_REFERENCIAS_SIN_SENAL",
            "A_8VARS_ORIG_vs_REFERENCIA_CONSTANTE_05",
            "A_8VARS_ORIG",
            "REFERENCIA_CONSTANTE_05",
            "Benchmark A (8 vars original) frente a referencia constante p=0.5",
        ),
        (
            "VARIANTES_VS_REFERENCIAS_SIN_SENAL",
            "B_8VARS_CONTR_05_vs_REFERENCIA_CONSTANTE_05",
            "B_8VARS_CONTR_05",
            "REFERENCIA_CONSTANTE_05",
            "Variante B (8 vars contraida 0.5) frente a referencia constante p=0.5",
        ),
        (
            "VARIANTES_VS_REFERENCIAS_SIN_SENAL",
            "C_2VARS_ORIG_vs_REFERENCIA_CONSTANTE_05",
            "C_2VARS_ORIG",
            "REFERENCIA_CONSTANTE_05",
            "Variante C (2 vars original) frente a referencia constante p=0.5",
        ),
        (
            "VARIANTES_VS_REFERENCIAS_SIN_SENAL",
            "D_2VARS_CONTR_05_vs_REFERENCIA_CONSTANTE_05",
            "D_2VARS_CONTR_05",
            "REFERENCIA_CONSTANTE_05",
            "Variante D (2 vars contraida 0.5) frente a referencia constante p=0.5",
        ),
    ]

    filas_comp: list[dict[str, Any]] = []
    for familia, clave, cand, ref, desc in definiciones:
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

        mejora_per = int(np.sum(b_c_per < b_r_per - 1e-15))
        empata_per = int(np.sum(np.isclose(b_c_per, b_r_per, atol=1e-15)))
        empeora_per = int(np.sum(b_c_per > b_r_per + 1e-15))

        filas_comp.append(
            {
                "regimen": regimen,
                "familia_comparacion": familia,
                "comparacion": clave,
                "variante_candidata": cand,
                "variante_referencia": ref,
                "descripcion": desc,
                "brier_candidata": float(np.mean(loss_cand)),
                "brier_referencia": float(np.mean(loss_ref)),
                "delta_brier_observado": float(info_b["media"]),
                "ic95_bajo": ic_low,
                "ic95_alto": ic_high,
                "ic95_incluye_cero": bool(ic_low <= 0.0 <= ic_high),
                "periodos_mejora_estricta": mejora_per,
                "periodos_empate": empata_per,
                "periodos_empeora": empeora_per,
                "total_periodos_evaluados": int(len(b_c_per)),
                "replicas_bootstrap": int(info_b["replicas"]),
                "longitud_bloque_sesiones": int(info_b["longitud_bloque_sesiones"]),
            }
        )

    return pd.DataFrame(filas_comp)


def construir_diagnosticos_calibracion(
    predicciones: pd.DataFrame,
    regimen: str,
) -> pd.DataFrame:
    y = predicciones["target_y"].to_numpy(dtype=float)
    filas: list[dict[str, Any]] = []

    esquemas = [
        ("ESQUEMA_5_BANDAS", INTERVALOS_CALIBRACION_5),
        ("ESQUEMA_3_BANDAS", INTERVALOS_CALIBRACION_3),
    ]

    for var in TODAS_LAS_SERIES:
        p = predicciones[f"prob_{var}"].to_numpy(dtype=float)
        for nombre_esquema, intervalos in esquemas:
            ece_ponderado = 0.0
            filas_esquema: list[dict[str, Any]] = []
            for idx_banda, (nombre_banda, lo, hi, inc_derecha) in enumerate(
                intervalos, start=1
            ):
                if idx_banda == 1 and inc_derecha:
                    mask = (p >= lo) & (p <= hi)
                elif inc_derecha:
                    if not intervalos[idx_banda - 2][3]:
                        mask = (p >= lo) & (p <= hi)
                    else:
                        mask = (p > lo) & (p <= hi)
                else:
                    mask = (p >= lo) & (p < hi)

                n_celda = int(np.sum(mask))
                if n_celda > 0:
                    p_med = float(np.mean(p[mask]))
                    f_obs = float(np.mean(y[mask]))
                    n_pos = int(np.sum(y[mask] == 1))
                    n_neg = int(np.sum(y[mask] == 0))
                    gap_abs = float(abs(p_med - f_obs))
                    sesgo_celda = float(p_med - f_obs)
                    brier_celda = float(np.mean((p[mask] - y[mask]) ** 2))
                    ece_ponderado += (n_celda / len(p)) * gap_abs
                else:
                    p_med = np.nan
                    f_obs = np.nan
                    n_pos = 0
                    n_neg = 0
                    gap_abs = np.nan
                    sesgo_celda = np.nan
                    brier_celda = np.nan

                filas_esquema.append(
                    {
                        "regimen": regimen,
                        "variante": var,
                        "esquema_intervalos": nombre_esquema,
                        "orden_banda": idx_banda,
                        "banda": nombre_banda,
                        "limite_inferior": float(lo),
                        "limite_superior": float(hi),
                        "n_observaciones": n_celda,
                        "proporcion_muestra": float(n_celda / len(p)),
                        "n_subida": n_pos,
                        "n_bajada_o_igual": n_neg,
                        "probabilidad_media_predicha": p_med,
                        "frecuencia_observada_subida": f_obs,
                        "sesgo_prob_menos_frecuencia": sesgo_celda,
                        "brecha_calibracion_absoluta": gap_abs,
                        "brier_en_banda": brier_celda,
                        "celda_pequena_n_menor_30": bool(
                            n_celda < MIN_N_CELDA_CONFIABLE
                        ),
                    }
                )
            for f in filas_esquema:
                f["ece_esquema_ponderado"] = float(ece_ponderado)
                filas.append(f)

    return pd.DataFrame(filas)


def ejecutar_investigacion(salida_dir: Path = SALIDA_DIR) -> dict[str, Any]:
    hashes_antes = hashes_protegidos()
    salida_dir.mkdir(parents=True, exist_ok=True)

    # 1. Registrar protocolo antes de calcular las nuevas metricas externas
    protocolo = construir_protocolo_preregistrado()
    protocolo["timestamp_registro_utc"] = timestamp_utc()
    protocolo_path = salida_dir / "protocolo.json"
    protocolo_path.write_text(
        json.dumps(protocolo, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    sha_protocolo = sha(protocolo_path)

    # 2. Preparar cobertura PPP completa de desarrollo (exclusivamente TRAIN)
    dev, resumen_datos = preparar_desarrollo_ppp(PANEL_PATH)

    # 3. Ejecutar analisis principal (EXPANSIVA) y sensibilidad secundaria (MOVIL_3_ANIOS)
    res_expansiva = ejecutar_regimen(dev, "EXPANSIVA")
    res_movil = ejecutar_regimen(dev, "MOVIL_3_ANIOS")

    # 4. Guardar artefactos tabulares auditables
    predicciones_todas = pd.concat(
        [res_expansiva["predicciones"], res_movil["predicciones"]],
        ignore_index=True,
    )
    metricas_periodo_todas = pd.concat(
        [res_expansiva["metricas_por_periodo"], res_movil["metricas_por_periodo"]],
        ignore_index=True,
    )
    seleccion_todas = pd.concat(
        [
            res_expansiva["seleccion_hiperparametros"],
            res_movil["seleccion_hiperparametros"],
        ],
        ignore_index=True,
    )
    internas_alpha_todas = pd.concat(
        [
            res_expansiva["particiones_internas_alpha"],
            res_movil["particiones_internas_alpha"],
        ],
        ignore_index=True,
    )
    coeficientes_todos = pd.concat(
        [res_expansiva["coeficientes"], res_movil["coeficientes"]],
        ignore_index=True,
    )
    comparaciones_todas = pd.concat(
        [
            res_expansiva["comparaciones_pareadas"],
            res_movil["comparaciones_pareadas"],
        ],
        ignore_index=True,
    )
    diagnosticos_todos = pd.concat(
        [
            res_expansiva["diagnosticos_calibracion"],
            res_movil["diagnosticos_calibracion"],
        ],
        ignore_index=True,
    )

    predicciones_path = salida_dir / "predicciones.csv"
    metricas_path = salida_dir / "metricas_por_periodo.csv"
    seleccion_path = salida_dir / "seleccion_hiperparametros.csv"
    internas_path = salida_dir / "particiones_internas_alpha.csv"
    coeficientes_path = salida_dir / "coeficientes.csv"
    comparaciones_path = salida_dir / "comparaciones_pareadas.csv"
    diagnosticos_path = salida_dir / "diagnosticos_calibracion.csv"

    predicciones_todas.to_csv(predicciones_path, index=False)
    metricas_periodo_todas.to_csv(metricas_path, index=False)
    seleccion_todas.to_csv(seleccion_path, index=False)
    internas_alpha_todas.to_csv(internas_path, index=False)
    coeficientes_todos.to_csv(coeficientes_path, index=False)
    comparaciones_todas.to_csv(comparaciones_path, index=False)
    diagnosticos_todos.to_csv(diagnosticos_path, index=False)

    hashes_despues = hashes_protegidos()
    if hashes_antes != hashes_despues:
        raise RuntimeError(
            "Se detecto una modificacion no autorizada en archivos protegidos del proyecto."
        )

    reporte = {
        "version_protocolo": VERSION_PROTOCOLO,
        "timestamp_ejecucion_utc": timestamp_utc(),
        "sha256_protocolo_preregistrado": sha_protocolo,
        "datos_desarrollo_ppp": resumen_datos,
        "analisis_principal_expansiva": {
            "resumen_variantes": res_expansiva["resumen_variantes"],
            "comparaciones_pareadas": res_expansiva[
                "comparaciones_pareadas"
            ].to_dict(orient="records"),
        },
        "sensibilidad_secundaria_movil_3_anios": {
            "resumen_variantes": res_movil["resumen_variantes"],
            "comparaciones_pareadas": res_movil["comparaciones_pareadas"].to_dict(
                orient="records"
            ),
        },
        "archivos_generados": {
            "protocolo": str(protocolo_path.relative_to(ROOT)),
            "predicciones": str(predicciones_path.relative_to(ROOT)),
            "metricas_por_periodo": str(metricas_path.relative_to(ROOT)),
            "seleccion_hiperparametros": str(seleccion_path.relative_to(ROOT)),
            "particiones_internas_alpha": str(internas_path.relative_to(ROOT)),
            "coeficientes": str(coeficientes_path.relative_to(ROOT)),
            "comparaciones_pareadas": str(comparaciones_path.relative_to(ROOT)),
            "diagnosticos_calibracion": str(diagnosticos_path.relative_to(ROOT)),
        },
        "hashes_archivos_generados": {
            "protocolo.json": sha_protocolo,
            "predicciones.csv": sha(predicciones_path),
            "metricas_por_periodo.csv": sha(metricas_path),
            "seleccion_hiperparametros.csv": sha(seleccion_path),
            "particiones_internas_alpha.csv": sha(internas_path),
            "coeficientes.csv": sha(coeficientes_path),
            "comparaciones_pareadas.csv": sha(comparaciones_path),
            "diagnosticos_calibracion.csv": sha(diagnosticos_path),
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
    rep = ejecutar_investigacion()
    print(
        json.dumps(
            {
                "version_protocolo": rep["version_protocolo"],
                "filas_desarrollo": rep["datos_desarrollo_ppp"][
                    "filas_desarrollo_ppp_elegibles"
                ],
                "sha256_desarrollo_ppp_canonico": rep["datos_desarrollo_ppp"][
                    "sha256_desarrollo_ppp_canonico"
                ],
                "expansiva_brier": {
                    k: v["brier"]
                    for k, v in rep["analisis_principal_expansiva"][
                        "resumen_variantes"
                    ].items()
                },
                "movil_3_anios_brier": {
                    k: v["brier"]
                    for k, v in rep["sensibilidad_secundaria_movil_3_anios"][
                        "resumen_variantes"
                    ].items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
