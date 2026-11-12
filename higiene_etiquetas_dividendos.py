from __future__ import annotations

import datetime
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from experimento_ajuste_dividendos import load_data
from experimentos_avanzados_entrenamiento import ajustar_logistica_con_zona_neutral
from experimentos_entrenamiento_desarrollo import (
    VARIABLES_REL_TRES,
    ajustar_logistica_pooled_panel,
)
from metodologia_ppp import (
    CORTE_TRAIN,
    FEATURE_NAMES,
    ROOT,
    calcular_features_ppp,
    mascara_etiquetas_conocidas,
    timestamp_utc,
    validar_ventana_fechas,
)
from monitor_prospectivo_segunda_generacion import (
    HIST_PPP_PATH,
    MODELOS_G2,
    PANEL_PATH,
    VARIABLES_DM5_REL_CUATRO,
    hashes_protegidos_g2,
    predecir_g2_v5_adaptativo_regimen_sectorial,
)

EVENTOS_CORP_PATH = ROOT / "eventos_corporativos_15_emisoras.csv"
PANEL_AJUSTADO_PATH = ROOT / "dataset_panel_15_emisoras_features_ajustado_fase1.csv"
REPORTE_FASE1_PATH = ROOT / "reporte_fase1_higiene.json"

YF_TICKER_POR_EMISORA: dict[str, str] = {
    "AC": "AC.MX",
    "AMX": "AMXB.MX",
    "ASUR": "ASURB.MX",
    "BIMBO": "BIMBOA.MX",
    "CEMEX": "CEMEXCPO.MX",
    "FEMSA": "FEMSAUBD.MX",
    "GAP": "GAPB.MX",
    "GFINBUR": "GFINBURO.MX",
    "GFNORTE": "GFNORTEO.MX",
    "GMEXICO": "GMEXICOB.MX",
    "GRUMA": "GRUMAB.MX",
    "LIVEPOL": "LIVEPOLC-1.MX",
    "PE&OLES": "PE&OLES.MX",
    "VESTA": "VESTA.MX",
    "WALMEX": "WALMEX.MX",
}

EMISORAS_FOCO_4 = ("AMX", "GFNORTE", "GMEXICO", "WALMEX")


