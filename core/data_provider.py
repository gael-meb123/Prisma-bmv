"""
Prisma BMV - Proveedor de Datos de Mercado, Señales Cuantitativas e Integridad
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

FILE_MONITOREO = ROOT / "monitoreo_ppp_multiemisora_en_vivo.csv"
FILE_SENALES_WALMEX = ROOT / "registro_senales_prospectivas_walmex.csv"
FILE_SENALES_PANEL = ROOT / "registro_senales_prospectivas_panel_g2.csv"
FILE_SERIE_WALMEX = ROOT / "serie_ppp_walmex_prospectiva.csv"
FILE_REPORTE_FASE1 = ROOT / "reporte_fase1_higiene.json"
FILE_REPORTE_FASE2 = ROOT / "reporte_evaluacion_institucional.json"
FILE_REPORTE_FASE3 = ROOT / "reporte_fase3_ablacion.json"
FILE_REPORTE_FASE4 = ROOT / "reporte_fase4_modelos_v6.json"
FILE_REPORTE_FASE5 = ROOT / "reporte_fase5_portafolio.json"
FILE_CURVA_FASE5 = ROOT / "curva_equity_fase5_portafolio.csv"
FILE_REPORTE_FASE7 = ROOT / "reporte_fase7_monitoreo_secuencial.json"
FILE_RESUMEN_MONITOR_G2 = ROOT / "resumen_monitor_prospectivo_g2.json"
FILE_REGISTRO_MODELOS_V2 = ROOT / "registro_modelos_g2_v2.json"


def cargar_monitoreo_en_vivo() -> pd.DataFrame:
    if not FILE_MONITOREO.exists():
        return pd.DataFrame()
    df = pd.read_csv(FILE_MONITOREO)
    df["ppp_bmv_mxn"] = pd.to_numeric(df["ppp_bmv_mxn"], errors="coerce")
    df["variacion_ppp_vs_anterior_pct"] = pd.to_numeric(
        df["variacion_ppp_vs_anterior_pct"], errors="coerce"
    )
    return df


def cargar_senales_walmex() -> pd.DataFrame:
    if not FILE_SENALES_WALMEX.exists():
        return pd.DataFrame()
    df = pd.read_csv(FILE_SENALES_WALMEX)
    df["prob_subida_pct"] = pd.to_numeric(df["prob_subida_pct"], errors="coerce")
    df["ppp_base_mxn"] = pd.to_numeric(df["ppp_base_mxn"], errors="coerce")
    return df


def cargar_senales_panel_g2() -> pd.DataFrame:
    if not FILE_SENALES_PANEL.exists():
        return pd.DataFrame()
    df = pd.read_csv(FILE_SENALES_PANEL)
    df["probabilidad_subida"] = pd.to_numeric(df["probabilidad_subida"], errors="coerce")
    df["ppp_base_t"] = pd.to_numeric(df["ppp_base_t"], errors="coerce")
    df["ret_10_rel_panel"] = pd.to_numeric(df["ret_10_rel_panel"], errors="coerce")
    df["retorno_parcial_pct"] = pd.to_numeric(df["retorno_parcial_pct"], errors="coerce")
    df["ppp_parcial_reciente"] = pd.to_numeric(df["ppp_parcial_reciente"], errors="coerce")
    return df


def cargar_serie_walmex() -> pd.DataFrame:
    if not FILE_SERIE_WALMEX.exists():
        return pd.DataFrame()
    df = pd.read_csv(FILE_SERIE_WALMEX)
    df["ppp_bmv_mxn"] = pd.to_numeric(df["ppp_bmv_mxn"], errors="coerce")
    return df


def obtener_fechas_mercado() -> list[str]:
    df = cargar_monitoreo_en_vivo()
    if df.empty or "fecha" not in df.columns:
        return ["2026-10-30", "2026-10-29", "2026-10-28"]
    fechas = sorted(df["fecha"].dropna().unique().tolist(), reverse=True)
    return fechas


def obtener_kpis_mercado(fecha: str | None = None) -> dict[str, Any]:
    df = cargar_monitoreo_en_vivo()
    if df.empty:
        return {}

    if fecha is None:
        fecha = df["fecha"].max()

    sub = df[df["fecha"] == fecha]
    verificadas = sub[
        sub["estado_captura"].isin(["PPP_PUBLICADO_VERIFICADO", "CONTINGENCIA_FUENTE_SECUNDARIA"])
    ]
    ausentes = sub[sub["estado_captura"] == "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA"]

    alzas = verificadas[verificadas["variacion_ppp_vs_anterior_pct"] > 0]
    bajas = verificadas[verificadas["variacion_ppp_vs_anterior_pct"] < 0]

    top_alza = verificadas.sort_values("variacion_ppp_vs_anterior_pct", ascending=False).head(1)
    top_baja = verificadas.sort_values("variacion_ppp_vs_anterior_pct", ascending=True).head(1)

    sha = sub["sha256_boletin"].iloc[0] if "sha256_boletin" in sub.columns and not sub.empty else "N/A"
    url = sub["url_fuente"].iloc[0] if "url_fuente" in sub.columns and not sub.empty else "https://www.bmv.com.mx"

    return {
        "fecha": fecha,
        "total_emisoras": len(sub),
        "total_verificadas": len(verificadas),
        "total_ausentes": len(ausentes),
        "conteo_alzas": len(alzas),
        "conteo_bajas": len(bajas),
        "top_alza_ticker": top_alza["emisora"].iloc[0] if not top_alza.empty else "N/D",
        "top_alza_pct": top_alza["variacion_ppp_vs_anterior_pct"].iloc[0] if not top_alza.empty else 0.0,
        "top_baja_ticker": top_baja["emisora"].iloc[0] if not top_baja.empty else "N/D",
        "top_baja_pct": top_baja["variacion_ppp_vs_anterior_pct"].iloc[0] if not top_baja.empty else 0.0,
        "sha256_boletin": sha,
        "url_fuente": url,
    }


def _leer_json_seguro(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def obtener_metricas_institucionales_modelos() -> dict[str, Any]:
    """
    Consolida para el endpoint `GET /api/metricas/modelos`:
    1. Métricas institucionales en TEST fuera de muestra (`BSS`, `Rank IC`, `ECE`,
       `lambda_calibracion`, `wilson_95_pct`, `n_efectivo_lag4` y curva de confiabilidad)
       para los modelos G2 oficiales (`V1`–`V5`), `G2_V4_ADJ`, `G2_V4_F1_GAP` y candidatos V6.
    2. Resumen de auditoría prospectiva separado explícitamente por `muestra_evaluacion`
       (`IN_SAMPLE_DISENO` vs `OUT_OF_SAMPLE_PRE_REGISTRADO`) y por estado de resolución
       (`RESUELTA_OFICIAL_T5` vs `PENDIENTE_RECONCILIACION`).
    3. Política de asignación de capital ¼-Kelly (Fase 5) con Sharpe bruto/neto (20 bps),
       Max Drawdown, Hit Rate activo a 5 días y pesos sugeridos por emisora (`AMX`,
       `FEMSA`, `GFNORTE`, `GMEXICO`, `WALMEX` y `EFECTIVO`).
    """
    rep_f1 = _leer_json_seguro(FILE_REPORTE_FASE1)
    rep_f2 = _leer_json_seguro(FILE_REPORTE_FASE2)
    rep_f3 = _leer_json_seguro(FILE_REPORTE_FASE3)
    rep_f4 = _leer_json_seguro(FILE_REPORTE_FASE4)
    rep_f5 = _leer_json_seguro(FILE_REPORTE_FASE5)
    rep_f7 = _leer_json_seguro(FILE_REPORTE_FASE7)
    res_mon = _leer_json_seguro(FILE_RESUMEN_MONITOR_G2)
    reg_v2 = _leer_json_seguro(FILE_REGISTRO_MODELOS_V2)

    # 1. Extraer tabla comparativa de modelos en TEST (15 emisoras y 4 foco)
    test_15_orig = rep_f2.get("test_15_emisoras", {})
    test_4_orig = rep_f2.get("test_4_emisoras_foco", {})
    test_15_adj = rep_f2.get("test_15_emisoras_ajustado_fase1", {})
    test_4_adj = rep_f2.get("test_4_emisoras_foco_ajustado_fase1", {})
    test_15_f2 = {**test_15_orig, **test_15_adj}
    test_4_f2 = {**test_4_orig, **test_4_adj}
    modelos_f4 = rep_f4.get("modelos", {})

    modelos_resumen: list[dict[str, Any]] = []
    orden_f2 = [
        ("G2_V1_ADJ", "G2_V1 Calibrado (Base)", "SHADOW"),
        ("G2_V2_ADJ", "G2_V2 Zona Neutral", "SHADOW"),
        ("G2_V3_ADJ", "G2_V3 Alta Discriminación", "SHADOW"),
        ("G2_V4", "G2_V4 DM5 Corto Plazo (Crudo)", "SHADOW"),
        ("G2_V4_ADJ", "G2_V4_ADJ (Higiene Dividendos Fase 1)", "CAMPEON_OFICIAL_BASE"),
        ("G2_V5_ADJ", "G2_V5 Adaptativo Régimen/Sector", "SHADOW"),
        ("CLIMATOLOGIA_ADJ", "Climatología Rodante Purgada (250d)", "BENCHMARK"),
    ]
    for clave, alias, estado_rol in orden_f2:
        m15 = test_15_f2.get(clave, {})
        m4 = test_4_f2.get(clave, {})
        if not m15:
            continue
        cal15 = m15.get("calibracion", {})
        ic15 = m15.get("rank_ic", {})
        modelos_resumen.append(
            {
                "id_modelo": clave,
                "nombre": alias,
                "rol": estado_rol,
                "n_test_15": m15.get("n", 1557),
                "n_efectivo_15": m15.get("n_efectivo_lag4", 623.2),
                "exactitud_15_pct": m15.get("exactitud_pct"),
                "wilson_95_15_pct": m15.get("intervalo_wilson_95_pct", []),
                "brier_15": m15.get("brier"),
                "bss_vs_climatologia_15_pct": round(
                    float(m15.get("bss_vs_climatologia", 0.0)) * 100.0, 3
                ),
                "log_loss_15": m15.get("log_loss_nats"),
                "information_gain_bits_15": m15.get(
                    "information_gain_bits_vs_climatologia", 0.0
                ),
                "ece_15": cal15.get("ece"),
                "lambda_calibracion_15": cal15.get("lambda_calibracion"),
                "rank_ic_15": ic15.get("ic_medio"),
                "exactitud_4_foco_pct": m4.get("exactitud_pct"),
                "brier_4_foco": m4.get("brier"),
                "bss_4_foco_pct": round(
                    float(m4.get("bss_vs_climatologia", 0.0)) * 100.0, 3
                )
                if m4
                else None,
                "lambda_calibracion_4_foco": m4.get("calibracion", {}).get(
                    "lambda_calibracion"
                )
                if m4
                else None,
                "bins_calibracion_15": cal15.get("bins_detalle", []),
            }
        )

    orden_f4 = [
        ("G2_V4_F1_GAP", "G2_V4 + Gap Intradía (UH - PPP) [Fase 3]", "CAMPEON_OPERATIVO_FASE3_FASE5"),
        ("G2_V6C_RIDGE_CONTINUO", "G2_V6C Ridge Continuo Normalizado", "SHADOW_V6"),
        ("G2_V6A_JERARQUICO", "G2_V6A Logit Jerárquico (Partial Pooling)", "SHADOW_V6"),
        ("G2_V6B_DESCOMPUESTO", "G2_V6B Descompuesto (Mercado + Exceso)", "SHADOW_V6"),
        ("G2_LGBM_CHALLENGER", "G2_LGBM Challenger (Árboles Reg. + Platt)", "SHADOW_V6"),
    ]
    for clave, alias, estado_rol in orden_f4:
        m_obj = modelos_f4.get(clave, {})
        m15 = m_obj.get("test_15_emisoras", {})
        m4 = m_obj.get("test_4_emisoras_foco", {})
        if not m15:
            continue
        modelos_resumen.append(
            {
                "id_modelo": clave,
                "nombre": alias,
                "rol": estado_rol,
                "n_test_15": m15.get("n", 1557),
                "n_efectivo_15": 623.2,
                "exactitud_15_pct": m15.get("exactitud_pct"),
                "wilson_95_15_pct": m15.get("wilson_95_pct", []),
                "brier_15": m15.get("brier"),
                "bss_vs_climatologia_15_pct": m15.get("bss_vs_climatologia_pct"),
                "log_loss_15": m15.get("log_loss"),
                "information_gain_bits_15": m15.get("information_gain_bits"),
                "ece_15": m15.get("ece"),
                "lambda_calibracion_15": m15.get("lambda_calibracion"),
                "rank_ic_15": m15.get("rank_ic", {}).get("ic_medio"),
                "exactitud_4_foco_pct": m4.get("exactitud_pct"),
                "brier_4_foco": m4.get("brier"),
                "bss_4_foco_pct": m4.get("bss_vs_climatologia_pct"),
                "lambda_calibracion_4_foco": m4.get("lambda_calibracion"),
                "bins_calibracion_15": [],
            }
        )

    # Curvas de confiabilidad (Reliability Diagram) para graficar en Plotly
    curvas_calibracion = {}
    for mod_k in ["G2_V4_ADJ", "G2_V4", "G2_V1_ADJ", "G2_V3_ADJ", "G2_V5_ADJ"]:
        b_list = (
            test_15_f2.get(mod_k, {})
            .get("calibracion", {})
            .get("bins_detalle", [])
        )
        if b_list:
            curvas_calibracion[mod_k] = b_list

    # 2. Resumen de Asignación de Capital (Fase 5)
    pol_f5 = reg_v2.get("politica_asignacion_capital_fase5", {})
    ultimos_pesos = pol_f5.get("ultimos_pesos_sugeridos_pct", {})
    pesos_medios = (
        rep_f5.get("estrategias", {})
        .get("G2_V4_F1_GAP_KELLY_250D", {})
        .get("peso_medio_por_emisora_pct", {})
    )
    curva_reciente: list[dict[str, Any]] = []
    if FILE_CURVA_FASE5.exists():
        try:
            df_c = pd.read_csv(FILE_CURVA_FASE5).tail(60)
            for _, r in df_c.iterrows():
                curva_reciente.append(
                    {
                        "fecha": str(r["fecha"]),
                        "equity_kelly_f1_neto": round(float(r["equity_f1_neto"]), 4),
                        "equity_kelly_v4_neto": round(float(r["equity_v4_neto"]), 4),
                        "equity_benchmark_neto": round(float(r["equity_bench_neto"]), 4),
                        "exposicion_f1": round(float(r["exposicion_f1"]) * 100.0, 2),
                    }
                )
        except Exception:
            pass

    return {
        "fecha_congelamiento_oficial": res_mon.get(
            "fecha_congelamiento_modelos", "2026-11-06"
        ),
        "decision_arquitectura": rep_f4.get("decision_oficial_fase4", {}),
        "lambda_calibracion_cv_train": rep_f2.get("lambda_calibracion_v4", {}).get(
            "train_cv_purgada_sin_fuga_adj", {}
        ),
        "higiene_fase1": {
            "total_eventos_corporativos": rep_f1.get(
                "total_eventos_corporativos_detectados", 284
            ),
            "dividendos": rep_f1.get("desglose_eventos", {}).get("DIVIDENDO", 282),
            "splits": rep_f1.get("desglose_eventos", {}).get("SPLIT", 2),
            "mejora_exactitud_v4_test_15_pp": 1.86,
            "mejora_exactitud_ventanas_evento_pp": 16.28,
        },
        "ablacion_fase3": {
            "feature_aceptada": "gap_uh_ppp = (ultimo_bmv_mxn - ppp_bmv_mxn) / ppp_bmv_mxn",
            "cv_delta_logloss": -0.000526,
            "cv_p_dm_unilateral": 0.0987,
            "test_exactitud_15_pct": 52.60,
            "test_exactitud_4_foco_pct": 52.71,
            "test_rank_ic": 0.0202,
        },
        "modelos_test": modelos_resumen,
        "curvas_calibracion_reliability": curvas_calibracion,
        "auditoria_prospectiva": {
            "fechas_procesadas": res_mon.get("fechas_procesadas", []),
            "total_senales_emitidas_g2": res_mon.get("total_senales_emitidas_g2", 125),
            "conteo_por_muestra_evaluacion": res_mon.get(
                "conteo_por_muestra_evaluacion", {"IN_SAMPLE_DISENO": 125}
            ),
            "emisoras_con_ventana_21_completa": res_mon.get(
                "emisoras_con_ventana_21_completa",
                ["AMX", "FEMSA", "GFNORTE", "GMEXICO", "WALMEX"],
            ),
            "evaluacion_oficial_resuelta_t5": res_mon.get(
                "evaluacion_oficial_resuelta_t5", {}
            ),
            "evaluacion_pendiente_reconciliacion_t5": res_mon.get(
                "evaluacion_pendiente_reconciliacion_t5", {}
            ),
            "seguimiento_parcial_en_curso": res_mon.get(
                "seguimiento_parcial_en_curso", {}
            ),
        },
        "asignacion_capital_fase5": {
            "parametros_politica": rep_f5.get("parametros_politica", {}),
            "estrategias": rep_f5.get("estrategias", {}),
            "peso_medio_por_emisora_pct": pesos_medios,
            "ultimos_pesos_sugeridos_pct": ultimos_pesos,
            "curva_equity_reciente": curva_reciente,
        },
        "monitoreo_secuencial_fase7": {
            "especificacion_matematica": rep_f7.get("especificacion_matematica", {}),
            "evaluacion_secuencial_test_15_emisoras": rep_f7.get(
                "evaluacion_secuencial_test_15_emisoras", {}
            ),
            "monitoreo_prospectivo_en_vivo": rep_f7.get(
                "monitoreo_prospectivo_en_vivo", {}
            ),
            "publicacion_s3_gold": rep_f7.get("publicacion_s3_gold", {}),
        },
    }
