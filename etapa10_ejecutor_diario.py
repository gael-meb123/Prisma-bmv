import argparse
import hashlib
import json
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd

from experimento_ajuste_dividendos import (
    FEATURES_8,
    build_adjusted_features_and_indicator,
    fit_logistic_regression_balanced,
    load_data,
    predict_proba_logistic,
    standard_scale,
)
from experimento_integral_ia_boletines_noticias import (
    attach_regulatory_features,
    fit_predict_random_forest,
    load_official_quarterly_regulatory_data,
    run_live_regulatory_and_news_scraper,
)
from sistema_nucleo_walmex_prospectivo import EMISORAS_15, fetch_and_verify_bmv_bulletin
from metodologia_ppp import (
    VERSION_FEATURES, VERSION_METODOLOGIA, FERIADOS_BMV_2026,
    is_bmv_business_day, add_bmv_sessions, calendario_objetivo, sesiones_entre,
    calcular_features_ppp, validar_ventana_fechas, mascara_etiquetas_conocidas,
    agregar_trazabilidad, localizar_insumo,
)

DOWNLOADS = Path.home() / "Downloads"
OUT_DIR = Path(__file__).resolve().parent
Z9G = localizar_insumo("etapa9G_WALMEX_PPP_20261028T164002342440Z.zip")

def consenso_label(c1: int, c2: int, c3: int) -> str:
    if c1 == c2 == c3 == 1:
        return "CONSENSO_ALTO_SUBIDA"
    if c1 == c2 == c3 == 0:
        return "CONSENSO_ALTO_NO_SUBIDA"
    nom = lambda c: "SUBIDA" if c else "NO_SUBIDA"
    return f"DIVERGENCIA_ALERTA (V1={nom(c1)}, V2R={nom(c2)}, V3={nom(c3)})"


def aplicar_correcciones_registro(df: pd.DataFrame) -> pd.DataFrame:
    """Idempotente. Anula el V2 original (usaba fechas de reportes sin fuente), agrega columnas de validez y
    recalcula el consenso con los modelos validos. Conserva en estado_consenso_original lo que se escribio antes."""
    df = df.copy()
    if "estado_consenso" not in df:
        df["estado_consenso"] = "NO_DOCUMENTADO_EN_REGISTRO_ORIGINAL"
    if "estado_validez" not in df.columns:
        df["estado_validez"] = np.nan
    if "timestamp_emision_utc" not in df.columns:
        df["timestamp_emision_utc"] = np.nan
    if "calendario_objetivo" not in df.columns:
        df["calendario_objetivo"] = np.nan
    if "estado_consenso_original" not in df.columns:
        df["estado_consenso_original"] = np.nan
    for col in ["estado_validez", "timestamp_emision_utc", "calendario_objetivo", "estado_consenso_original"]:
        df[col] = df[col].astype(object)
    df["estado_validez"] = df["estado_validez"].fillna("VALIDA")
    df["timestamp_emision_utc"] = df["timestamp_emision_utc"].fillna("NO_REGISTRADO_ANTES_2026-10-29")
    df["calendario_objetivo"] = df["calendario_objetivo"].fillna("OFICIAL_2026")
    df["estado_consenso_original"] = df["estado_consenso_original"].fillna(df["estado_consenso"])

    old_v2 = df["id_senal"].astype(str).str.endswith("_V2_RETADOR_HIBRIDO_BOLETIN")
    df.loc[old_v2, "estado_validez"] = "ANULADA_FECHAS_REPORTE_NO_DOCUMENTADAS"

    ids = df["id_senal"].astype(str)
    for f in df["fecha_senal"].unique():
        m = df["fecha_senal"] == f
        def pred(sufijo):
            sel = df[m & ids.str.contains(sufijo) & (df["estado_validez"] == "VALIDA")]
            return int(sel["prediccion_clase"].iloc[0]) if len(sel) else None
        c1, c2, c3 = pred("_V1_CONTROL"), pred("_V2R_"), pred("_V3_")
        if None not in (c1, c2, c3):
            df.loc[m & (df["estado_validez"] == "VALIDA"), "estado_consenso"] = consenso_label(c1, c2, c3)
    return agregar_trazabilidad(df)