def construir_eventos_corporativos_15_emisoras(
    hist_path: Path = HIST_PPP_PATH,
    output_path: Path = EVENTOS_CORP_PATH,
    forzar_descarga: bool = False,
) -> pd.DataFrame:
    """
    Construye el catálogo auditado de eventos corporativos (DIVIDENDO | SPLIT)
    para las 15 emisoras del panel con columnas:
      emisora, fecha_ex, tipo, monto_mxn, factor, fuente
    donde para dividendos f = 1 - D / PPP_{ex-1} (usando el último PPP verificado previo a fecha_ex)
    y para splits f = denominador / numerador.
    """
    if output_path.exists() and not forzar_descarga:
        df_cached = pd.read_csv(output_path)
        cols_req = ["emisora", "fecha_ex", "tipo", "monto_mxn", "factor", "fuente"]
        if list(df_cached.columns) == cols_req and len(df_cached) > 0:
            return df_cached

    hist = pd.read_csv(hist_path, dtype=str)
    hist["fecha"] = pd.to_datetime(hist["fecha"], errors="raise").dt.strftime("%Y-%m-%d")
    hist["ppp_bmv_mxn"] = pd.to_numeric(hist["ppp_bmv_mxn"], errors="coerce")

    # Para WALMEX priorizamos los dividendos documentados y contrastados con MexDer / B×+ / Emisora (9D y 9G)
    walmex_doc: dict[str, tuple[float, str]] = {}
    try:
        _, _, divs9d, _, _, _, _, _, _, _, divs9g = load_data()
        for _, r in divs9d.iterrows():
            walmex_doc[str(r["fecha_ex"])] = (
                float(r["dividendo_documentado"]),
                "DOCUMENTADO_MEXDER_EMISORA_9D",
            )
        for _, r in divs9g.iterrows():
            walmex_doc[str(r["fecha_ex"])] = (
                float(r["dividendo_documentado"]),
                "DOCUMENTADO_BXMAS_EMISORA_9G",
            )
    except Exception:
        walmex_doc = {}

    headers = {"User-Agent": "Mozilla/5.0 PrismaBMV-CloudML/1.0"}
    p1 = int(datetime.datetime(2016, 10, 1, tzinfo=datetime.timezone.utc).timestamp())
    p2 = int(datetime.datetime(2026, 11, 7, tzinfo=datetime.timezone.utc).timestamp())
    cdmx_tz = datetime.timezone(datetime.timedelta(hours=-6))

    filas: list[dict[str, Any]] = []
    for em, yf_sym in sorted(YF_TICKER_POR_EMISORA.items()):
        sub_em = (
            hist[(hist["emisora"] == em) & (hist["ppp_bmv_mxn"].notna())]
            .sort_values("fecha")
            .reset_index(drop=True)
        )
        fechas_em = sub_em["fecha"].tolist()
        ppps_em = sub_em["ppp_bmv_mxn"].tolist()

        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{urllib.parse.quote(yf_sym)}?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit"
        )
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        ev = data["chart"]["result"][0].get("events", {})

        if em == "WALMEX" and walmex_doc:
            for f_ex, (monto, fte) in sorted(walmex_doc.items()):
                prev_ppps = [p for f, p in zip(fechas_em, ppps_em) if f < f_ex]
                if not prev_ppps:
                    continue
                ppp_prev = float(prev_ppps[-1])
                if 0.0 < monto < 0.5 * ppp_prev:
                    factor = round(1.0 - monto / ppp_prev, 8)
                    filas.append(
                        {
                            "emisora": em,
                            "fecha_ex": f_ex,
                            "tipo": "DIVIDENDO",
                            "monto_mxn": round(monto, 6),
                            "factor": factor,
                            "fuente": fte,
                        }
                    )
        else:
            divs_por_fecha: dict[str, float] = {}
            for _, d_obj in sorted(ev.get("dividends", {}).items(), key=lambda x: int(x[0])):
                f_ex = datetime.datetime.fromtimestamp(int(d_obj["date"]), tz=cdmx_tz).strftime(
                    "%Y-%m-%d"
                )
                divs_por_fecha[f_ex] = divs_por_fecha.get(f_ex, 0.0) + float(d_obj["amount"])
            for f_ex, monto in sorted(divs_por_fecha.items()):
                prev_ppps = [p for f, p in zip(fechas_em, ppps_em) if f < f_ex]
                if not prev_ppps:
                    continue
                ppp_prev = float(prev_ppps[-1])
                if 0.0 < monto < 0.5 * ppp_prev:
                    factor = round(1.0 - monto / ppp_prev, 8)
                    filas.append(
                        {
                            "emisora": em,
                            "fecha_ex": f_ex,
                            "tipo": "DIVIDENDO",
                            "monto_mxn": round(monto, 6),
                            "factor": factor,
                            "fuente": f"YAHOO_FINANCE_V8_{yf_sym}",
                        }
                    )

        for _, s_obj in sorted(ev.get("splits", {}).items(), key=lambda x: int(x[0])):
            f_ex = datetime.datetime.fromtimestamp(int(s_obj["date"]), tz=cdmx_tz).strftime(
                "%Y-%m-%d"
            )
            num = float(s_obj["numerator"])
            den = float(s_obj["denominator"])
            if num > 0.0 and den > 0.0 and abs(num - den) > 1e-9:
                factor = round(den / num, 8)
                filas.append(
                    {
                        "emisora": em,
                        "fecha_ex": f_ex,
                        "tipo": "SPLIT",
                        "monto_mxn": 0.0,
                        "factor": factor,
                        "fuente": f"YAHOO_FINANCE_V8_{yf_sym}",
                    }
                )

    df_ev = (
        pd.DataFrame(filas)[["emisora", "fecha_ex", "tipo", "monto_mxn", "factor", "fuente"]]
        .sort_values(["emisora", "fecha_ex", "tipo"])
        .reset_index(drop=True)
    )
    df_ev.to_csv(output_path, index=False)
    return df_ev


