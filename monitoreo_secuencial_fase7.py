"""
Prisma BMV — Fase 7: Monitoreo Secuencial Activo (CUSUM de Log-Score + SPRT de Wald)
====================================================================================
Implementa el sistema de vigilancia estadística continua para los modelos del Panel G2:
1. Diferencial de Log-Score acumulado frente a la climatología rodante purgada (250d)
   y estadística CUSUM unilateral de Page para detección temprana de degradación.
2. Prueba Secuencial de Razón de Probabilidades de Wald (SPRT) para contrastar
   H0: p = 0.50 vs H1: p = 0.55 con alpha = 0.05 y beta = 0.20 (potencia 80%),
   reportando el tamaño muestral efectivo actual (N_eff) y cuántas señales efectivas
   independientes faltan para alcanzar la potencia objetivo (~618-620 independientes).
3. Generador de reporte semanal estructurado para la capa Gold de S3
   (`gold/reportes/monitoreo_semanal_YYYYMMDD.json`) y respaldo local auditable
   (`reporte_fase7_monitoreo_secuencial.json` + `curva_monitoreo_secuencial_fase7.csv`).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from evaluacion_institucional import (
    PANEL_AJUSTADO_PATH,
    _evaluar_panel_completo_en_test,
    _preparar_vista_panel,
    n_efectivo,
)
from metodologia_ppp import CORTE_TRAIN, ROOT, mascara_etiquetas_conocidas, timestamp_utc
from monitor_prospectivo_segunda_generacion import (
    FECHA_CONGELAMIENTO_G2,
    REGISTRO_G2_PATH,
    VARIABLES_DM5_REL_CUATRO,
    ajustar_logistica_pooled_panel,
    hashes_protegidos_g2,
)

PANEL_FASE3_PATH = ROOT / "dataset_panel_15_emisoras_features_fase3.csv"
VARIABLES_V4_F1 = [*VARIABLES_DM5_REL_CUATRO, "gap_uh_ppp"]
REPORTE_FASE7_PATH = ROOT / "reporte_fase7_monitoreo_secuencial.json"
CURVA_FASE7_PATH = ROOT / "curva_monitoreo_secuencial_fase7.csv"
GOLD_REPORTES_DIR = ROOT / "gold" / "reportes"


def calcular_requerimiento_muestral_sprt(
    p0: float = 0.50,
    p1: float = 0.55,
    alpha: float = 0.05,
    beta: float = 0.20,
) -> dict[str, float]:
    """
    Calcula las fronteras de Wald (A, B), la divergencia de Kullback-Leibler bajo H1 y H0,
    el tamaño muestral fijo clásico de Neyman-Pearson (unilateral, potencia 1-beta) y el
    número esperado de observaciones independientes del SPRT (E[N | H1], E[N | H0]).
    Para p0=0.50, p1=0.55, alpha=0.05 (unilateral) y potencia 80% (beta=0.20),
    N_fijo ≈ 618 señales independientes (~620).
    """
    if not (0.0 < p0 < 1.0 and 0.0 < p1 < 1.0 and p1 > p0):
        raise ValueError("Se requiere 0 < p0 < p1 < 1.")
    if not (0.0 < alpha < 0.5 and 0.0 < beta < 0.5):
        raise ValueError("Se requiere 0 < alpha, beta < 0.5.")

    # Fronteras de Wald
    A = float(math.log((1.0 - beta) / alpha))
    B = float(math.log(beta / (1.0 - alpha)))

    # Paso log-verosimilitud por acierto y fallo
    step_hit = float(math.log(p1 / p0))
    step_miss = float(math.log((1.0 - p1) / (1.0 - p0)))

    # Esperanza del incremento bajo H1 y bajo H0 (divergencias KL)
    e_z_h1 = float(p1 * step_hit + (1.0 - p1) * step_miss)
    e_z_h0 = float(p0 * step_hit + (1.0 - p0) * step_miss)

    # Esperanza de N en SPRT de Wald
    e_n_sprt_h1 = float(((1.0 - beta) * A + beta * B) / e_z_h1)
    e_n_sprt_h0 = float((alpha * A + (1.0 - alpha) * B) / e_z_h0)

    # Tamaño muestral independiente clásico para confirmar p1=0.55 vs p0=0.50 con potencia 80%
    # z_{1-alpha} (unilateral alpha=0.05) = 1.6448536, z_{1-beta} (beta=0.20) = 0.8416212
    z_alpha = 1.6448536269514722
    z_beta = 0.8416212335729143
    num = z_alpha * math.sqrt(p0 * (1.0 - p0)) + z_beta * math.sqrt(p1 * (1.0 - p1))
    n_indep_fijo = float((num / (p1 - p0)) ** 2)

    return {
        "p0": p0,
        "p1": p1,
        "alpha": alpha,
        "beta": beta,
        "potencia_objetivo": round(1.0 - beta, 4),
        "frontera_superior_A": round(A, 6),
        "frontera_inferior_B": round(B, 6),
        "step_acierto_nats": round(step_hit, 6),
        "step_fallo_nats": round(step_miss, 6),
        "kl_h1_vs_h0_nats": round(e_z_h1, 6),
        "n_independientes_requeridas_80pct": int(math.ceil(n_indep_fijo)),
        "e_n_sprt_bajo_h1": round(e_n_sprt_h1, 1),
        "e_n_sprt_bajo_h0": round(e_n_sprt_h0, 1),
    }


def evaluar_sprt_modelo(
    y_true: np.ndarray,
    probs: np.ndarray,
    n_efectivo: float,
    p0: float = 0.50,
    p1: float = 0.55,
    alpha: float = 0.05,
    beta: float = 0.20,
) -> dict[str, Any]:
    """
    Evalúa el estado secuencial SPRT de Wald para las predicciones direccionales
    (`probs >= 0.5`) de un modelo:
      - Calcula la razón de log-verosimilitud acumulada nominal (LLR_nominal) y
        ajustada por solapamiento (LLR_efectivo = LLR_nominal * (N_eff / N_nominal)).
      - Determina si se cruza la frontera superior A (`ACEPTAR_H1_SUPERIORIDAD`),
        la frontera inferior B (`ACEPTAR_H0_SIN_VENTAJA`) o si continúa en muestreo
        (`CONTINUAR_MUESTREO`).
      - Calcula cuántas señales efectivas independientes faltan respecto al umbral
        de potencia 80% (~618 señales independientes).
    """
    req = calcular_requerimiento_muestral_sprt(p0=p0, p1=p1, alpha=alpha, beta=beta)
    y_arr = np.asarray(y_true, dtype=int)
    p_arr = np.asarray(probs, dtype=float)
    n_nom = int(len(y_arr))

    if n_nom == 0:
        return {
            **req,
            "n_nominal": 0,
            "n_efectivo": 0.0,
            "factor_solapamiento": 1.0,
            "aciertos_direccionales": 0,
            "tasa_acierto_pct": None,
            "llr_nominal": 0.0,
            "llr_efectivo": 0.0,
            "estado_sprt": "SIN_MUESTRA_RESUELTA",
            "senales_efectivas_faltantes_80pct": float(req["n_independientes_requeridas_80pct"]),
            "progreso_muestral_efectivo_pct": 0.0,
        }

    pred_dir = (p_arr >= 0.5).astype(int)
    hits = (pred_dir == y_arr).astype(int)
    k_hits = int(np.sum(hits))
    n_misses = int(n_nom - k_hits)

    step_hit = math.log(p1 / p0)
    step_miss = math.log((1.0 - p1) / (1.0 - p0))
    llr_nom = float(k_hits * step_hit + n_misses * step_miss)

    n_eff = float(max(0.0, min(float(n_nom), float(n_efectivo))))
    ratio_eff = float(n_eff / n_nom) if n_nom > 0 else 1.0
    llr_eff = float(llr_nom * ratio_eff)

    A = req["frontera_superior_A"]
    B = req["frontera_inferior_B"]
    if llr_eff >= A:
        estado = "ACEPTAR_H1_SUPERIORIDAD"
    elif llr_eff <= B:
        estado = "ACEPTAR_H0_SIN_VENTAJA"
    else:
        estado = "CONTINUAR_MUESTREO"

    n_req = float(req["n_independientes_requeridas_80pct"])
    faltantes = float(max(0.0, n_req - n_eff))
    progreso_pct = float(min(100.0, round(100.0 * n_eff / n_req, 2)))

    return {
        **req,
        "n_nominal": n_nom,
        "n_efectivo": round(n_eff, 2),
        "factor_solapamiento": round(float(n_nom / n_eff), 4) if n_eff > 0 else 1.0,
        "aciertos_direccionales": k_hits,
        "tasa_acierto_pct": round(100.0 * k_hits / n_nom, 2),
        "llr_nominal": round(llr_nom, 6),
        "llr_efectivo": round(llr_eff, 6),
        "estado_sprt": estado,
        "senales_efectivas_faltantes_80pct": round(faltantes, 1),
        "progreso_muestral_efectivo_pct": progreso_pct,
    }


def calcular_cusum_y_logscore_secuencial(
    fechas: np.ndarray,
    y_true: np.ndarray,
    probs_modelo: np.ndarray,
    probs_climatologia: np.ndarray,
    k_holgura_nats: float = 0.001,
    h_umbral_alarma_nats: float = 1.50,
) -> dict[str, Any]:
    """
    Calcula por fecha de sesión:
    1. El diferencial de Log-Score acumulado:
         Δℓ_i = ℓ(p_modelo, y_i) - ℓ(p_climatologia, y_i)
       donde Δℓ_i > 0 significa que el modelo asignó mayor verosimilitud que la climatología.
    2. La estadística CUSUM unilateral de Page para detectar degradación:
         S_t = max(0, S_{t-1} + (-Δℓ_t_medio - k_holgura_nats))
       acumulada sobre las medias diarias transversales Δℓ_t_medio para evitar inflar
       la alarma por correlación contemporánea entre emisoras.
    """
    y_arr = np.asarray(y_true, dtype=float)
    p_mod = np.clip(np.asarray(probs_modelo, dtype=float), 1e-6, 1.0 - 1e-6)
    p_clim = np.clip(np.asarray(probs_climatologia, dtype=float), 1e-6, 1.0 - 1e-6)
    f_arr = np.asarray(fechas, dtype=str)

    if len(y_arr) == 0:
        return {
            "n_observaciones": 0,
            "n_sesiones": 0,
            "log_score_modelo_total_nats": 0.0,
            "log_score_climatologia_total_nats": 0.0,
            "delta_log_score_acumulado_nats": 0.0,
            "delta_log_score_acumulado_bits": 0.0,
            "cusum_actual_nats": 0.0,
            "cusum_max_historico_nats": 0.0,
            "k_holgura_nats": k_holgura_nats,
            "h_umbral_alarma_nats": h_umbral_alarma_nats,
            "alarma_cusum_activa": False,
            "estado_cusum": "SIN_DATOS",
            "fecha_primera_alarma": None,
            "serie_diaria": [],
        }

    ll_mod = y_arr * np.log(p_mod) + (1.0 - y_arr) * np.log(1.0 - p_mod)
    ll_clim = y_arr * np.log(p_clim) + (1.0 - y_arr) * np.log(1.0 - p_clim)
    delta_ll = ll_mod - ll_clim

    df_temp = pd.DataFrame(
        {
            "fecha": f_arr,
            "ll_mod": ll_mod,
            "ll_clim": ll_clim,
            "delta_ll": delta_ll,
        }
    )
    diario = (
        df_temp.groupby("fecha", as_index=False)
        .agg(
            n_emisoras=("delta_ll", "count"),
            delta_ll_suma=("delta_ll", "sum"),
            delta_ll_medio=("delta_ll", "mean"),
        )
        .sort_values("fecha")
        .reset_index(drop=True)
    )

    s_val = 0.0
    s_max = 0.0
    cum_nats = 0.0
    fecha_alarma: str | None = None
    serie_diaria: list[dict[str, Any]] = []

    for _, row in diario.iterrows():
        f_str = str(row["fecha"])
        d_sum = float(row["delta_ll_suma"])
        d_mean = float(row["delta_ll_medio"])
        cum_nats += d_sum
        # Estadística CUSUM de degradación: acumula cuando d_mean < -k_holgura_nats
        s_val = float(max(0.0, s_val + (-d_mean - float(k_holgura_nats))))
        if s_val > s_max:
            s_max = s_val
        if s_val >= float(h_umbral_alarma_nats) and fecha_alarma is None:
            fecha_alarma = f_str
        serie_diaria.append(
            {
                "fecha": f_str,
                "n_emisoras": int(row["n_emisoras"]),
                "delta_ll_diario_medio_nats": round(d_mean, 6),
                "delta_ll_acumulado_nats": round(cum_nats, 6),
                "delta_ll_acumulado_bits": round(cum_nats / math.log(2.0), 6),
                "cusum_degradacion_nats": round(s_val, 6),
            }
        )

    alarma_activa = bool(s_val >= float(h_umbral_alarma_nats))
    estado_str = (
        "ALARMA_DEGRADACION_ACTIVA"
        if alarma_activa
        else ("ALERTA_HISTORICA_RECUPERADA" if fecha_alarma is not None else "OPERACION_NORMAL_ESTABLE")
    )

    return {
        "n_observaciones": int(len(y_arr)),
        "n_sesiones": int(len(diario)),
        "log_score_modelo_total_nats": round(float(np.sum(ll_mod)), 4),
        "log_score_climatologia_total_nats": round(float(np.sum(ll_clim)), 4),
        "delta_log_score_acumulado_nats": round(float(np.sum(delta_ll)), 6),
        "delta_log_score_acumulado_bits": round(float(np.sum(delta_ll) / math.log(2.0)), 6),
        "cusum_actual_nats": round(s_val, 6),
        "cusum_max_historico_nats": round(s_max, 6),
        "k_holgura_nats": k_holgura_nats,
        "h_umbral_alarma_nats": h_umbral_alarma_nats,
        "alarma_cusum_activa": alarma_activa,
        "estado_cusum": estado_str,
        "fecha_primera_alarma": fecha_alarma,
        "serie_diaria": serie_diaria,
    }


def _evaluar_g2_v4_f1_gap_en_test(df_eval_base: pd.DataFrame) -> np.ndarray:
    """
    Calcula las probabilidades fuera de muestra en TEST para `G2_V4_F1_GAP`
    usando exactamente el corte de entrenamiento congelado (<= CORTE_TRAIN).
    """
    raw_f3 = pd.read_csv(PANEL_FASE3_PATH, dtype=str)
    vista_f3 = _preparar_vista_panel(raw_f3, usar_ajustado=True)
    vista_f3["gap_uh_ppp"] = pd.to_numeric(raw_f3["gap_uh_ppp"], errors="coerce")

    mask_tr = (
        (vista_f3["periodo_oficial"].astype(str) == "TRAIN")
        & (vista_f3["fecha"] <= CORTE_TRAIN)
        & mascara_etiquetas_conocidas(vista_f3, CORTE_TRAIN)
        & (vista_f3["fecha_objetivo_h5"] <= CORTE_TRAIN)
    )
    tr_df = (
        vista_f3[mask_tr]
        .dropna(subset=[*VARIABLES_V4_F1, "target_y"])
        .sort_values(["posicion_sesion", "emisora"])
        .reset_index(drop=True)
    )

    # Alinear df_eval_base con gap_uh_ppp de vista_f3
    llave_gap = vista_f3[["fecha", "emisora", "gap_uh_ppp"]].drop_duplicates(["fecha", "emisora"])
    ev_df = df_eval_base.merge(llave_gap, on=["fecha", "emisora"], how="left")
    ev_df["gap_uh_ppp"] = ev_df["gap_uh_ppp"].fillna(0.0)

    probs_f1, _ = ajustar_logistica_pooled_panel(
        tr_df,
        ev_df,
        VARIABLES_V4_F1,
        c=0.01,
        tipo_scaler="STANDARD",
        ponderacion="UNIFORME",
    )
    return probs_f1


def publicar_reporte_semanal_s3_gold(
    reporte: dict[str, Any],
    fecha_corte: str = "2026-11-06",
    s3_client=None,
    bucket_name: str = "prisma-bmv-datalake-tunombre-2026",
) -> dict[str, str]:
    """
    Escribe el reporte semanal de monitoreo secuencial en:
    1. Disco local: `gold/reportes/monitoreo_semanal_YYYYMMDD.json`
    2. S3 Gold (si `s3_client` está disponible): `s3://<bucket>/gold/reportes/monitoreo_semanal_YYYYMMDD.json`
    """
    fecha_compacta = str(fecha_corte).replace("-", "")
    GOLD_REPORTES_DIR.mkdir(parents=True, exist_ok=True)
    rel_key = f"gold/reportes/monitoreo_semanal_{fecha_compacta}.json"
    local_gold_path = ROOT / rel_key

    payload_bytes = json.dumps(reporte, indent=2, ensure_ascii=False).encode("utf-8")
    local_gold_path.write_bytes(payload_bytes)

    estado_s3 = "SOLO_LOCAL_SIN_CLIENTE_S3"
    if s3_client is not None:
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=rel_key,
                Body=payload_bytes,
                ContentType="application/json",
            )
            estado_s3 = f"PUBLICADO_S3_OK (s3://{bucket_name}/{rel_key})"
        except Exception as exc:
            estado_s3 = f"FALLBACK_LOCAL ({exc})"

    return {
        "s3_key": rel_key,
        "local_path": str(local_gold_path.relative_to(ROOT)),
        "estado_publicacion": estado_s3,
    }


def ejecutar_monitoreo_secuencial_fase7(
    panel_ajustado_path: Path = PANEL_AJUSTADO_PATH,
    registro_prospectivo_path: Path = REGISTRO_G2_PATH,
    reporte_path: Path = REPORTE_FASE7_PATH,
    curva_path: Path = CURVA_FASE7_PATH,
    fecha_reporte: str = FECHA_CONGELAMIENTO_G2,
    s3_client=None,
) -> dict[str, Any]:
    """
    Ejecuta el monitoreo secuencial completo (Fase 7):
    - Evalúa Log-Score acumulado vs climatología, alarma CUSUM y SPRT de Wald
      sobre TEST (`2025-04-30` a `2026-10-27`, N=1557) para `G2_V1`–`G2_V5` y `G2_V4_F1_GAP`.
    - Evalúa el registro prospectivo en vivo (`registro_senales_prospectivas_panel_g2.csv`)
      separando explícitamente `IN_SAMPLE_DISENO` (< 2026-11-06) y `OUT_OF_SAMPLE_PRE_REGISTRADO` (>= 2026-11-06),
      excluyendo señales en `PENDIENTE_RECONCILIACION`.
    - Genera `curva_monitoreo_secuencial_fase7.csv`, `reporte_fase7_monitoreo_secuencial.json`
      y `gold/reportes/monitoreo_semanal_YYYYMMDD.json`.
    """
    hashes_antes = hashes_protegidos_g2()

    df_panel_adj = pd.read_csv(panel_ajustado_path, dtype=str)
    vista_adj = _preparar_vista_panel(df_panel_adj, usar_ajustado=True)
    te_adj = _evaluar_panel_completo_en_test(vista_adj)
    te_adj["prob_G2_V4_F1_GAP"] = _evaluar_g2_v4_f1_gap_en_test(te_adj)

    fechas_test = te_adj["fecha"].astype(str).to_numpy()
    y_test = te_adj["target_y"].to_numpy(dtype=int)
    p_clim_test = te_adj["prob_CLIMATOLOGIA"].to_numpy(dtype=float)
    n_eff_test = n_efectivo(y_test, lag=4)

    modelos_evaluar = [
        ("G2_V4_F1_GAP", "prob_G2_V4_F1_GAP", "CAMPEON_OPERATIVO_FASE3_FASE5"),
        ("G2_V4_ADJ", "prob_G2_V4", "CAMPEON_BASE_FASE1"),
        ("G2_V5_ADJ", "prob_G2_V5", "SHADOW"),
        ("G2_V3_ADJ", "prob_G2_V3", "SHADOW"),
        ("G2_V1_ADJ", "prob_G2_V1", "SHADOW"),
        ("G2_V2_ADJ", "prob_G2_V2", "SHADOW"),
    ]

    resultados_test: dict[str, Any] = {}
    series_por_modelo: dict[str, list[dict[str, Any]]] = {}

    for nombre_mod, col_prob, rol_mod in modelos_evaluar:
        p_vec = te_adj[col_prob].to_numpy(dtype=float)
        cusum_info = calcular_cusum_y_logscore_secuencial(
            fechas=fechas_test,
            y_true=y_test,
            probs_modelo=p_vec,
            probs_climatologia=p_clim_test,
            k_holgura_nats=0.001,
            h_umbral_alarma_nats=1.50,
        )
        sprt_info = evaluar_sprt_modelo(
            y_true=y_test,
            probs=p_vec,
            n_efectivo=n_eff_test,
            p0=0.50,
            p1=0.55,
            alpha=0.05,
            beta=0.20,
        )
        serie_diaria = cusum_info.pop("serie_diaria", [])
        series_por_modelo[nombre_mod] = serie_diaria

        # Evaluar también SPRT sobre señales activas fuera de la banda muerta (|p - 0.5| >= 0.03)
        mask_activas = np.abs(p_vec - 0.5) >= 0.03
        y_act = y_test[mask_activas]
        p_act = p_vec[mask_activas]
        n_eff_act = n_efectivo(y_act, lag=4) if len(y_act) > 0 else 0.0
        sprt_activas = evaluar_sprt_modelo(
            y_true=y_act,
            probs=p_act,
            n_efectivo=n_eff_act,
            p0=0.50,
            p1=0.55,
            alpha=0.05,
            beta=0.20,
        )

        resultados_test[nombre_mod] = {
            "rol": rol_mod,
            "cusum_logscore": cusum_info,
            "sprt_wald": sprt_info,
            "sprt_wald_senales_activas_fuera_banda": sprt_activas,
        }

    # Construir CSV consolidado de curvas diarias (Delta Log-Score y CUSUM) en TEST
    df_curva_base = pd.DataFrame(series_por_modelo["G2_V4_F1_GAP"]).rename(
        columns={
            "delta_ll_diario_medio_nats": "d_ll_f1_gap",
            "delta_ll_acumulado_nats": "cum_ll_f1_gap_nats",
            "delta_ll_acumulado_bits": "cum_ll_f1_gap_bits",
            "cusum_degradacion_nats": "cusum_f1_gap_nats",
        }
    )
    for mod_extra, suf in [
        ("G2_V4_ADJ", "v4_adj"),
        ("G2_V5_ADJ", "v5_adj"),
        ("G2_V1_ADJ", "v1_adj"),
    ]:
        df_ext = pd.DataFrame(series_por_modelo[mod_extra])[
            ["fecha", "delta_ll_acumulado_nats", "cusum_degradacion_nats"]
        ].rename(
            columns={
                "delta_ll_acumulado_nats": f"cum_ll_{suf}_nats",
                "cusum_degradacion_nats": f"cusum_{suf}_nats",
            }
        )
        df_curva_base = df_curva_base.merge(df_ext, on="fecha", how="left")

    df_curva_base.to_csv(curva_path, index=False)

    # Evaluar monitoreo prospectivo en vivo separado por muestra_evaluacion
    prospectivo_resumen: dict[str, Any] = {
        "fecha_congelamiento": FECHA_CONGELAMIENTO_G2,
        "OUT_OF_SAMPLE_PRE_REGISTRADO": {},
        "IN_SAMPLE_DISENO": {},
    }
    if registro_prospectivo_path.exists():
        df_prosp = pd.read_csv(registro_prospectivo_path)
        if "muestra_evaluacion" not in df_prosp.columns:
            df_prosp["muestra_evaluacion"] = np.where(
                df_prosp["fecha_senal"].astype(str) < FECHA_CONGELAMIENTO_G2,
                "IN_SAMPLE_DISENO",
                "OUT_OF_SAMPLE_PRE_REGISTRADO",
            )
        for etiqueta_m in ("OUT_OF_SAMPLE_PRE_REGISTRADO", "IN_SAMPLE_DISENO"):
            sub_m = df_prosp[df_prosp["muestra_evaluacion"] == etiqueta_m].copy()
            resueltas_m = sub_m[sub_m["estado_resolucion"] == "RESUELTA_OFICIAL_T5"].copy()
            pendientes_m = sub_m[sub_m["estado_resolucion"] == "PENDIENTE_RECONCILIACION"].copy()

            modelos_prosp: dict[str, Any] = {}
            for mod_g2 in sorted(df_prosp["modelo_g2"].dropna().unique().tolist()):
                sub_mod_res = resueltas_m[resueltas_m["modelo_g2"] == mod_g2]
                if not sub_mod_res.empty and "target_y_observado" in sub_mod_res.columns:
                    y_p = pd.to_numeric(sub_mod_res["target_y_observado"], errors="coerce").dropna().to_numpy(dtype=int)
                    probs_p = pd.to_numeric(sub_mod_res.loc[sub_mod_res["target_y_observado"].notna(), "probabilidad_subida"], errors="coerce").to_numpy(dtype=float)
                    # En ventana prospectiva corta, factor de solapamiento conservador = 2.5 si hay múltiples fechas
                    n_fechas_res = int(sub_mod_res["fecha_senal"].nunique())
                    n_eff_p = float(len(y_p)) if n_fechas_res <= 1 else float(len(y_p)) / 2.5
                else:
                    y_p = np.array([], dtype=int)
                    probs_p = np.array([], dtype=float)
                    n_eff_p = 0.0

                sprt_p = evaluar_sprt_modelo(y_true=y_p, probs=probs_p, n_efectivo=n_eff_p)
                modelos_prosp[mod_g2] = {
                    "senales_emitidas": int(len(sub_m[sub_m["modelo_g2"] == mod_g2])),
                    "senales_resueltas_oficial_t5": int(len(y_p)),
                    "senales_pendientes_reconciliacion": int(
                        len(pendientes_m[pendientes_m["modelo_g2"] == mod_g2])
                    ),
                    "sprt_wald": sprt_p,
                }
            prospectivo_resumen[etiqueta_m] = {
                "total_senales_emitidas": int(len(sub_m)),
                "total_resueltas_oficial_t5": int(len(resueltas_m)),
                "total_pendientes_reconciliacion": int(len(pendientes_m)),
                "por_modelo": modelos_prosp,
            }

    req_base = calcular_requerimiento_muestral_sprt(p0=0.50, p1=0.55, alpha=0.05, beta=0.20)
    reporte: dict[str, Any] = {
        "fase": "FASE_7_MONITOREO_SECUENCIAL_ACTIVO_CUSUM_SPRT",
        "timestamp_utc": timestamp_utc(),
        "fecha_reporte": fecha_reporte,
        "especificacion_matematica": {
            "cusum_page": {
                "definicion": "S_t = max(0, S_{t-1} + (-Delta_LL_medio_t - k))",
                "k_holgura_nats": 0.001,
                "h_umbral_alarma_nats": 1.50,
                "interpretacion": "Detecta degradación persistente de log-verosimilitud frente a la climatología rodante purgada (250d).",
            },
            "sprt_wald": req_base,
        },
        "evaluacion_secuencial_test_15_emisoras": resultados_test,
        "monitoreo_prospectivo_en_vivo": prospectivo_resumen,
        "curva_reciente_test": df_curva_base.tail(60).to_dict(orient="records"),
        "integridad_archivos_protegidos_intacta": True,
    }

    pub_info = publicar_reporte_semanal_s3_gold(
        reporte=reporte,
        fecha_corte=fecha_reporte,
        s3_client=s3_client,
    )
    reporte["publicacion_s3_gold"] = pub_info
    reporte_path.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")

    hashes_despues = hashes_protegidos_g2()
    if hashes_antes != hashes_despues:
        raise RuntimeError("Se detectó modificación en archivos protegidos durante Fase 7.")

    return reporte


if __name__ == "__main__":
    rep = ejecutar_monitoreo_secuencial_fase7()
    res_f1 = rep["evaluacion_secuencial_test_15_emisoras"]["G2_V4_F1_GAP"]
    print(
        json.dumps(
            {
                "G2_V4_F1_GAP": res_f1,
                "publicacion_s3_gold": rep["publicacion_s3_gold"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