def init_or_update_master_ppp_series(bulletin_info: dict, series_csv_path: Path) -> pd.DataFrame:
    """
    Inicializa (desde las ultimas 30 sesiones verificadas de 9G) o actualiza de manera idempotente
    la serie prospectiva de PPP estricto de WALMEX *.
    """
    if series_csv_path.exists():
        df_series = pd.read_csv(series_csv_path)
    else:
        with zipfile.ZipFile(Z9G) as zf:
            ppp_9g = pd.read_csv(zf.open("datos/PPP_final_controles.csv"))
        tail_df = ppp_9g.sort_values("posicion_rejilla_heredada").tail(35).copy()
        df_series = pd.DataFrame(
            {
                "fecha": tail_df["fecha"].astype(str),
                "posicion_sesion": tail_df["posicion_rejilla_heredada"].astype(int),
                "emisora": "WALMEX",
                "serie": "*",
                "ppp_bmv_mxn": tail_df["precio_para_calculo"].astype(float),
                "estado": tail_df["estado"].astype(str),
                "url_fuente": tail_df["url_fuente"].astype(str),
                "sha256_html": tail_df["sha256_html"].astype(str),
                "precio_apto_calculo": tail_df["precio_apto_calculo"].astype(bool),
            }
        )

    fecha_nueva = bulletin_info["fecha_boletin"]
    if not is_bmv_business_day(date.fromisoformat(fecha_nueva)):
        raise ValueError(f"El boletin solicitado no corresponde a una sesion BMV: {fecha_nueva}")
    if df_series.fecha.duplicated().any():
        raise ValueError("La serie prospectiva contiene fechas duplicadas")
    w_quote = bulletin_info["cotizaciones"].get("WALMEX")
    ppp_val = float(w_quote["ppp"]) if w_quote is not None else np.nan
    if w_quote is not None and not (np.isfinite(ppp_val) and ppp_val > 0):
        raise ValueError(f"PPP no finito o no positivo ({ppp_val}) en {fecha_nueva}")
    old = df_series[df_series.fecha.eq(fecha_nueva)]
    if not old.empty and old.ppp_bmv_mxn.notna().any():
        if w_quote is None or not np.isclose(float(old.ppp_bmv_mxn.iloc[0]), ppp_val, rtol=0, atol=1e-9):
            raise ValueError(f"Conflicto con PPP previamente documentado en {fecha_nueva}")
    else:
        df_series = df_series[~df_series.fecha.eq(fecha_nueva)]
        df_series = pd.concat([df_series, pd.DataFrame([{
            "fecha": fecha_nueva, "emisora": "WALMEX", "serie": "*",
            "ppp_bmv_mxn": ppp_val,
            "estado": "PPP_PUBLICADO_VERIFICADO" if w_quote is not None else "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA",
            "url_fuente": bulletin_info["url_fuente"], "sha256_html": bulletin_info["sha256_html"],
            "precio_apto_calculo": w_quote is not None,
            "timestamp_captura_utc": bulletin_info.get("timestamp_verificacion_utc", datetime.now(timezone.utc).isoformat()),
        }])], ignore_index=True)
    df_series = df_series.sort_values("fecha")
    anchor = df_series[df_series.posicion_sesion.notna()].iloc[0]
    fechas = sesiones_entre(str(df_series.fecha.min()), str(df_series.fecha.max()))
    if not set(df_series.fecha).issubset(fechas):
        raise ValueError("La serie contiene fechas ajenas al calendario BMV")
    anchor_offset = fechas.index(str(anchor.fecha))
    df_series = df_series.set_index("fecha").reindex(fechas).rename_axis("fecha").reset_index()
    df_series["posicion_sesion"] = int(anchor.posicion_sesion) - anchor_offset + np.arange(len(fechas))
    df_series["emisora"] = "WALMEX"
    df_series["serie"] = "*"
    df_series["estado"] = df_series["estado"].fillna("SESION_SIN_CAPTURA_DOCUMENTADA")
    df_series["precio_apto_calculo"] = df_series["precio_apto_calculo"].eq(True)
    df_series.to_csv(series_csv_path, index=False, encoding="utf-8-sig")
    return df_series


