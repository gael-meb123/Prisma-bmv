from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from estabilidad_historica_gmexico import sha
from experimentos_avanzados_entrenamiento import (
    ARCHIVOS_PROTEGIDOS_AVANZADOS,
    ajustar_logistica_con_zona_neutral,
)
from experimentos_entrenamiento_desarrollo import (
    PANEL_PATH,
    VARIABLES_REL_TRES,
    ajustar_logistica_pooled_panel,
)
from metodologia_ppp import (
    CORTE_TRAIN,
    FEATURE_NAMES,
    ROOT,
    VERSION_FEATURES,
    VERSION_METODOLOGIA,
    add_bmv_sessions,
    calcular_features_ppp,
    calendario_objetivo,
    is_bmv_business_day,
    mascara_etiquetas_conocidas,
    sesiones_entre,
    timestamp_utc,
    validar_ventana_fechas,
)

HIST_PPP_PATH = ROOT / "serie_ppp_historica_15_emisoras_bmv.csv"
VIVO_PPP_PATH = ROOT / "monitoreo_ppp_multiemisora_en_vivo.csv"

REGISTRO_G2_PATH = ROOT / "registro_senales_prospectivas_panel_g2.csv"
VENTANAS_G2_PATH = ROOT / "estado_ventanas_panel_g2.csv"
RESUMEN_G2_PATH = ROOT / "resumen_monitor_prospectivo_g2.json"

VERSION_MONITOR_G2 = "MONITOR_PROSPECTIVO_PANEL_G2_V1"

MODELOS_G2 = (
    (
        "G2_V1_POOLED_REL3_CALIBRADO",
        "TRAIN_CONGELADO",
        0.01,
        0.0,
        "Pooled Panel 3 vars (ret_10, ret_10_rel_panel, volatilidad_20), C=0.01, Train congelado <= 2025-04-29",
    ),
    (
        "G2_V2_POOLED_REL3_ZONA_NEUTRAL",
        "TRAIN_CONGELADO",
        0.01,
        0.0025,
        "Pooled Panel 3 vars con filtrado de zona neutral |ret_h5| >= 0.25% en Train congelado, C=0.01",
    ),
    (
        "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO",
        "HISTORIA_PURGADA_HASTA_CORTE",
        0.001,
        0.0,
        "Pooled Panel 3 vars con alta regularizacion C=0.001 entrenado sobre toda la historia purgada (fecha_objetivo_h5 <= fecha_senal)",
    ),
)


def hashes_protegidos_g2() -> dict[str, str]:
    archivos = list(ARCHIVOS_PROTEGIDOS_AVANZADOS) + [
        ROOT / "experimentos_avanzados_entrenamiento" / "protocolo.json",
        ROOT / "experimentos_avanzados_entrenamiento" / "reporte.json",
        ROOT / "experimentos_avanzados_entrenamiento" / "predicciones.csv",
    ]
    return {
        str(p.relative_to(ROOT)): sha(p)
        for p in archivos
        if p.exists()
    }