def construir_panel_con_ppp_ajustado(
    panel_path: Path = PANEL_PATH,
    hist_path: Path = HIST_PPP_PATH,
    eventos_path: Path = EVENTOS_CORP_PATH,
    output_path: Path = PANEL_AJUSTADO_PATH,
) -> pd.DataFrame:
    """
    Genera una versión enriquecida del panel de 15 emisoras conservando intacto ppp_t y
    añadiendo:
      - ppp_ajustado: serie ajustada causalmente por dividendos y splits (f = 1 - D/PPP_{ex-1})
      - ppp_t5_ajustado: ppp_ajustado en fecha_objetivo_h5
      - ventana_con_evento: 1 si ocurre algún evento corporativo en (fecha, fecha_objetivo_h5], 0 en otro caso
      - ventana_21_con_evento: 1 si ocurre algún evento corporativo en (t-20, t], 0 en otro caso
      - target_y_ajustado: I(ppp_t5_ajustado > ppp_ajustado)
      - 8 features recalculadas sobre ppp_ajustado (con sufijo _adj)
    """
    df_ev = construir_eventos_corporativos_15_emisoras(hist_path=hist_path, output_path=eventos_path)
    panel = pd.read_csv(panel_path, dtype=str)
    panel["fecha"] = pd.to_datetime(panel["fecha"], errors="raise").dt.strftime("%Y-%m-%d")
    panel["fecha_objetivo_h5"] = pd.to_datetime(
        panel["fecha_objetivo_h5"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    panel["posicion_sesion"] = pd.to_numeric(panel["posicion_sesion"], errors="raise").astype(int)
    panel["ppp_t"] = pd.to_numeric(panel["ppp_t"], errors="coerce")
    panel["ppp_t5"] = pd.to_numeric(panel["ppp_t5"], errors="coerce")
    panel["target_y"] = pd.to_numeric(panel["target_y"], errors="coerce")
    for col in FEATURE_NAMES:
        panel[col] = pd.to_numeric(panel[col], errors="coerce")

    # Construir ppp_ajustado sobre la rejilla completa de serie_ppp_historica_15_emisoras_bmv.csv
    # para que toda ventana de 21 sesiones [i-20..i] presente en el panel tenga sus 21 precios ajustados
    hist = pd.read_csv(hist_path, dtype=str)
    hist["fecha"] = pd.to_datetime(hist["fecha"], errors="raise").dt.strftime("%Y-%m-%d")
    hist["posicion_sesion"] = pd.to_numeric(hist["posicion_sesion"], errors="raise").astype(int)
    hist["ppp_bmv_mxn"] = pd.to_numeric(hist["ppp_bmv_mxn"], errors="coerce")

    ev_grouped = df_ev.groupby(["emisora", "fecha_ex"])["factor"].prod().to_dict()
    fechas_ev_por_em: dict[str, list[str]] = {
        str(em): sorted(grp["fecha_ex"].unique().tolist())
        for em, grp in df_ev.groupby("emisora")
    }

    lookup_em: dict[tuple[str, str], dict[str, Any]] = {}
    for em, grp_h_raw in hist.groupby("emisora", sort=False):
        grp_h = grp_h_raw.sort_values("posicion_sesion").reset_index(drop=True)
        fechas_h = grp_h["fecha"].tolist()
        pos_h = grp_h["posicion_sesion"].to_numpy(dtype=int)
        ppp_h = grp_h["ppp_bmv_mxn"].to_numpy(dtype=float)
        n_h = len(grp_h)

        evs_em = fechas_ev_por_em.get(str(em), [])
        f_diario = np.ones(n_h, dtype=float)
        evento_en_sesion = np.zeros(n_h, dtype=int)
        for idx_i in range(n_h):
            f_cur = fechas_h[idx_i]
            f_prev = fechas_h[idx_i - 1] if idx_i > 0 else "0000-00-00"
            f_prod = 1.0
            hubo = 0
            for f_ex in evs_em:
                if f_prev < f_ex <= f_cur:
                    f_prod *= float(ev_grouped[(str(em), f_ex)])
                    hubo = 1
            f_diario[idx_i] = f_prod
            evento_en_sesion[idx_i] = hubo

        inv_f = 1.0 / np.maximum(f_diario, 1e-8)
        indice_causal = np.cumprod(inv_f)
        ppp_adj_h = np.where(np.isfinite(ppp_h), ppp_h * indice_causal, np.nan)
        mapa_fecha_ppp_adj = dict(zip(fechas_h, ppp_adj_h))

        for idx_i in range(n_h):
            f_cur = fechas_h[idx_i]
            feats_adj_i = None
            win21_ev_i = 0
            if idx_i >= 20:
                win_pos = pos_h[idx_i - 20 : idx_i + 1]
                win_p_adj = ppp_adj_h[idx_i - 20 : idx_i + 1]
                if (
                    np.all(np.diff(win_pos) == 1)
                    and np.all(np.isfinite(win_p_adj))
                    and np.all(win_p_adj > 0)
                ):
                    feats_adj_i = calcular_features_ppp(win_p_adj)
                    win21_ev_i = int(np.any(evento_en_sesion[idx_i - 19 : idx_i + 1] == 1))
            lookup_em[(str(em), f_cur)] = {
                "ppp_ajustado": float(ppp_adj_h[idx_i]) if np.isfinite(ppp_adj_h[idx_i]) else np.nan,
                "evento_ex_en_sesion": int(evento_en_sesion[idx_i]),
                "ventana_21_con_evento": int(win21_ev_i),
                "feats_adj": feats_adj_i,
                "mapa_fecha_ppp_adj": mapa_fecha_ppp_adj,
            }

    df_out = panel.copy()
    n_p = len(df_out)
    ppp_adj_col = np.full(n_p, np.nan, dtype=float)
    ppp_t5_adj_col = np.full(n_p, np.nan, dtype=float)
    evento_sesion_col = np.zeros(n_p, dtype=int)
    ventana_ev_col = np.zeros(n_p, dtype=int)
    ventana_21_ev_col = np.zeros(n_p, dtype=int)
    feats_adj_mat = np.full((n_p, len(FEATURE_NAMES)), np.nan, dtype=float)

    for r_idx, row in df_out.iterrows():
        em = str(row["emisora"])
        f_cur = str(row["fecha"])
        fh5 = row["fecha_objetivo_h5"]
        info = lookup_em.get((em, f_cur))
        if info is None:
            continue
        ppp_adj_col[r_idx] = info["ppp_ajustado"]
        evento_sesion_col[r_idx] = info["evento_ex_en_sesion"]
        ventana_21_ev_col[r_idx] = info["ventana_21_con_evento"]
        if info["feats_adj"] is not None:
            feats_adj_mat[r_idx, :] = info["feats_adj"]
        if pd.notna(fh5):
            ppp_t5_adj_col[r_idx] = info["mapa_fecha_ppp_adj"].get(str(fh5), np.nan)
            for f_ex in fechas_ev_por_em.get(em, []):
                if f_cur < f_ex <= str(fh5):
                    ventana_ev_col[r_idx] = 1
                    break

    df_out["ppp_ajustado"] = ppp_adj_col
    df_out["ppp_t5_ajustado"] = ppp_t5_adj_col
    df_out["evento_ex_en_sesion"] = evento_sesion_col
    df_out["ventana_con_evento"] = ventana_ev_col
    df_out["ventana_21_con_evento"] = ventana_21_ev_col
    df_out["target_y_ajustado"] = np.where(
        np.isfinite(ppp_t5_adj_col)
        & np.isfinite(ppp_adj_col)
        & df_out["target_disponible"].astype(str).isin(["True", "true", "1"]),
        (ppp_t5_adj_col > ppp_adj_col).astype(float),
        np.nan,
    )
    for j, col in enumerate(FEATURE_NAMES):
        df_out[f"{col}_adj"] = feats_adj_mat[:, j]

    df_out.to_csv(output_path, index=False)
    return df_out


def _preparar_vista_panel(df_panel: pd.DataFrame, usar_ajustado: bool) -> pd.DataFrame:
    """
    Prepara un DataFrame con las columnas estándar de features y target_y
    (ya sea la vista original o la vista ajustada por dividendos/splits) y calcula
    las variables relativas intrapanel contemporáneas sin fuga temporal.
    """
    df = df_panel.copy()
    if usar_ajustado:
        for col in FEATURE_NAMES:
            df[col] = pd.to_numeric(df[f"{col}_adj"], errors="coerce")
        df["ppp_t"] = pd.to_numeric(df["ppp_ajustado"], errors="coerce")
        df["ppp_t5"] = pd.to_numeric(df["ppp_t5_ajustado"], errors="coerce")
        df["target_y"] = pd.to_numeric(df["target_y_ajustado"], errors="coerce")
    else:
        for col in FEATURE_NAMES:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["ppp_t"] = pd.to_numeric(df["ppp_t"], errors="coerce")
        df["ppp_t5"] = pd.to_numeric(df["ppp_t5"], errors="coerce")
        df["target_y"] = pd.to_numeric(df["target_y"], errors="coerce")

    for col_base in ["ret_1", "ret_5", "ret_10", "ret_20", "distancia_media_5", "distancia_media_20"]:
        m = df.groupby("fecha")[col_base].transform("mean")
        cnt = df.groupby("fecha")[col_base].transform("count")
        df[f"{col_base}_rel_panel"] = np.where(cnt >= 2, df[col_base] - m, 0.0)

    return df


def _evaluar_cinco_modelos_en_vista(df_vista: pd.DataFrame, sufijo: str = "") -> pd.DataFrame:
    """
    Entrena V1..V5 en TRAIN purgado (fecha_objetivo_h5 <= CORTE_TRAIN) y predice en TEST.
    """
    mask_tr = (
        (df_vista["periodo_oficial"].astype(str) == "TRAIN")
        & (df_vista["target_disponible"].astype(str).isin(["True", "true", "1"]))
        & (df_vista["fecha_objetivo_h5"] <= CORTE_TRAIN)
        & df_vista["target_y"].notna()
        & df_vista["ret_10"].notna()
    )
    mask_te = (
        (df_vista["periodo_oficial"].astype(str) == "TEST")
        & (df_vista["target_disponible"].astype(str).isin(["True", "true", "1"]))
        & df_vista["target_y"].notna()
        & df_vista["ret_10"].notna()
    )

    tr = df_vista[mask_tr].copy().reset_index(drop=True)
    te = df_vista[mask_te].copy().reset_index(drop=True)
    tr["target_y"] = tr["target_y"].astype(int)
    te["target_y"] = te["target_y"].astype(int)

    p_v1, _ = ajustar_logistica_pooled_panel(
        tr, te, VARIABLES_REL_TRES, c=0.01, tipo_scaler="STANDARD", ponderacion="UNIFORME"
    )
    p_v2 = ajustar_logistica_con_zona_neutral(
        tr, te, VARIABLES_REL_TRES, c=0.01, tau=0.0025, modo_panel=True
    )
    p_v3, _ = ajustar_logistica_pooled_panel(
        tr, te, VARIABLES_REL_TRES, c=0.001, tipo_scaler="STANDARD", ponderacion="UNIFORME"
    )
    p_v4, _ = ajustar_logistica_pooled_panel(
        tr, te, VARIABLES_DM5_REL_CUATRO, c=0.01, tipo_scaler="STANDARD", ponderacion="UNIFORME"
    )
    p_v5 = predecir_g2_v5_adaptativo_regimen_sectorial(tr, te)

    te[f"prob_V1{sufijo}"] = p_v1
    te[f"prob_V2{sufijo}"] = p_v2
    te[f"prob_V3{sufijo}"] = p_v3
    te[f"prob_V4{sufijo}"] = p_v4
    te[f"prob_V5{sufijo}"] = p_v5
    return te


def _calcular_metricas_subconjunto(
    df_eval: pd.DataFrame,
    col_prob: str,
    col_y: str = "target_y",
) -> dict[str, Any]:
    sub = df_eval[df_eval[col_prob].notna() & df_eval[col_y].notna()].copy()
    n = int(len(sub))
    if n == 0:
        return {"n": 0, "aciertos": 0, "exactitud_pct": None, "brier": None, "log_loss": None}
    p = np.clip(sub[col_prob].to_numpy(dtype=float), 1e-12, 1.0 - 1e-12)
    y = sub[col_y].to_numpy(dtype=int)
    pred = (p >= 0.5).astype(int)
    aciertos = int(np.sum(pred == y))
    acc_pct = round(100.0 * aciertos / n, 2)
    brier = round(float(np.mean((p - y) ** 2)), 6)
    ll = round(float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))), 6)
    return {
        "n": n,
        "aciertos": aciertos,
        "exactitud_pct": acc_pct,
        "brier": brier,
        "log_loss": ll,
    }