def update_live_multicompany_ppp(bulletin_info: dict, multi_csv_path: Path) -> pd.DataFrame:
    rows = []
    for tk, info in bulletin_info["cotizaciones"].items():
        rows.append(
            {
                "fecha": bulletin_info["fecha_boletin"],
                "emisora": info["emisora"],
                "serie": info["serie"],
                "anillo_madurez": info.get("anillo_madurez", ""),
                "sector_economico": info.get("sector_economico", ""),
                "estado_captura": "PPP_PUBLICADO_VERIFICADO",
                "ppp_bmv_mxn": info["ppp"],
                "ultimo_bmv_mxn": info["ultimo"],
                "anterior_bmv_mxn": info["anterior"],
                "variacion_ppp_vs_anterior_pct": info.get("variacion_ppp_vs_anterior_pct", np.nan),
                "evidencia_exacta": info["evidencia_exacta"],
                "url_fuente": bulletin_info["url_fuente"],
                "sha256_boletin": bulletin_info["sha256_html"],
            }
        )
    # Emisoras de la lista que el boletin RSS de ese dia no publico: se registran como hueco, sin imputar nada
    for miss in bulletin_info.get("no_publicadas_en_boletin", []):
        rows.append(
            {
                "fecha": bulletin_info["fecha_boletin"],
                "emisora": miss["emisora"],
                "serie": miss["serie"],
                "anillo_madurez": miss["anillo_madurez"],
                "sector_economico": miss["sector_economico"],
                "estado_captura": "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA",
                "ppp_bmv_mxn": np.nan,
                "ultimo_bmv_mxn": np.nan,
                "anterior_bmv_mxn": np.nan,
                "variacion_ppp_vs_anterior_pct": np.nan,
                "evidencia_exacta": "Emisora ausente del boletin RSS de la fecha; hueco conservado, no se imputa valor",
                "url_fuente": bulletin_info["url_fuente"],
                "sha256_boletin": bulletin_info["sha256_html"],
            }
        )
    df_new = pd.DataFrame(rows)
    if multi_csv_path.exists():
        df_old = pd.read_csv(multi_csv_path)
        if "estado_captura" not in df_old.columns:
            df_old["estado_captura"] = "PPP_PUBLICADO_VERIFICADO"
        combined = pd.concat([df_old, df_new], ignore_index=True)
        combined = combined.drop_duplicates(subset=["fecha", "emisora"], keep="last")
    else:
        combined = df_new
    lista = {t for t, _, _, _ in EMISORAS_15}
    combined["en_lista_oficial"] = combined["emisora"].isin(lista)
    combined = combined.sort_values(["fecha", "en_lista_oficial", "emisora"], ascending=[True, False, True])
    combined.to_csv(multi_csv_path, index=False, encoding="utf-8-sig")
    return combined