def construir_serie_unificada_ppp(
    hist_path: Path = HIST_PPP_PATH,
    vivo_path: Path = VIVO_PPP_PATH,
) -> pd.DataFrame:
    """
    Combina sin duplicados la serie historica verificada (2016-2026) de las 15 emisoras
    con las capturas verificadas en vivo de monitoreo_ppp_multiemisora_en_vivo.csv.
    Garantiza que solo entren las 15 emisoras oficiales y conserva los huecos sin imputar.
    """
    hist = pd.read_csv(hist_path, dtype=str)
    emisoras_15 = sorted(hist["emisora"].astype(str).unique().tolist())

    cols_comunes = [
        "fecha",
        "emisora",
        "serie",
        "sector_economico",
        "anillo_madurez",
        "estado_captura",
        "ppp_bmv_mxn",
        "ultimo_bmv_mxn",
        "anterior_bmv_mxn",
        "variacion_ppp_vs_anterior_pct",
        "evidencia_exacta",
        "sha256_boletin",
        "url_fuente",
    ]
    base = hist[cols_comunes].copy()

    if vivo_path.exists():
        vivo = pd.read_csv(vivo_path, dtype=str)
        vivo = vivo[vivo["emisora"].astype(str).isin(emisoras_15)].copy()
        for c in cols_comunes:
            if c not in vivo.columns:
                vivo[c] = np.nan
        vivo_sub = vivo[cols_comunes].copy()
        comb = pd.concat([base, vivo_sub], ignore_index=True)
    else:
        comb = base

    comb["fecha"] = pd.to_datetime(comb["fecha"], errors="raise").dt.strftime("%Y-%m-%d")
    comb["ppp_bmv_mxn"] = pd.to_numeric(comb["ppp_bmv_mxn"], errors="coerce")
    comb["ultimo_bmv_mxn"] = pd.to_numeric(comb["ultimo_bmv_mxn"], errors="coerce")
    comb["anterior_bmv_mxn"] = pd.to_numeric(comb["anterior_bmv_mxn"], errors="coerce")
    comb["variacion_ppp_vs_anterior_pct"] = pd.to_numeric(
        comb["variacion_ppp_vs_anterior_pct"], errors="coerce"
    )

    # Verificar que si una fecha/emisora aparece en ambos archivos con PPP finito, coincida exactamente
    con_ppp = comb[comb["ppp_bmv_mxn"].notna()]
    dup_check = con_ppp.groupby(["fecha", "emisora"])["ppp_bmv_mxn"].nunique()
    if (dup_check > 1).any():
        conflictos = dup_check[dup_check > 1].index.tolist()
        raise ValueError(f"Conflicto de PPP entre historico y vivo en: {conflictos}")

    comb = (
        comb.sort_values(["fecha", "emisora"])
        .drop_duplicates(["fecha", "emisora"], keep="last")
        .reset_index(drop=True)
    )
    return comb