def ejecutar_fase1_higiene(
    panel_path: Path = PANEL_PATH,
    hist_path: Path = HIST_PPP_PATH,
    eventos_path: Path = EVENTOS_CORP_PATH,
    panel_ajustado_path: Path = PANEL_AJUSTADO_PATH,
    reporte_path: Path = REPORTE_FASE1_PATH,
) -> dict[str, Any]:
    """
    Ejecuta el flujo completo de la Fase 1 (Higiene de etiquetas):
    1. Construye eventos_corporativos_15_emisoras.csv
    2. Genera dataset_panel_15_emisoras_features_ajustado_fase1.csv con ppp_ajustado y ventana_con_evento
    3. Evalúa V1..V5 (originales congelados) y V1_ADJ..V5_ADJ en TEST para 15 emisoras y 4 emisoras foco
    4. Guarda reporte_fase1_higiene.json y verifica integridad de hashes protegidos.
    """
    hashes_antes = hashes_protegidos_g2()

    df_ev = construir_eventos_corporativos_15_emisoras(
        hist_path=hist_path, output_path=eventos_path
    )
    df_panel_adj = construir_panel_con_ppp_ajustado(
        panel_path=panel_path,
        hist_path=hist_path,
        eventos_path=eventos_path,
        output_path=panel_ajustado_path,
    )

    vista_orig = _preparar_vista_panel(df_panel_adj, usar_ajustado=False)
    vista_adj = _preparar_vista_panel(df_panel_adj, usar_ajustado=True)

    te_orig = _evaluar_cinco_modelos_en_vista(vista_orig, sufijo="")
    te_adj = _evaluar_cinco_modelos_en_vista(vista_adj, sufijo="_ADJ")

    te_orig_foco = te_orig[te_orig["emisora"].isin(EMISORAS_FOCO_4)].copy()
    te_adj_foco = te_adj[te_adj["emisora"].isin(EMISORAS_FOCO_4)].copy()

    modelos_base = ["V1", "V2", "V3", "V4", "V5"]
    comparativa_15: dict[str, Any] = {}
    comparativa_4_foco: dict[str, Any] = {}
    comparativa_ventanas_evento_15: dict[str, Any] = {}

    for m in modelos_base:
        m_orig_15 = _calcular_metricas_subconjunto(te_orig, f"prob_{m}")
        m_adj_15 = _calcular_metricas_subconjunto(te_adj, f"prob_{m}_ADJ")
        comparativa_15[m] = m_orig_15
        comparativa_15[f"{m}_ADJ"] = m_adj_15
        comparativa_15[f"{m}_DELTA_ADJ_MENOS_ORIG"] = {
            "delta_exactitud_pp": round(m_adj_15["exactitud_pct"] - m_orig_15["exactitud_pct"], 2),
            "delta_brier": round(m_adj_15["brier"] - m_orig_15["brier"], 6),
        }

        m_orig_4 = _calcular_metricas_subconjunto(te_orig_foco, f"prob_{m}")
        m_adj_4 = _calcular_metricas_subconjunto(te_adj_foco, f"prob_{m}_ADJ")
        comparativa_4_foco[m] = m_orig_4
        comparativa_4_foco[f"{m}_ADJ"] = m_adj_4
        comparativa_4_foco[f"{m}_DELTA_ADJ_MENOS_ORIG"] = {
            "delta_exactitud_pp": round(m_adj_4["exactitud_pct"] - m_orig_4["exactitud_pct"], 2),
            "delta_brier": round(m_adj_4["brier"] - m_orig_4["brier"], 6),
        }

        te_orig_ev = te_orig[te_orig["ventana_con_evento"] == 1]
        te_adj_ev = te_adj[te_adj["ventana_con_evento"] == 1]
        comparativa_ventanas_evento_15[m] = _calcular_metricas_subconjunto(te_orig_ev, f"prob_{m}")
        comparativa_ventanas_evento_15[f"{m}_ADJ"] = _calcular_metricas_subconjunto(
            te_adj_ev, f"prob_{m}_ADJ"
        )

    # Auditoría de cambios de etiqueta entre target_y y target_y_ajustado
    mask_elig = df_panel_adj["target_disponible"].astype(str).isin(["True", "true", "1"]) & df_panel_adj["target_y"].notna() & df_panel_adj["target_y_ajustado"].notna()
    sub_elig = df_panel_adj[mask_elig].copy()
    sub_sin_ev = sub_elig[sub_elig["ventana_con_evento"] == 0]
    sub_con_ev = sub_elig[sub_elig["ventana_con_evento"] == 1]
    cambios_en_sin_evento = int(np.sum(sub_sin_ev["target_y"] != sub_sin_ev["target_y_ajustado"]))
    cambios_en_con_evento = int(np.sum(sub_con_ev["target_y"] != sub_con_ev["target_y_ajustado"]))

    hashes_despues = hashes_protegidos_g2()
    if hashes_antes != hashes_despues:
        raise RuntimeError("Se detectó modificación en archivos protegidos durante Fase 1.")

    reporte = {
        "fase": "FASE_1_HIGIENE_DE_ETIQUETAS",
        "timestamp_utc": timestamp_utc(),
        "catalogo_eventos_corporativos": {
            "archivo": str(eventos_path.name),
            "total_eventos": int(len(df_ev)),
            "dividendos": int((df_ev["tipo"] == "DIVIDENDO").sum()),
            "splits": int((df_ev["tipo"] == "SPLIT").sum()),
            "eventos_por_emisora": {
                str(k): int(v) for k, v in df_ev.groupby("emisora").size().to_dict().items()
            },
        },
        "auditoria_etiquetas_panel": {
            "total_observaciones_con_target": int(len(sub_elig)),
            "observaciones_ventana_con_evento": int(len(sub_con_ev)),
            "observaciones_ventana_sin_evento": int(len(sub_sin_ev)),
            "cambios_etiqueta_en_ventana_sin_evento": cambios_en_sin_evento,
            "cambios_etiqueta_en_ventana_con_evento": cambios_en_con_evento,
            "test_15_n_ventanas_con_evento": int((te_orig["ventana_con_evento"] == 1).sum()),
            "test_4_foco_n_ventanas_con_evento": int((te_orig_foco["ventana_con_evento"] == 1).sum()),
        },
        "test_15_emisoras": comparativa_15,
        "test_4_emisoras_foco": comparativa_4_foco,
        "test_15_solo_ventanas_con_evento": comparativa_ventanas_evento_15,
        "integridad_archivos_protegidos_intacta": True,
    }
    reporte_path.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")
    return reporte


if __name__ == "__main__":
    rep = ejecutar_fase1_higiene()
    print(json.dumps(rep, indent=2, ensure_ascii=False))