def generate_daily_signals_for_date(
    fecha_senal: str,
    df_series: pd.DataFrame,
    merged_9d: pd.DataFrame,
    reg_df: pd.DataFrame,
    signals_csv_path: Path,
    div_map: dict | None = None,
) -> pd.DataFrame:
    """
    Si la fecha_senal no existe aun en signals_csv_path, verifica las 21 sesiones hasta fecha_senal,
    calcula las 3 senales (V1 Control, V2 Hibrido Boletin, V3 Random Forest) y determina el estado de consenso.
    """
    df_s = df_series[df_series["fecha"] <= fecha_senal].sort_values("fecha").reset_index(drop=True)
    if len(df_s) < 21:
        raise RuntimeError(f"Historia insuficiente ({len(df_s)} < 21) para emitir senal en {fecha_senal}")

    win_df = df_s.tail(21)
    validar_ventana_fechas(win_df["fecha"], fecha_senal)
    if not np.all(win_df["precio_apto_calculo"].eq(True)):
        raise RuntimeError(f"Hueco o precio no apto dentro de las 21 sesiones previas a {fecha_senal}")

    win_21 = win_df["ppp_bmv_mxn"].to_numpy(dtype=float)
    row_today = win_df.iloc[-1]
    ppp_today = float(row_today["ppp_bmv_mxn"])
    url_today = str(row_today["url_fuente"])
    sha_today = str(row_today["sha256_html"])

    feats_today = calcular_features_ppp(win_21)

    with zipfile.ZipFile(Z9G) as zf:
        params_9g = json.loads(zf.read("resultados/parametros.json").decode("utf-8"))["logistica_balanceada"]
    if params_9g["ultimo_precio_etiquetas_train"] > fecha_senal:
        raise ValueError("El control congelado contiene etiquetas posteriores al corte solicitado")

    # 1. V1 Control (LogReg Base congelado)
    mean_v1 = np.array(params_9g["media"], dtype=float)
    scale_v1 = np.array(params_9g["escala"], dtype=float)
    coef_v1 = np.array(params_9g["coeficientes"], dtype=float)
    inter_v1 = float(params_9g["intercepto"])
    z_v1 = float(((feats_today - mean_v1) / scale_v1) @ coef_v1 + inter_v1)
    prob_v1 = float(1.0 / (1.0 + np.exp(-z_v1)))

    # 2. Entrenamiento historico ajustado para V2 y V3
    tr_adj = merged_9d[
        (merged_9d["apto_features_ajustadas"] == True)
        & (merged_9d["apto_label_h5"] == True)
        & (merged_9d["soporte_dentro_del_bloque"] == True)
        & mascara_etiquetas_conocidas(merged_9d, fecha_senal, objetivo="fecha_fin_label_h5")
    ].copy()
    if tr_adj.empty:
        raise ValueError("No hay etiquetas historicas conocidas al corte de la senal")
    # Las entradas ajustadas deben usar exactamente el mismo ajuste local que Train.
    div_map = div_map or {}
    divs = np.array([div_map.get(str(f), 0.0) for f in win_df.fecha], dtype=float)
    adjusted = win_21.copy()
    for j in range(1, 21):
        if divs[j] > 0:
            adjusted[:j] -= divs[j]
    feats_today_adj = calcular_features_ppp(adjusted)
    feat_cols_adj = [f"{c}_adj" for c in FEATURES_8]
    X_tr_raw = tr_adj[feat_cols_adj].to_numpy(dtype=float)
    y_tr = tr_adj["y_h5"].to_numpy(dtype=int)
    X_tr_s, x_today_s, _, _ = standard_scale(X_tr_raw, feats_today_adj.reshape(1, -1))

    # V2R: logistica balanceada con ajuste retroactivo de dividendos. No usa fechas ni contenido de reportes
    # (las fechas historicas de reportes no estan documentadas) ni anticipa ex-dividendos no documentados.
    coef_v2, inter_v2 = fit_logistic_regression_balanced(X_tr_s, y_tr, C=1.0)
    prob_v2 = float(predict_proba_logistic(x_today_s, coef_v2, inter_v2)[0])

    # 3. V3 Random Forest (max_depth=3, min_samples_leaf=25)
    prob_v3 = float(
        fit_predict_random_forest(
            X_tr_s, y_tr, x_today_s, n_estimators=80, max_depth=3, min_samples_leaf=25, seed=42
        )[0]
    )

    c1, c2, c3 = int(prob_v1 >= 0.5), int(prob_v2 >= 0.5), int(prob_v3 >= 0.5)
    consenso = consenso_label(c1, c2, c3)

    fecha_obj = add_bmv_sessions(fecha_senal, 5)
    cal_obj = calendario_objetivo(fecha_senal, fecha_obj)
    ts_emision = datetime.now(timezone.utc).isoformat()
    compact_d = fecha_senal.replace("-", "")

    new_signals = [
        {
            "id_senal": f"WALMEX_{compact_d}_V1_CONTROL_LOGREG",
            "fecha_senal": fecha_senal,
            "fecha_objetivo_h5": fecha_obj,
            "emisora": "WALMEX",
            "serie": "*",
            "ppp_base_mxn": ppp_today,
            "cambio_diario_pct": round(feats_today[0] * 100, 2),
            "rol_modelo": "V1_TITULAR_CONTROL (Intacto Etapa 9I)",
            "algoritmo": "StandardScaler + LogisticRegression(C=1.0, balanced)",
            "n_entrenamiento": int(params_9g["n_train"]),
            "prob_subida_h5": round(prob_v1, 6),
            "prob_subida_pct": round(prob_v1 * 100, 2),
            "prediccion_clase": c1,
            "prediccion_etiqueta": "SUBIDA" if c1 == 1 else "NO_SUBIDA",
            "estado_consenso": consenso,
            "timestamp_emision_utc": ts_emision,
            "estado_validez": "VALIDA",
            "calendario_objetivo": cal_obj,
            "url_boletin_bmv": url_today,
            "sha256_boletin_bmv": sha_today,
            "estado_resolucion": "PENDIENTE",
            "fecha_resolucion_real": "",
            "ppp_t5_mxn": np.nan,
            "retorno_real_h5_pct": np.nan,
            "y_real_h5": np.nan,
            "acierto": np.nan,
            "log_loss_individual": np.nan,
            "brier_individual": np.nan,
        },
        {
            "id_senal": f"WALMEX_{compact_d}_V2R_RETADOR_LINEAL_AJUSTE_DIVIDENDOS",
            "fecha_senal": fecha_senal,
            "fecha_objetivo_h5": fecha_obj,
            "emisora": "WALMEX",
            "serie": "*",
            "ppp_base_mxn": ppp_today,
            "cambio_diario_pct": round(feats_today[0] * 100, 2),
            "rol_modelo": "V2R_RETADOR_LINEAL (Ajuste retroactivo de dividendos)",
            "algoritmo": "StandardScaler + LogisticRegression(C=1.0, balanced) con ajuste retroactivo de dividendos, sin variables de reportes",
            "n_entrenamiento": int(len(tr_adj)),
            "prob_subida_h5": round(prob_v2, 6),
            "prob_subida_pct": round(prob_v2 * 100, 2),
            "prediccion_clase": c2,
            "prediccion_etiqueta": "SUBIDA" if c2 == 1 else "NO_SUBIDA",
            "estado_consenso": consenso,
            "timestamp_emision_utc": ts_emision,
            "estado_validez": "VALIDA",
            "calendario_objetivo": cal_obj,
            "url_boletin_bmv": url_today,
            "sha256_boletin_bmv": sha_today,
            "estado_resolucion": "PENDIENTE",
            "fecha_resolucion_real": "",
            "ppp_t5_mxn": np.nan,
            "retorno_real_h5_pct": np.nan,
            "y_real_h5": np.nan,
            "acierto": np.nan,
            "log_loss_individual": np.nan,
            "brier_individual": np.nan,
        },
        {
            "id_senal": f"WALMEX_{compact_d}_V3_RETADOR_SELECCIONADO_RF",
            "fecha_senal": fecha_senal,
            "fecha_objetivo_h5": fecha_obj,
            "emisora": "WALMEX",
            "serie": "*",
            "ppp_base_mxn": ppp_today,
            "cambio_diario_pct": round(feats_today[0] * 100, 2),
            "rol_modelo": "V3_RETADOR_GANADOR_SELECTOR (Random Forest max_depth=3 + Dividendos)",
            "algoritmo": "RandomForestClassifier(n_estimators=80, max_depth=3, min_samples_leaf=25, balanced)",
            "n_entrenamiento": int(len(tr_adj)),
            "prob_subida_h5": round(prob_v3, 6),
            "prob_subida_pct": round(prob_v3 * 100, 2),
            "prediccion_clase": c3,
            "prediccion_etiqueta": "SUBIDA" if c3 == 1 else "NO_SUBIDA",
            "estado_consenso": consenso,
            "timestamp_emision_utc": ts_emision,
            "estado_validez": "VALIDA",
            "calendario_objetivo": cal_obj,
            "url_boletin_bmv": url_today,
            "sha256_boletin_bmv": sha_today,
            "estado_resolucion": "PENDIENTE",
            "fecha_resolucion_real": "",
            "ppp_t5_mxn": np.nan,
            "retorno_real_h5_pct": np.nan,
            "y_real_h5": np.nan,
            "acierto": np.nan,
            "log_loss_individual": np.nan,
            "brier_individual": np.nan,
        },
    ]

    df_new_sig = pd.DataFrame(new_signals)
    df_new_sig["version_features"] = VERSION_FEATURES
    df_new_sig["version_metodologia"] = VERSION_METODOLOGIA
    df_new_sig["fecha_corte_entrenamiento"] = [
        params_9g["ultimo_precio_etiquetas_train"],
        str(tr_adj["fecha_fin_label_h5"].max()), str(tr_adj["fecha_fin_label_h5"].max()),
    ]
    df_new_sig["timestamp_captura_datos_utc"] = row_today.get("timestamp_captura_utc", "NO_DOCUMENTADO")
    if signals_csv_path.exists():
        df_existing = pd.read_csv(signals_csv_path)
        # Asegurar columnas de resolucion si viene del formato previo
        for col in df_new_sig.columns:
            if col not in df_existing.columns:
                df_existing[col] = df_new_sig[col].iloc[0] if col == "estado_consenso" else np.nan
        existing_ids = set(df_existing["id_senal"].astype(str))
        to_add = df_new_sig[~df_new_sig["id_senal"].isin(existing_ids)]
        if len(to_add) > 0:
            df_all = pd.concat([df_existing, to_add], ignore_index=True)
        else:
            df_all = df_existing
    else:
        df_all = df_new_sig

    df_all = agregar_trazabilidad(df_all)
    df_all.to_csv(signals_csv_path, index=False, encoding="utf-8-sig")
    return df_all