def extraer_ventanas_y_features_en_fecha(
    serie_unificada: pd.DataFrame,
    fecha_corte: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Para una fecha de corte BMV (ej. 2026-10-28 o 2026-10-29):
    1. Determina las 21 sesiones habiles BMV exactas que terminan en fecha_corte.
    2. Audita las 15 emisoras: documenta cuantas sesiones con PPP verificado tiene cada una
       en esa ventana de 21 sesiones (sin comprimir huecos ni rellenar).
    3. Calcula las 8 variables canonicas PPP_V2_MEDIA20 para las emisoras con 21/21 sesiones
       y calcula el retorno relativo intrapanel (ret_10_rel_panel) entre ellas.
    """
    if not is_bmv_business_day(date.fromisoformat(fecha_corte)):
        raise ValueError(f"La fecha {fecha_corte} no es sesion habil de la BMV.")

    todas_sesiones = sesiones_entre("2026-08-01", fecha_corte)
    if len(todas_sesiones) < 21 or todas_sesiones[-1] != fecha_corte:
        raise ValueError(f"No hay 21 sesiones habiles previas para {fecha_corte}.")
    fechas_21 = todas_sesiones[-21:]
    validar_ventana_fechas(fechas_21, fecha_corte)

    emisoras_15 = sorted(serie_unificada["emisora"].astype(str).unique().tolist())
    filas_estado: list[dict[str, Any]] = []
    filas_elegibles: list[dict[str, Any]] = []

    for em in emisoras_15:
        sub_em = (
            serie_unificada[serie_unificada["emisora"] == em]
            .set_index("fecha")
            .reindex(fechas_21)
        )
        meta_em = serie_unificada[serie_unificada["emisora"] == em].iloc[-1]
        serie_str = str(meta_em["serie"])
        sector_str = str(meta_em["sector_economico"])
        anillo_str = str(meta_em["anillo_madurez"])

        precios_21 = sub_em["ppp_bmv_mxn"].to_numpy(dtype=float)
        mask_finitos = np.isfinite(precios_21) & (precios_21 > 0)
        n_presentes = int(np.sum(mask_finitos))
        n_huecos = int(21 - n_presentes)
        fechas_faltantes = [
            f for f, ok in zip(fechas_21, mask_finitos) if not ok
        ]

        fila_corte = sub_em.loc[fecha_corte]
        ppp_hoy = float(fila_corte["ppp_bmv_mxn"]) if np.isfinite(fila_corte["ppp_bmv_mxn"]) else np.nan
        sha_hoy = str(fila_corte["sha256_boletin"]) if pd.notna(fila_corte["sha256_boletin"]) else "SIN_BOLETIN"
        url_hoy = str(fila_corte["url_fuente"]) if pd.notna(fila_corte["url_fuente"]) else "SIN_URL"
        evidencia_hoy = str(fila_corte["evidencia_exacta"]) if pd.notna(fila_corte["evidencia_exacta"]) else "SIN_EVIDENCIA"

        apta_21 = bool(n_presentes == 21)
        filas_estado.append(
            {
                "fecha_corte": fecha_corte,
                "emisora": em,
                "serie": serie_str,
                "sector_economico": sector_str,
                "anillo_madurez": anillo_str,
                "ppp_fecha_corte": ppp_hoy,
                "sesiones_con_ppp_en_ventana_21": n_presentes,
                "huecos_en_ventana_21": n_huecos,
                "ventana_21_completa_apta_inferencia": apta_21,
                "inicio_ventana_21": fechas_21[0],
                "fin_ventana_21": fechas_21[-1],
                "fechas_huecos_ventana_21": ";".join(fechas_faltantes) if fechas_faltantes else "NINGUNO",
                "estado_inferencia_g2": (
                    "ELEGIBLE_VENTANA_21_COMPLETA"
                    if apta_21
                    else f"BLOQUEADA_HUECOS_REALES_{n_presentes}_DE_21"
                ),
            }
        )

        if apta_21:
            feats = calcular_features_ppp(precios_21)
            fila_feat = {
                "fecha": fecha_corte,
                "emisora": em,
                "serie": serie_str,
                "sector_economico": sector_str,
                "anillo_madurez": anillo_str,
                "ppp_t": ppp_hoy,
                "inicio_ventana_21": fechas_21[0],
                "fin_ventana_21": fechas_21[-1],
                "sha256_boletin": sha_hoy,
                "url_fuente": url_hoy,
                "evidencia_exacta": evidencia_hoy,
            }
            for nombre_f, val_f in zip(FEATURE_NAMES, feats):
                fila_feat[nombre_f] = float(val_f)
            filas_elegibles.append(fila_feat)

    df_estado = pd.DataFrame(filas_estado)
    df_elegibles = pd.DataFrame(filas_elegibles)
    if not df_elegibles.empty:
        media_ret_10 = float(df_elegibles["ret_10"].mean())
        n_em_corte = len(df_elegibles)
        df_elegibles["media_ret_10_panel_corte"] = media_ret_10
        df_elegibles["n_emisoras_panel_corte"] = int(n_em_corte)
        df_elegibles["ret_10_rel_panel"] = (
            df_elegibles["ret_10"] - media_ret_10 if n_em_corte >= 2 else 0.0
        )

    return df_estado, df_elegibles


def preparar_panel_entrenamiento_para_corte(
    panel_path: Path,
    fecha_corte: str,
    modo_entrenamiento: str,
) -> pd.DataFrame:
    """
    Construye el conjunto de entrenamiento del panel garantizando cero fuga temporal:
    - Si modo_entrenamiento == 'TRAIN_CONGELADO': usa exclusivamente TRAIN (<= 2025-04-29).
    - Si modo_entrenamiento == 'HISTORIA_PURGADA_HASTA_CORTE': usa todas las observaciones
      historicas cuya etiqueta ya vencio al cierre de fecha_corte (fecha_objetivo_h5 <= fecha_corte
      y fecha < fecha_corte).
    """
    raw = pd.read_csv(panel_path, dtype=str)
    raw["fecha"] = pd.to_datetime(raw["fecha"], errors="raise").dt.strftime("%Y-%m-%d")
    raw["fecha_objetivo_h5"] = pd.to_datetime(
        raw["fecha_objetivo_h5"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    limite_corte = CORTE_TRAIN if modo_entrenamiento == "TRAIN_CONGELADO" else fecha_corte
    sub_tiempo = raw[raw["fecha"] <= limite_corte].copy()
    if modo_entrenamiento == "TRAIN_CONGELADO":
        sub_tiempo = sub_tiempo[sub_tiempo["periodo_oficial"].astype(str) == "TRAIN"].copy()

    for col in FEATURE_NAMES:
        sub_tiempo[col] = pd.to_numeric(sub_tiempo[col], errors="coerce")

    mask_v = np.isfinite(sub_tiempo["ret_10"].to_numpy(dtype=float))
    medias = (
        sub_tiempo[mask_v]
        .groupby("fecha")["ret_10"]
        .agg(media_ret_10_panel="mean", n_emisoras_fecha="count")
        .reset_index()
    )
    sub_tiempo = sub_tiempo.merge(medias, on="fecha", how="left")
    sub_tiempo["ret_10_rel_panel"] = np.where(
        sub_tiempo["n_emisoras_fecha"].fillna(0) >= 2,
        sub_tiempo["ret_10"] - sub_tiempo["media_ret_10_panel"],
        0.0,
    )

    mask_elegible = (
        sub_tiempo["target_disponible"].astype(str).isin(["True", "true", "1"])
        & mascara_etiquetas_conocidas(sub_tiempo, limite_corte)
        & (sub_tiempo["fecha"] < fecha_corte)
        & (sub_tiempo["fecha_objetivo_h5"] <= limite_corte)
    )
    tr_df = sub_tiempo[mask_elegible].copy()
    cols_num = ["posicion_sesion", "ppp_t", "ppp_t5", "target_y", *FEATURE_NAMES, "ret_10_rel_panel"]
    for col in cols_num:
        tr_df[col] = pd.to_numeric(tr_df[col], errors="raise")
    tr_df["target_y"] = tr_df["target_y"].astype(int)
    tr_df["posicion_sesion"] = tr_df["posicion_sesion"].astype(int)

    if (tr_df["fecha_objetivo_h5"] > limite_corte).any():
        raise ValueError("Fuga detectada en preparar_panel_entrenamiento_para_corte.")
    return tr_df.sort_values(["posicion_sesion", "emisora"]).reset_index(drop=True)


def etiqueta_consenso_g2(c1: int, c2: int, c3: int) -> str:
    if c1 == c2 == c3 == 1:
        return "CONSENSO_PANEL_G2_SUBIDA"
    if c1 == c2 == c3 == 0:
        return "CONSENSO_PANEL_G2_NO_SUBIDA"
    nom = lambda c: "SUBIDA" if c == 1 else "NO_SUBIDA"
    return f"DIVERGENCIA_G2 (V1={nom(c1)}, V2={nom(c2)}, V3={nom(c3)})"


def ejecutar_monitor_prospectivo_g2(
    fechas_solicitud: list[str] | None = None,
    registro_path: Path = REGISTRO_G2_PATH,
    ventanas_path: Path = VENTANAS_G2_PATH,
    resumen_path: Path = RESUMEN_G2_PATH,
) -> dict[str, Any]:
    hashes_antes = hashes_protegidos_g2()
    serie_unificada = construir_serie_unificada_ppp()

    if fechas_solicitud is None:
        # Por defecto procesa todas las fechas prospectivas (>= 2026-10-28) presentes en la serie unificada
        fechas_disp = sorted(
            serie_unificada[serie_unificada["fecha"] >= "2026-10-28"]["fecha"].unique().tolist()
        )
        fechas_solicitud = fechas_disp

    # Preservar timestamps de emision previamente registrados para garantizar idempotencia
    timestamps_previos: dict[str, str] = {}
    if registro_path.exists():
        reg_prev = pd.read_csv(registro_path, dtype=str)
        for _, r in reg_prev.iterrows():
            timestamps_previos[str(r["id_senal_g2"])] = str(r["timestamp_emision_utc"])

    marcos_ventanas: list[pd.DataFrame] = []
    filas_senales: list[dict[str, Any]] = []

    for f_corte in sorted(fechas_solicitud):
        df_est, df_eleg = extraer_ventanas_y_features_en_fecha(serie_unificada, f_corte)
        marcos_ventanas.append(df_est)
        if df_eleg.empty:
            continue

        fecha_obj_h5 = add_bmv_sessions(f_corte, 5)
        cal_obj = calendario_objetivo(f_corte, fecha_obj_h5)

        cache_train: dict[str, pd.DataFrame] = {}
        probs_por_modelo: dict[str, np.ndarray] = {}
        meta_train_modelo: dict[str, dict[str, Any]] = {}

        for id_mod, modo_tr, c_val, tau_val, desc_mod in MODELOS_G2:
            if modo_tr not in cache_train:
                cache_train[modo_tr] = preparar_panel_entrenamiento_para_corte(
                    PANEL_PATH, f_corte, modo_tr
                )
            tr_panel = cache_train[modo_tr]
            if tau_val > 0.0:
                p_vec = ajustar_logistica_con_zona_neutral(
                    tr_panel,
                    df_eleg,
                    VARIABLES_REL_TRES,
                    c=float(c_val),
                    tau=float(tau_val),
                    modo_panel=True,
                )
            else:
                p_vec, _ = ajustar_logistica_pooled_panel(
                    tr_panel,
                    df_eleg,
                    VARIABLES_REL_TRES,
                    c=float(c_val),
                    tipo_scaler="STANDARD",
                    ponderacion="UNIFORME",
                )
            probs_por_modelo[id_mod] = p_vec
            meta_train_modelo[id_mod] = {
                "modo_entrenamiento": modo_tr,
                "n_train_panel": int(len(tr_panel)),
                "fin_etiquetas_train_panel": str(tr_panel["fecha_objetivo_h5"].max()),
                "c_regularizacion": float(c_val),
                "tau_zona_neutral": float(tau_val),
                "descripcion": desc_mod,
            }

        for idx_em, row_em in df_eleg.iterrows():
            em = str(row_em["emisora"])
            p1 = float(probs_por_modelo["G2_V1_POOLED_REL3_CALIBRADO"][idx_em])
            p2 = float(probs_por_modelo["G2_V2_POOLED_REL3_ZONA_NEUTRAL"][idx_em])
            p3 = float(probs_por_modelo["G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO"][idx_em])
            c1, c2, c3 = int(p1 >= 0.5), int(p2 >= 0.5), int(p3 >= 0.5)
            consenso_str = etiqueta_consenso_g2(c1, c2, c3)

            # Verificar seguimiento parcial (ultimo PPP posterior a f_corte y <= fecha_obj_h5)
            sub_futuro = serie_unificada[
                (serie_unificada["emisora"] == em)
                & (serie_unificada["fecha"] > f_corte)
                & (serie_unificada["fecha"] <= fecha_obj_h5)
                & (serie_unificada["ppp_bmv_mxn"].notna())
            ].sort_values("fecha")

            if not sub_futuro.empty:
                ult_fila = sub_futuro.iloc[-1]
                fecha_parcial = str(ult_fila["fecha"])
                ppp_parcial = float(ult_fila["ppp_bmv_mxn"])
                ret_parcial_pct = float((ppp_parcial / float(row_em["ppp_t"]) - 1.0) * 100.0)
                dir_parcial = int(ppp_parcial > float(row_em["ppp_t"]))
                sesiones_transcurridas = len(sesiones_entre(f_corte, fecha_parcial)) - 1
            else:
                fecha_parcial = "PENDIENTE"
                ppp_parcial = np.nan
                ret_parcial_pct = np.nan
                dir_parcial = None
                sesiones_transcurridas = 0

            # Verificar si ya vencio exactamente la fecha_obj_h5
            fila_h5 = serie_unificada[
                (serie_unificada["emisora"] == em)
                & (serie_unificada["fecha"] == fecha_obj_h5)
                & (serie_unificada["ppp_bmv_mxn"].notna())
            ]
            if not fila_h5.empty:
                ppp_t5_obs = float(fila_h5.iloc[0]["ppp_bmv_mxn"])
                y_obs = int(ppp_t5_obs > float(row_em["ppp_t"]))
                estado_res = "RESUELTA_OFICIAL_T5"
            else:
                ppp_t5_obs = np.nan
                y_obs = np.nan
                estado_res = (
                    f"EN_CURSO_T+{sesiones_transcurridas}"
                    if sesiones_transcurridas > 0
                    else "PENDIENTE_T+5"
                )

            for id_mod, _, _, _, _ in MODELOS_G2:
                prob_m = float(probs_por_modelo[id_mod][idx_em])
                clase_m = int(prob_m >= 0.5)
                etiq_m = "SUBIDA" if clase_m == 1 else "NO_SUBIDA"
                info_m = meta_train_modelo[id_mod]

                id_senal = f"G2_{f_corte.replace('-', '')}_{em}_{id_mod}"
                ts_emision = timestamps_previos.get(id_senal, timestamp_utc())

                acierto_parcial = (
                    bool(clase_m == dir_parcial) if dir_parcial is not None else np.nan
                )
                acierto_t5 = (
                    bool(clase_m == y_obs) if not np.isnan(y_obs) else np.nan
                )
                brier_t5 = (
                    float((prob_m - y_obs) ** 2) if not np.isnan(y_obs) else np.nan
                )

                filas_senales.append(
                    {
                        "id_senal_g2": id_senal,
                        "generacion_modelo": "SEGUNDA_GENERACION_POOLED_PANEL_REL3",
                        "fecha_senal": f_corte,
                        "fecha_objetivo_h5": fecha_obj_h5,
                        "calendario_objetivo": cal_obj,
                        "emisora": em,
                        "serie": str(row_em["serie"]),
                        "sector_economico": str(row_em["sector_economico"]),
                        "modelo_g2": id_mod,
                        "modo_entrenamiento": info_m["modo_entrenamiento"],
                        "n_train_panel": info_m["n_train_panel"],
                        "fin_etiquetas_train_panel": info_m["fin_etiquetas_train_panel"],
                        "c_regularizacion": info_m["c_regularizacion"],
                        "tau_zona_neutral": info_m["tau_zona_neutral"],
                        "ppp_base_t": float(row_em["ppp_t"]),
                        "ret_10": float(row_em["ret_10"]),
                        "media_ret_10_panel_corte": float(row_em["media_ret_10_panel_corte"]),
                        "ret_10_rel_panel": float(row_em["ret_10_rel_panel"]),
                        "volatilidad_20": float(row_em["volatilidad_20"]),
                        "probabilidad_subida": round(prob_m, 6),
                        "prediccion_clase": clase_m,
                        "prediccion_etiqueta": etiq_m,
                        "estado_consenso_g2": consenso_str,
                        "estado_resolucion": estado_res,
                        "sesiones_transcurridas": int(sesiones_transcurridas),
                        "fecha_parcial_reciente": fecha_parcial,
                        "ppp_parcial_reciente": ppp_parcial,
                        "retorno_parcial_pct": round(ret_parcial_pct, 4) if np.isfinite(ret_parcial_pct) else np.nan,
                        "acierto_parcial_en_curso": acierto_parcial,
                        "ppp_t5_observado": ppp_t5_obs,
                        "target_y_observado": y_obs,
                        "acierto_direccional_t5": acierto_t5,
                        "brier_observado_t5": brier_t5,
                        "inicio_ventana_21": str(row_em["inicio_ventana_21"]),
                        "fin_ventana_21": str(row_em["fin_ventana_21"]),
                        "sha256_boletin_base": str(row_em["sha256_boletin"]),
                        "url_fuente_base": str(row_em["url_fuente"]),
                        "version_features": VERSION_FEATURES,
                        "version_metodologia": VERSION_METODOLOGIA,
                        "version_monitor_g2": VERSION_MONITOR_G2,
                        "timestamp_emision_utc": ts_emision,
                    }
                )

    df_ventanas_todas = pd.concat(marcos_ventanas, ignore_index=True)
    df_senales_todas = pd.DataFrame(filas_senales)

    df_ventanas_todas.to_csv(ventanas_path, index=False)
    df_senales_todas.to_csv(registro_path, index=False)

    hashes_despues = hashes_protegidos_g2()
    if hashes_antes != hashes_despues:
        raise RuntimeError(
            "Se detecto una modificacion no autorizada en archivos protegidos durante ejecutar_monitor_prospectivo_g2."
        )

    # Construir resumen ejecutivo JSON
    en_curso = df_senales_todas[df_senales_todas["sesiones_transcurridas"] > 0].copy()
    resumen_en_curso: dict[str, Any] = {}
    if not en_curso.empty:
        for mod_id in [m[0] for m in MODELOS_G2]:
            sub_m = en_curso[en_curso["modelo_g2"] == mod_id]
            aciertos = int(sub_m["acierto_parcial_en_curso"].eq(True).sum())
            total_m = int(len(sub_m))
            resumen_en_curso[mod_id] = {
                "emisoras_en_seguimiento_parcial": total_m,
                "aciertos_parciales_t1": aciertos,
                "tasa_acierto_parcial_pct": round(100.0 * aciertos / total_m, 2) if total_m else None,
            }

    resumen = {
        "version_monitor_g2": VERSION_MONITOR_G2,
        "timestamp_actualizacion_utc": timestamp_utc(),
        "fechas_procesadas": sorted(fechas_solicitud),
        "total_senales_emitidas_g2": int(len(df_senales_todas)),
        "emisoras_con_ventana_21_completa": sorted(
            df_senales_todas["emisora"].unique().tolist()
        ),
        "seguimiento_parcial_en_curso": resumen_en_curso,
        "detalle_senales": df_senales_todas[
            [
                "fecha_senal",
                "fecha_objetivo_h5",
                "emisora",
                "modelo_g2",
                "ppp_base_t",
                "ret_10",
                "ret_10_rel_panel",
                "volatilidad_20",
                "probabilidad_subida",
                "prediccion_etiqueta",
                "estado_consenso_g2",
                "estado_resolucion",
                "ppp_parcial_reciente",
                "retorno_parcial_pct",
                "acierto_parcial_en_curso",
            ]
        ].to_dict(orient="records"),
        "hashes_archivos_generados": {
            (
                str(registro_path.relative_to(ROOT))
                if registro_path.is_relative_to(ROOT)
                else registro_path.name
            ): sha(registro_path),
            (
                str(ventanas_path.relative_to(ROOT))
                if ventanas_path.is_relative_to(ROOT)
                else ventanas_path.name
            ): sha(ventanas_path),
        },
        "integridad_archivos_protegidos_intacta": True,
    }
    resumen_path.write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return resumen


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Monitor Prospectivo de Segunda Generacion (Pooled Panel + Retorno Relativo Intrapanel)."
    )
    parser.add_argument(
        "--fechas",
        nargs="*",
        default=None,
        help="Fechas de corte YYYY-MM-DD a evaluar (por defecto todas las >= 2026-10-28).",
    )
    args = parser.parse_args()
    res = ejecutar_monitor_prospectivo_g2(fechas_solicitud=args.fechas)
    print(json.dumps(res, indent=2, ensure_ascii=False))
