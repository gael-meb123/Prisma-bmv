import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from metodologia_ppp import calcular_features_ppp, localizar_insumo, mascara_etiquetas_conocidas, validar_ventana_fechas

from experimento_ajuste_dividendos import (
    FEATURES_8,
    build_adjusted_features_and_indicator,
    evaluate_predictions,
    fit_logistic_regression_balanced,
    load_data,
    predict_proba_logistic,
    standard_scale,
)
from experimento_integral_ia_boletines_noticias import (
    attach_regulatory_features,
    evaluate_all_models_on_495,
    fit_elasticnet_logistic_balanced,
    fit_predict_gbdt,
    fit_predict_mlp,
    fit_predict_random_forest,
    load_official_quarterly_regulatory_data,
    run_live_regulatory_and_news_scraper,
)

DOWNLOADS = Path.home() / "Downloads"
OUT_DIR = Path(__file__).resolve().parent
Z9G = localizar_insumo("etapa9G_WALMEX_PPP_20261028T164002342440Z.zip")


# Lista oficial de 15 emisoras confirmada por el usuario el 2026-10-29.
EMISORAS_15 = [
    ("GMEXICO", "B", "Anillo 2 (Plata: Seleccion Modelo Sectorial)", "Mineria y materiales"),
    ("GFNORTE", "O", "Anillo 2 (Plata: Seleccion Modelo Sectorial)", "Banca y servicios financieros"),
    ("FEMSA", "UBD", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Consumo y comercio"),
    ("AMX", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Telecomunicaciones"),
    ("WALMEX", r"\*", "Anillo 1 (Oro: Inferencia Prospectiva Estricta)", "Comercio y autoservicio"),
    ("CEMEX", "CPO", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Cemento y construccion"),
    ("PE&OLES", r"\*", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Mineria y metales"),
    ("GAP", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Infraestructura aeroportuaria"),
    ("AC", r"\*", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Bebidas y consumo"),
    ("ASUR", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Infraestructura aeroportuaria"),
    ("BIMBO", "A", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Industria alimentaria"),
    ("GFINBUR", "O", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Servicios financieros"),
    ("VESTA", r"\*", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Inmuebles industriales"),
    ("LIVEPOL", "C-1", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Comercio departamental"),
    ("GRUMA", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Industria alimentaria"),
]
EMISORAS_15_IPC = EMISORAS_15  # alias de compatibilidad

YF_TICKER_MAP = {
    "GMEXICO": "GMEXICOB.MX",
    "GFNORTE": "GFNORTEO.MX",
    "FEMSA": "FEMSAUBD.MX",
    "AMX": "AMXB.MX",
    "WALMEX": "WALMEX.MX",
    "CEMEX": "CEMEXCPO.MX",
    "PE&OLES": "PE%26OLES.MX",
    "GAP": "GAPB.MX",
    "AC": "AC.MX",
    "ASUR": "ASURB.MX",
    "BIMBO": "BIMBOA.MX",
    "GFINBUR": "GFINBURO.MX",
    "VESTA": "VESTA.MX",
    "LIVEPOL": "LIVEPOLC-1.MX",
    "GRUMA": "GRUMAB.MX",
}


def fetch_secondary_contingency_bulletin(date_yyyymmdd: str) -> dict:
    """
    Fuente secundaria de contingencia cuando el boletin primario RSS de la BMV
    aun no ha sido publicado (HTTP 404).
    Extrae cotizaciones de cierre y VWAP de cierre (13:40-14:00 CDMX) para las 15
    emisoras del IPC y las marca con estado 'CONTINGENCIA_FUENTE_SECUNDARIA' para
    que sean reconciliadas y reemplazadas automaticamente en cuanto la BMV publique
    el boletin primario oficial.
    """
    from zoneinfo import ZoneInfo

    fecha_iso = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:]}"
    cache_dir = OUT_DIR / "cache_boletines"
    cache_dir.mkdir(exist_ok=True)
    sec_cache_file = cache_dir / f"contingencia_{date_yyyymmdd}.json"

    if sec_cache_file.exists():
        cached_payload = json.loads(sec_cache_file.read_text(encoding="utf-8"))
        return cached_payload

    tz_mx = ZoneInfo("America/Mexico_City")
    extracted = {}
    no_publicadas = []

    for ticker, serie, anillo, sector in EMISORAS_15:
        serie_clean = serie.replace("\\", "")
        yf_sym = YF_TICKER_MAP.get(ticker)
        if not yf_sym:
            no_publicadas.append(
                {"emisora": ticker, "serie": serie_clean, "anillo_madurez": anillo, "sector_economico": sector}
            )
            continue

        url_1d = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}?interval=1d&range=1mo"
        req_1d = urllib.request.Request(url_1d, headers={"User-Agent": "Mozilla/5.0 PrismaBMV-Contingencia/1.0"})
        try:
            with urllib.request.urlopen(req_1d, timeout=10) as r1:
                data_1d = json.loads(r1.read().decode("utf-8"))["chart"]["result"][0]
            ts_list = data_1d.get("timestamp", [])
            closes = data_1d["indicators"]["quote"][0].get("close", [])
            daily_pairs = []
            for t_val, c_val in zip(ts_list, closes):
                if c_val is not None and np.isfinite(c_val) and c_val > 0:
                    d_str = datetime.fromtimestamp(t_val, tz=tz_mx).strftime("%Y-%m-%d")
                    daily_pairs.append((d_str, round(float(c_val), 2)))

            idx_match = next((i for i, (d_s, _) in enumerate(daily_pairs) if d_s == fecha_iso), None)
            if idx_match is None:
                no_publicadas.append(
                    {"emisora": ticker, "serie": serie_clean, "anillo_madurez": anillo, "sector_economico": sector}
                )
                continue

            ultimo_val = daily_pairs[idx_match][1]
            anterior_val = daily_pairs[idx_match - 1][1] if idx_match > 0 else ultimo_val
            ppp_val = ultimo_val

            # Intentar calcular el VWAP de los ultimos 20 minutos (13:40 a 14:00 CDMX) con barras de 1m
            try:
                url_1m = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}?interval=1m&range=5d"
                req_1m = urllib.request.Request(url_1m, headers={"User-Agent": "Mozilla/5.0 PrismaBMV-Contingencia/1.0"})
                with urllib.request.urlopen(req_1m, timeout=8) as r_m:
                    data_1m = json.loads(r_m.read().decode("utf-8"))["chart"]["result"][0]
                ts_m = data_1m.get("timestamp", [])
                q_m = data_1m["indicators"]["quote"][0]
                num_20m, den_20m = 0.0, 0.0
                for t_i, c_i, h_i, l_i, v_i in zip(
                    ts_m,
                    q_m.get("close", []),
                    q_m.get("high", []),
                    q_m.get("low", []),
                    q_m.get("volume", []),
                ):
                    if c_i is None or v_i is None or v_i <= 0:
                        continue
                    dt_mx = datetime.fromtimestamp(t_i, tz=tz_mx)
                    if dt_mx.strftime("%Y-%m-%d") == fecha_iso:
                        hm = dt_mx.hour * 60 + dt_mx.minute
                        if 13 * 60 + 40 <= hm <= 14 * 60:
                            typ = (h_i + l_i + c_i) / 3.0 if (h_i is not None and l_i is not None) else c_i
                            num_20m += float(typ) * float(v_i)
                            den_20m += float(v_i)
                if den_20m > 0:
                    ppp_val = round(num_20m / den_20m, 2)
            except Exception:
                pass

            var_pct = round((ppp_val / anterior_val - 1.0) * 100.0, 2) if anterior_val > 0 else 0.0
            extracted[ticker] = {
                "emisora": ticker,
                "serie": serie_clean,
                "anillo_madurez": anillo,
                "sector_economico": sector,
                "ultimo": ultimo_val,
                "anterior": anterior_val,
                "ppp": ppp_val,
                "variacion_ppp_vs_anterior_pct": var_pct,
                "evidencia_exacta": f"{ticker} / {serie_clean} / CONTINGENCIA_SECUNDARIA / {ppp_val:.2f}",
            }
        except Exception:
            no_publicadas.append(
                {"emisora": ticker, "serie": serie_clean, "anillo_madurez": anillo, "sector_economico": sector}
            )

    if not extracted:
        raise RuntimeError(f"Sin datos tanto en fuente primaria BMV como en secundaria para {fecha_iso}")

    canonical_bytes = json.dumps(extracted, sort_keys=True, ensure_ascii=False).encode("utf-8")
    sha256_sec = hashlib.sha256(canonical_bytes).hexdigest()
    url_contingencia = f"https://query1.finance.yahoo.com/v8/finance/chart/WALMEX.MX?date={fecha_iso}#contingencia_bmv_404"

    result = {
        "fecha_boletin": fecha_iso,
        "origen_fuente": "SECUNDARIA_CONTINGENCIA",
        "estado_captura": "CONTINGENCIA_FUENTE_SECUNDARIA",
        "url_fuente": url_contingencia,
        "sha256_html": sha256_sec,
        "bytes_html": len(canonical_bytes),
        "timestamp_verificacion_utc": datetime.now(timezone.utc).isoformat(),
        "cotizaciones": extracted,
        "no_publicadas_en_boletin": no_publicadas,
    }
    sec_cache_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def fetch_and_verify_bmv_bulletin(date_yyyymmdd="20261028", allow_secondary_fallback: bool = False):
    """
    Descarga el boletin publico oficial de la BMV (Fuente Primaria) y extrae el PPP de las 15 emisoras del IPC,
    clasificandolas en los 3 Anillos de Madurez de Datos del proyecto.
    Si allow_secondary_fallback=True y el boletin primario aun no existe en la BMV (HTTP 404),
    recurre temporalmente a la fuente secundaria marcando el estado como CONTINGENCIA_FUENTE_SECUNDARIA.
    """
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{date_yyyymmdd}.html"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PrismaBMV-Nucleo/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read()
    except Exception as exc:
        if not allow_secondary_fallback:
            raise
        print(
            f"[CONTINGENCIA] Boletin primario BMV no disponible para {date_yyyymmdd} ({exc}). "
            f"Consultando fuente secundaria..."
        )
        return fetch_secondary_contingency_bulletin(date_yyyymmdd)

    sha256_html = hashlib.sha256(raw).hexdigest()
    # Mismo parser estricto que la reconstruccion validada contra 9C/9G.
    from reconstruccion_ppp_15_emisoras import parse_bulletin_quotes
    quotes = parse_bulletin_quotes(raw)

    extracted = {}
    for ticker, serie, anillo, sector in EMISORAS_15:
        serie_clean = serie.replace("\\", "")
        quote = quotes.get((ticker, serie_clean))
        if quote is None:
            continue
        extracted[ticker] = {
            "emisora": ticker, "serie": serie_clean, "anillo_madurez": anillo,
            "sector_economico": sector, **quote,
            "evidencia_exacta": f"{ticker} / {serie_clean} / PPP / {quote['ppp']:.2f}",
        }

    no_publicadas = [
        {"emisora": t, "serie": sr.replace("\\", ""), "anillo_madurez": an, "sector_economico": sec}
        for t, sr, an, sec in EMISORAS_15
        if t not in extracted
    ]

    return {
        "fecha_boletin": f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:]}",
        "origen_fuente": "PRIMARIA_BOLETIN_OFICIAL_BMV",
        "estado_captura": "PPP_PUBLICADO_VERIFICADO",
        "url_fuente": url,
        "sha256_html": sha256_html,
        "bytes_html": len(raw),
        "timestamp_verificacion_utc": datetime.now(timezone.utc).isoformat(),
        "cotizaciones": extracted,
        "no_publicadas_en_boletin": no_publicadas,
    }


def compute_prospective_signal_2026_10_28(merged_9d, merged_9g, reg_df, bulletin_info):
    """
    Calcula las 8 variables exactas para el corte del 28 de octubre de 2026 (PPP = 48.40 MXN)
    y emite en paralelo:
      1. Modelo Control (v1_logreg_base): parametros congelados de 9G (53.59%).
      2. Modelo Retador Lineal Hibrido (v2_hibrido_div_boletin): entrenado en el historico previo con
         ajuste retroactivo de dividendos + sorpresa de boletin regulatorio (3T26 publicado el 27/10/2026).
      3. Modelo Retador No Lineal Seleccionado (v3_rf_d3_div): Random Forest (max_depth=3, min_samples_leaf=25)
         seleccionado automaticamente en 9E y entrenado con el historico previo a la senal.
    """
    import zipfile

    with zipfile.ZipFile(Z9G) as zf:
        params_9g = json.loads(zf.read("resultados/parametros.json").decode("utf-8"))["logistica_balanceada"]
        ppp_9g = pd.read_csv(zf.open("datos/PPP_final_controles.csv"))

    tail = ppp_9g.sort_values("posicion_rejilla_heredada").tail(20)
    validar_ventana_fechas(tail["fecha"].astype(str).tolist() + ["2026-10-28"], "2026-10-28")
    ppp_tail_20 = tail["precio_para_calculo"].to_numpy(dtype=float)
    ppp_today = float(bulletin_info["cotizaciones"]["WALMEX"]["ppp"])
    win_21 = np.append(ppp_tail_20, ppp_today)

    assert len(win_21) == 21 and np.all(win_21 > 0), "Ventana de 21 observaciones invalida"

    feats_today = calcular_features_ppp(win_21)

    # 1. Modelo Control Oficial (v1_logreg_base) usando parametros oficiales guardados en 9G
    mean_v1 = np.array(params_9g["media"], dtype=float)
    scale_v1 = np.array(params_9g["escala"], dtype=float)
    coef_v1 = np.array(params_9g["coeficientes"], dtype=float)
    inter_v1 = float(params_9g["intercepto"])

    x_v1_norm = (feats_today - mean_v1) / scale_v1
    z_v1 = float(x_v1_norm @ coef_v1 + inter_v1)
    prob_v1 = float(1.0 / (1.0 + np.exp(-z_v1)))

    # 2. Preparar conjunto de entrenamiento ajustado por dividendos (1,785 sesiones verificadas en 9D)
    m_9d_reg = attach_regulatory_features(merged_9d, reg_df)
    tr_adj = m_9d_reg[
        (m_9d_reg["apto_features_ajustadas"] == True)
        & (m_9d_reg["apto_label_h5"] == True)
        & (m_9d_reg["soporte_dentro_del_bloque"] == True)
        & mascara_etiquetas_conocidas(m_9d_reg, "2026-10-28", objetivo="fecha_fin_label_h5")
    ].copy()

    feat_cols_adj = [f"{c}_adj" for c in FEATURES_8]
    X_tr_raw = tr_adj[feat_cols_adj].to_numpy(dtype=float)
    y_tr = tr_adj["y_h5"].to_numpy(dtype=int)
    X_tr_s, x_today_s, _, _ = standard_scale(X_tr_raw, feats_today.reshape(1, -1))

    # Modelo Retador Lineal Hibrido (v2_hibrido_div_boletin):
    # Hoy 2026-10-28 es sesion t+1 posterior al reporte del 3T26 (publicado el 27/10/2026 con caida de 6% en utilidad)
    coef_v2, inter_v2 = fit_logistic_regression_balanced(X_tr_s, y_tr, C=1.0)
    prob_v2_base = float(predict_proba_logistic(x_today_s, coef_v2, inter_v2)[0])
    # Ajuste por sorpresa negativa de boletin trimestral en t+1 (post_rep_5d == 1 y sorpresa < 0)
    tr_neg = tr_adj[(tr_adj["post_rep_5d"] == 1) & (tr_adj["sorpresa_regulatoria_5d"] < 0)]
    p_neg = float(np.mean(tr_neg["y_h5"])) if len(tr_neg) > 5 else 0.5
    shift_neg = 0.5 * np.log(np.clip(p_neg, 0.1, 0.9) / (1.0 - np.clip(p_neg, 0.1, 0.9)))
    z_v2 = np.log(prob_v2_base / (1.0 - prob_v2_base)) + shift_neg
    prob_v2 = float(1.0 / (1.0 + np.exp(-z_v2)))

    # 3. Modelo Retador No Lineal Seleccionado (v3_rf_d3_div): Random Forest (80 arboles, max_depth=3)
    prob_v3 = float(
        fit_predict_random_forest(
            X_tr_s, y_tr, x_today_s, n_estimators=80, max_depth=3, min_samples_leaf=25, seed=42
        )[0]
    )

    signals = [
        {
            "id_senal": "WALMEX_20261028_V1_CONTROL_LOGREG",
            "fecha_senal": "2026-10-28",
            "fecha_objetivo_h5": "2026-11-05",
            "emisora": "WALMEX",
            "serie": "*",
            "ppp_base_mxn": ppp_today,
            "cambio_diario_pct": round((feats_today[0]) * 100, 2),
            "rol_modelo": "TITULAR_CONTROL (Intacto Etapa 9I)",
            "algoritmo": "StandardScaler + LogisticRegression(C=1.0, balanced)",
            "n_entrenamiento": int(params_9g["n_train"]),
            "prob_subida_h5": round(prob_v1, 6),
            "prob_subida_pct": round(prob_v1 * 100, 2),
            "prediccion_clase": int(prob_v1 >= 0.5),
            "prediccion_etiqueta": "SUBIDA" if prob_v1 >= 0.5 else "NO_SUBIDA",
            "url_boletin_bmv": bulletin_info["url_fuente"],
            "sha256_boletin_bmv": bulletin_info["sha256_html"],
            "respuesta_real_h5": "PENDIENTE_HASTA_2026-11-05",
        },
        {
            "id_senal": "WALMEX_20261028_V2_RETADOR_HIBRIDO_BOLETIN",
            "fecha_senal": "2026-10-28",
            "fecha_objetivo_h5": "2026-11-05",
            "emisora": "WALMEX",
            "serie": "*",
            "ppp_base_mxn": ppp_today,
            "cambio_diario_pct": round((feats_today[0]) * 100, 2),
            "rol_modelo": "RETADOR_SOMBRA_LINEAL (Ajuste Dividendos + Boletin Trimestral t+1)",
            "algoritmo": "LogisticRegression + Ajuste Retroactivo Dividendos + Sorpresa Reporte 3T26",
            "n_entrenamiento": int(len(tr_adj)),
            "prob_subida_h5": round(prob_v2, 6),
            "prob_subida_pct": round(prob_v2 * 100, 2),
            "prediccion_clase": int(prob_v2 >= 0.5),
            "prediccion_etiqueta": "SUBIDA" if prob_v2 >= 0.5 else "NO_SUBIDA",
            "url_boletin_bmv": bulletin_info["url_fuente"],
            "sha256_boletin_bmv": bulletin_info["sha256_html"],
            "respuesta_real_h5": "PENDIENTE_HASTA_2026-11-05",
        },
        {
            "id_senal": "WALMEX_20261028_V3_RETADOR_SELECCIONADO_RF",
            "fecha_senal": "2026-10-28",
            "fecha_objetivo_h5": "2026-11-05",
            "emisora": "WALMEX",
            "serie": "*",
            "ppp_base_mxn": ppp_today,
            "cambio_diario_pct": round((feats_today[0]) * 100, 2),
            "rol_modelo": "RETADOR_SOMBRA_GANADOR_SELECTOR (Random Forest max_depth=3 + Dividendos)",
            "algoritmo": "RandomForestClassifier(n_estimators=80, max_depth=3, min_samples_leaf=25, balanced)",
            "n_entrenamiento": int(len(tr_adj)),
            "prob_subida_h5": round(prob_v3, 6),
            "prob_subida_pct": round(prob_v3 * 100, 2),
            "prediccion_clase": int(prob_v3 >= 0.5),
            "prediccion_etiqueta": "SUBIDA" if prob_v3 >= 0.5 else "NO_SUBIDA",
            "url_boletin_bmv": bulletin_info["url_fuente"],
            "sha256_boletin_bmv": bulletin_info["sha256_html"],
            "respuesta_real_h5": "PENDIENTE_HASTA_2026-11-05",
        },
    ]

    return signals, dict(zip(FEATURES_8, [round(float(x), 6) for x in feats_today]))


def main():
    if (OUT_DIR / "registro_senales_prospectivas_walmex.csv").exists():
        print("Este script quedo reemplazado por etapa10_ejecutor_diario.py y no se ejecuta de nuevo "
              "para no sobrescribir el registro prospectivo existente.")
        return
    s9d, el9d, divs9d, periodos9e, pred9e, coefs9e, pred9f, s9g, sel9g, pred9g, divs9g = load_data()
    div_map = dict(zip(divs9d["fecha_ex"].astype(str), divs9d["dividendo_documentado"].astype(float)))
    for _, r in divs9g.iterrows():
        div_map[str(r["fecha_ex"])] = float(r["dividendo_documentado"])

    merged_9d = build_adjusted_features_and_indicator(s9d, el9d, div_map)
    merged_9g = build_adjusted_features_and_indicator(s9g, sel9g, div_map)
    reg_df = load_official_quarterly_regulatory_data()
    merged_9d = attach_regulatory_features(merged_9d, reg_df)

    # 1. Selector Automatico de Modelo en WALMEX (usando unicamente los 4 periodos internos 9E)
    results_9e = evaluate_all_models_on_495(merged_9d, periodos9e)
    eligible_9e = [
        r for r in results_9e
        if r["periodos_que_superan_base"] >= 3 and r["log_loss"] < 0.6900 and r["FP"] < 131
    ]
    winner_9e = sorted(eligible_9e, key=lambda r: (-r["balanced_accuracy_pct"], r["log_loss"]))[0]

    # 2. Captura en vivo del Boletin Oficial BMV del 28 de octubre de 2026
    bulletin_info = fetch_and_verify_bmv_bulletin("20261028")

    # 3. Calculo de las 3 senales prospectivas del 28 de octubre de 2026 para WALMEX *
    signals, feats_today = compute_prospective_signal_2026_10_28(merged_9d, merged_9g, reg_df, bulletin_info)

    # 4. Scraping en tiempo real de Boletines BMV y Noticias Financieras
    scraping_evidence, df_news = run_live_regulatory_and_news_scraper()

    # Guardar salidas del Nucleo Principal WALMEX
    df_signals = pd.DataFrame(signals)
    df_signals.to_csv(OUT_DIR / "registro_senales_prospectivas_walmex.csv", index=False, encoding="utf-8-sig")

    # Guardar monitoreo vivo de PPP de las 3 emisoras (en archivo separado sin tocar la serie maestra de WALMEX)
    ppp_live_rows = []
    for tk, info in bulletin_info["cotizaciones"].items():
        ppp_live_rows.append(
            {
                "fecha": bulletin_info["fecha_boletin"],
                "emisora": info["emisora"],
                "serie": info["serie"],
                "ppp_bmv_mxn": info["ppp"],
                "ultimo_bmv_mxn": info["ultimo"],
                "anterior_bmv_mxn": info["anterior"],
                "evidencia_exacta": info["evidencia_exacta"],
                "url_fuente": bulletin_info["url_fuente"],
                "sha256_boletin": bulletin_info["sha256_html"],
            }
        )
    pd.DataFrame(ppp_live_rows).to_csv(
        OUT_DIR / "monitoreo_ppp_multiemisora_en_vivo.csv", index=False, encoding="utf-8-sig"
    )

    state_summary = {
        "fecha_corte": "2026-10-28",
        "arquitectura": "Opcion 1: Nucleo Estricto en WALMEX * + Modulo Comparativo Multi-Emisora Separado",
        "selector_automatico_walmex_9E": {
            "criterio_seleccion": "Cumplir >=3/4 periodos sobre base, FP < 131, LogLoss < 0.6900 y mayor Exactitud Balanceada en 9E (sin mirar 9G)",
            "modelo_seleccionado": winner_9e["modelo"],
            "metricas_9E_ganador": winner_9e,
        },
        "boletin_bmv_20261028": bulletin_info,
        "variables_walmex_20261028": feats_today,
        "senales_prospectivas_20261028": signals,
        "resumen_scraping_tiempo_real": {
            "fuentes_auditadas": len(scraping_evidence),
            "items_en_bitacora": int(len(df_news)),
            "noticias_tiempo_real": int(np.sum(df_news["tipo_fuente"] == "NOTICIA_PROSPECTIVA_TIEMPO_REAL")),
        },
    }
    with open(OUT_DIR / "estado_sistema_nucleo_walmex_20261028.json", "w", encoding="utf-8") as f:
        json.dump(state_summary, f, indent=2, ensure_ascii=False)

    print("=== NUCLEO ESTRICTO WALMEX EJECUTADO CON EXITO ===")
    print(f"Selector automatico en 9E eligio: {winner_9e['modelo']}")
    print("\n=== SENALES PROSPECTIVAS REGISTRADAS EL 2026-10-28 (OBJETIVO 2026-11-05) ===")
    for s in signals:
        print(f" - [{s['id_senal']}] ({s['rol_modelo']})")
        print(
            f"   PPP={s['ppp_base_mxn']} MXN | Prob. Subida={s['prob_subida_pct']}% | "
            f"Prediccion={s['prediccion_etiqueta']} | SHA256={s['sha256_boletin_bmv'][:16]}..."
        )


if __name__ == "__main__":
    main()