def resolver_senales_fecha_exacta(df_sig, df_series):
    """Resuelve por fecha bursatil fija; los huecos intermedios no desplazan t+5."""
    df_sig = agregar_trazabilidad(df_sig)
    df_sig["estado_validez"] = df_sig.get("estado_validez", pd.Series("VALIDA", index=df_sig.index)).fillna("VALIDA")
    for col in ["estado_resolucion", "fecha_resolucion_real"]:
        if col not in df_sig:
            df_sig[col] = ""
        df_sig[col] = df_sig[col].fillna("").astype(object)
    metricas = ["ppp_t5_mxn", "retorno_real_h5_pct", "y_real_h5", "acierto", "log_loss_individual", "brier_individual"]
    for col in metricas:
        df_sig[col] = np.nan  # Descarta cualquier resolucion antigua desplazada.
    df_sig["fecha_resolucion_real"] = ""
    if df_series.fecha.duplicated().any():
        raise ValueError("Serie con fechas duplicadas; no se puede resolver un PPP univoco")
    latest = str(df_series.fecha.max()) if not df_series.empty else ""
    apto = df_series.precio_apto_calculo.eq(True) & np.isfinite(df_series.ppp_bmv_mxn) & df_series.ppp_bmv_mxn.gt(0)
    precios = df_series.loc[apto].set_index("fecha")["ppp_bmv_mxn"]
    for idx, row in df_sig.iterrows():
        if row.estado_validez != "VALIDA":
            df_sig.loc[idx, "estado_resolucion"] = "ANULADA_NO_EVALUABLE"
            continue
        try:
            expected = add_bmv_sessions(str(row.fecha_senal), 5)
        except ValueError:
            df_sig.loc[idx, "estado_resolucion"] = "CALENDARIO_NO_VERIFICADO"
            continue
        if str(row.fecha_objetivo_h5) != expected:
            df_sig.loc[idx, "estado_resolucion"] = "ERROR_FECHA_OBJETIVO"
            continue
        if str(row.fecha_senal) not in precios.index or not np.isclose(float(precios.loc[str(row.fecha_senal)]), float(row.ppp_base_mxn), rtol=0, atol=1e-8):
            df_sig.loc[idx, "estado_resolucion"] = "BASE_NO_VERIFICABLE"
            continue
        if expected not in precios.index:
            estado = "PENDIENTE_FECHA_OBJETIVO" if latest < expected else "NO_RESOLUBLE_PPP_OBJETIVO_AUSENTE"
            df_sig.loc[idx, "estado_resolucion"] = estado
            continue
        ppp_t5, ppp_t = float(precios.loc[expected]), float(row.ppp_base_mxn)
        p = float(row.prob_subida_h5)
        if not np.isfinite(p) or not 0 <= p <= 1 or row.prediccion_clase not in (0, 1):
            raise ValueError(f"Probabilidad o clase invalida: {row.id_senal}")
        y = int(ppp_t5 > ppp_t)
        pc = float(np.clip(p, 1e-15, 1 - 1e-15))
        df_sig.loc[idx, "estado_resolucion"] = "RESUELTA_VERIFICADA"
        df_sig.loc[idx, "fecha_resolucion_real"] = expected
        df_sig.loc[idx, metricas] = [
            ppp_t5, (ppp_t5 / ppp_t - 1) * 100, y, int(row.prediccion_clase == y),
            -(y * np.log(pc) + (1 - y) * np.log(1 - pc)), (p - y) ** 2,
        ]
    return df_sig


def resolve_matured_signals_and_update_scoreboard(
    df_series: pd.DataFrame,
    signals_csv_path: Path,
    scoreboard_csv_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Resuelve usando la fecha objetivo exacta y actualiza el marcador documentado.
    """
    df_sig = pd.read_csv(signals_csv_path)
    df_sig = resolver_senales_fecha_exacta(df_sig, df_series)
    ts = pd.to_datetime(df_sig.timestamp_emision_utc, errors="coerce", utc=True, format="mixed")
    fecha_emision = ts.dt.tz_convert("America/Mexico_City").dt.strftime("%Y-%m-%d")
    df_sig["apta_evaluacion_prospectiva"] = ts.notna() & fecha_emision.ge(df_sig.fecha_corte_datos) & fecha_emision.lt(df_sig.fecha_objetivo_h5)
    df_sig.to_csv(signals_csv_path, index=False, encoding="utf-8-sig")

    # Construir marcador prospectivo por rol_modelo
    score_rows = []
    for (rol, version, features), grp in df_sig[df_sig["estado_validez"] == "VALIDA"].groupby(
        ["rol_modelo", "version_metodologia", "version_features"], sort=False
    ):
        resueltas = grp[(grp["estado_resolucion"] == "RESUELTA_VERIFICADA") & grp.apta_evaluacion_prospectiva]
        n_emitidas = int(len(grp))
        n_resueltas = int(len(resueltas))
        n_pendientes = int(grp.estado_resolucion.eq("PENDIENTE_FECHA_OBJETIVO").sum())

        if n_resueltas > 0:
            aciertos = int(resueltas["acierto"].sum())
            acc_pct = round(float(resueltas["acierto"].mean() * 100.0), 2)
            ll_mean = round(float(resueltas["log_loss_individual"].mean()), 4)
            brier_mean = round(float(resueltas["brier_individual"].mean()), 4)
            fp_count = int(
                np.sum((resueltas["prediccion_clase"] == 1) & (resueltas["y_real_h5"] == 0))
            )
        else:
            aciertos = 0
            acc_pct = np.nan
            ll_mean = np.nan
            brier_mean = np.nan
            fp_count = 0

        score_rows.append(
            {
                "rol_modelo": rol,
                "senales_emitidas": n_emitidas,
                "senales_resueltas": n_resueltas,
                "senales_resueltas_por_precio": int(grp.estado_resolucion.eq("RESUELTA_VERIFICADA").sum()),
                "senales_pendientes": n_pendientes,
                "senales_no_resolubles": int(grp.estado_resolucion.eq("NO_RESOLUBLE_PPP_OBJETIVO_AUSENTE").sum()),
                "senales_sin_trazabilidad_prospectiva": int((~grp.apta_evaluacion_prospectiva).sum()),
                "version_metodologia": version,
                "version_features": features,
                "aciertos_acumulados": aciertos,
                "falsas_subidas_acumuladas": fp_count,
                "exactitud_prospectiva_pct": acc_pct,
                "log_loss_prospectivo": ll_mean,
                "brier_prospectivo": brier_mean,
                "meta_revision_2027_04_30": "Minimo 60 resueltas y >=10 por clase",
            }
        )

    df_score = pd.DataFrame(score_rows)
    df_score.to_csv(scoreboard_csv_path, index=False, encoding="utf-8-sig")
    return df_sig, df_score


def run_self_test_simulation(df_series_real, merged_9d, reg_df):
    """Compatibilidad: valida el calendario sin fabricar cotizaciones ni emitir senales."""
    assert [add_bmv_sessions("2026-10-28", i) for i in range(1, 6)] == [
        "2026-10-29", "2026-10-30", "2026-11-03", "2026-11-04", "2026-11-05",
    ]
    return True


def main():
    parser = argparse.ArgumentParser(description="Etapa 10A: Ejecutor Diario Autonomo Prisma BMV")
    parser.add_argument(
        "--fecha",
        type=str,
        default=pd.Timestamp.now(tz="America/Mexico_City").strftime("%Y%m%d"),
        help="Fecha del boletin BMV en formato YYYYMMDD (por defecto: hoy en Mexico)",
    )
    args = parser.parse_args()

    s9d, el9d, divs9d, periodos9e, pred9e, coefs9e, pred9f, s9g, sel9g, pred9g, divs9g = load_data()
    div_map = dict(zip(divs9d["fecha_ex"].astype(str), divs9d["dividendo_documentado"].astype(float)))
    for _, r in divs9g.iterrows():
        div_map[str(r["fecha_ex"])] = float(r["dividendo_documentado"])

    merged_9d = build_adjusted_features_and_indicator(s9d, el9d, div_map)
    reg_df = pd.DataFrame()  # Los modelos activos no usan variables de reportes.

    # Paso 1: Descargar y verificar boletin oficial de la BMV
    bulletin_info = fetch_and_verify_bmv_bulletin(args.fecha)
    fecha_iso = bulletin_info["fecha_boletin"]

    # Paso 2: Actualizar de manera idempotente la serie maestra prospectiva de PPP y monitoreo multi-emisora
    series_csv = OUT_DIR / "serie_ppp_walmex_prospectiva.csv"
    multi_csv = OUT_DIR / "monitoreo_ppp_multiemisora_en_vivo.csv"
    signals_csv = OUT_DIR / "registro_senales_prospectivas_walmex.csv"
    scoreboard_csv = OUT_DIR / "marcador_modelos_prospectivo.csv"

    df_series = init_or_update_master_ppp_series(bulletin_info, series_csv)
    df_multi_15 = update_live_multicompany_ppp(bulletin_info, multi_csv)

    # Paso 3: Prueba unitaria en memoria del resolutor t+5 y salto del feriado 2026-11-02
    test_ok = add_bmv_sessions("2026-10-28", 5) == "2026-11-05"
    print(f"Autoverificacion del Resolutor t+5 y feriado 2026-11-02 en memoria: {'OK' if test_ok else 'ERROR'}")

    # Paso 4: Emitir las 3 senales del dia (V1 Control, V2 Hibrido, V3 Random Forest) con estado de consenso
    try:
        df_signals = generate_daily_signals_for_date(
            fecha_iso, df_series, merged_9d, reg_df, signals_csv, div_map=div_map
        )
    except (ValueError, RuntimeError) as exc:
        print(f"Senal no emitida para {fecha_iso}: {exc}")
        if not signals_csv.exists():
            return
        df_signals = pd.read_csv(signals_csv)

    df_signals = aplicar_correcciones_registro(df_signals)
    df_signals.to_csv(signals_csv, index=False, encoding="utf-8-sig")

    # Paso 5: Ejecutar el Resolutor Automatico t+5 y actualizar el Marcador Prospectivo
    df_signals, df_score = resolve_matured_signals_and_update_scoreboard(
        df_series, signals_csv, scoreboard_csv
    )

    # Paso 6: Actualizar bitacora de noticias y boletines en tiempo real
    scraping_ev, df_news = run_live_regulatory_and_news_scraper()

    print(f"\n=== ETAPA 10A EJECUTADA PARA FECHA DE CORTE {fecha_iso} ===")
    print(f"Serie prospectiva WALMEX *: {len(df_series)} sesiones verificadas (ultima: {df_series.iloc[-1]['fecha']}, PPP={df_series.iloc[-1]['ppp_bmv_mxn']} MXN)")
    print(f"\n=== INGESTA EN VIVO DE LAS 15 EMISORAS DEL IPC ({fecha_iso}) ===")
    df_today_15 = df_multi_15[(df_multi_15["fecha"] == fecha_iso) & (df_multi_15["en_lista_oficial"])]
    for _, mr in df_today_15.iterrows():
        print(
            f" * {mr['emisora']:8s} ({mr['serie']:3s}) | PPP={mr['ppp_bmv_mxn']:7.2f} MXN "
            f"(Ult={mr['ultimo_bmv_mxn']:7.2f}, Ant={mr['anterior_bmv_mxn']:7.2f}, VarPPP={mr['variacion_ppp_vs_anterior_pct']:+5.2f}%) | "
            f"{mr['anillo_madurez']}"
        )
    print("\n=== REGISTRO DE SENALES PROSPECTIVAS Y CONSENSO ===")
    for _, r in df_signals.iterrows():
        print(
            f" * {r['id_senal']} | Prob={r['prob_subida_pct']}% ({r['prediccion_etiqueta']}) | "
            f"Consenso: {r['estado_consenso']} | Estado: {r['estado_resolucion']}"
        )

    print("\n=== MARCADOR PROSPECTIVO ACUMULADO ===")
    for _, sr in df_score.iterrows():
        print(
            f" * {sr['rol_modelo']}: Emitidas={sr['senales_emitidas']}, "
            f"Resueltas={sr['senales_resueltas']}, Pendientes={sr['senales_pendientes']}"
        )


if __name__ == "__main__":
    main()
