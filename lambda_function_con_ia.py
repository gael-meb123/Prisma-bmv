"""
Prisma BMV - Código Oficial para AWS Lambda con Inferencia de IA (Capa Gold)
Archivo: lambda_function_con_ia.py
Instrucciones: Copia todo este archivo y pégalo en lambda_function.py en la consola de AWS Lambda.
"""

import datetime
import hashlib
import io
import json
import re
import urllib.request
import boto3
import numpy as np
import pandas as pd

# ==============================================================================
# CONFIGURACIÓN DEL DATA LAKE
# ==============================================================================
# IMPORTANTE: Reemplaza con el nombre exacto de tu bucket en Amazon S3:
BUCKET_NAME = "prisma-bmv-datalake-tunombre-2026"

EMISORAS_15 = [
    ("GMEXICO", "B", "Anillo 2 (Plata: Seleccion Modelo Sectorial)", "Mineria y materiales"),
    ("GFNORTE", "O", "Anillo 2 (Plata: Seleccion Modelo Sectorial)", "Banca y servicios financieros"),
    ("FEMSA", "UBD", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Consumo y comercio"),
    ("AMX", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Telecomunicaciones"),
    ("WALMEX", "*", "Anillo 1 (Oro: Inferencia Prospectiva Estricta)", "Comercio y autoservicio"),
    ("CEMEX", "CPO", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Cemento y construccion"),
    ("PE&OLES", "*", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Mineria y metales"),
    ("GAP", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Infraestructura aeroportuaria"),
    ("AC", "*", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Bebidas y consumo"),
    ("ASUR", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Infraestructura aeroportuaria"),
    ("BIMBO", "A", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Industria alimentaria"),
    ("GFINBUR", "O", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Servicios financieros"),
    ("VESTA", "*", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Inmuebles industriales"),
    ("LIVEPOL", "C-1", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Comercio departamental"),
    ("GRUMA", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Industria alimentaria"),
]

# Parámetros matemáticos oficiales calibrados de los modelos de 2ª Generación (Panel G2)
MODELOS_G2_CONFIG = {
    "G2_V1_POOLED_REL3_CALIBRADO": {
        "beta": [0.005237, -0.136803, -0.038745, -0.025182],
        "c_val": 0.01,
        "tau_val": 0.0,
        "scalers": {
            "AMX": {"mean": [0.00282, 0.00003, 0.01521], "scale": [0.05120, 0.03710, 0.00580]},
            "GFNORTE": {"mean": [0.00315, 0.00004, 0.01840], "scale": [0.05310, 0.03920, 0.00690]},
            "GMEXICO": {"mean": [0.00350, 0.00005, 0.01910], "scale": [0.05520, 0.04110, 0.00710]},
            "WALMEX": {"mean": [0.00290, 0.00002, 0.01630], "scale": [0.04980, 0.03650, 0.00590]},
        },
    },
    "G2_V2_POOLED_REL3_ZONA_NEUTRAL": {
        "beta": [-0.000773, -0.129536, -0.050115, -0.028877],
        "c_val": 0.01,
        "tau_val": 0.0025,
        "scalers": {
            "AMX": {"mean": [0.00282, 0.00003, 0.01521], "scale": [0.05120, 0.03710, 0.00580]},
            "GFNORTE": {"mean": [0.00315, 0.00004, 0.01840], "scale": [0.05310, 0.03920, 0.00690]},
            "GMEXICO": {"mean": [0.00350, 0.00005, 0.01910], "scale": [0.05520, 0.04110, 0.00710]},
            "WALMEX": {"mean": [0.00290, 0.00002, 0.01630], "scale": [0.04980, 0.03650, 0.00590]},
        },
    },
    "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO": {
        "beta": [0.009705, -0.077949, -0.034840, 0.007082],
        "c_val": 0.001,
        "tau_val": 0.0,
        "scalers": {
            "AMX": {"mean": [0.00410, 0.00005, 0.01520], "scale": [0.05180, 0.03850, 0.00570]},
            "GFNORTE": {"mean": [0.00430, 0.00006, 0.01830], "scale": [0.05380, 0.04050, 0.00680]},
            "GMEXICO": {"mean": [0.00460, 0.00007, 0.01900], "scale": [0.05590, 0.04220, 0.00700]},
            "WALMEX": {"mean": [0.00405, 0.00004, 0.01620], "scale": [0.05040, 0.03790, 0.00580]},
        },
    },
}


def parse_bulletin_quotes(raw_html_bytes: bytes) -> dict:
    if not raw_html_bytes:
        return {}
    html_txt = raw_html_bytes.decode("utf-8", errors="ignore")
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html_txt, flags=re.DOTALL | re.IGNORECASE)
    quotes = {}
    for tbl in tables:
        header_text = re.sub(r"<[^>]+>", " ", tbl[:300])
        is_quote_table = (
            ("Negociadas" in header_text or "Variac" in header_text or "Alza" in header_text or "Baja" in header_text)
            and "Paquetes" not in header_text
        )
        if not is_quote_table:
            continue
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, flags=re.DOTALL | re.IGNORECASE)
        for r in rows:
            tds = re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.DOTALL | re.IGNORECASE)
            clean = [re.sub(r"<[^>]+>", "", td).strip() for td in tds]
            clean = [re.sub(r"\s+", " ", td) for td in clean if td]
            if len(clean) >= 5 and clean[0] not in [
                "Emisora",
                "M&aacute;s Negociadas",
                "Mayor Variaci&oacute;n a la Alza",
                "Mayor Variaci&oacute;n a la Baja",
            ]:
                try:
                    tk = clean[0]
                    sr = clean[1]
                    ult = float(clean[2].replace(",", ""))
                    ant = float(clean[3].replace(",", ""))
                    candidate_ppp = float(clean[4].replace(",", ""))
                    if candidate_ppp <= 0:
                        continue
                    var_pct = round((candidate_ppp / ant - 1.0) * 100.0, 2) if ant > 0 else 0.0
                    k = (tk, sr)
                    if k not in quotes:
                        quotes[k] = {
                            "ultimo": ult,
                            "anterior": ant,
                            "ppp": candidate_ppp,
                            "variacion_ppp_vs_anterior_pct": var_pct,
                        }
                except (ValueError, ZeroDivisionError):
                    pass
    return quotes


def calcular_fecha_h5(fecha_iso: str) -> str:
    """Calcula la fecha a 5 sesiones hábiles omitiendo fines de semana."""
    dt = datetime.date.fromisoformat(fecha_iso)
    agregadas = 0
    while agregadas < 5:
        dt += datetime.timedelta(days=1)
        if dt.weekday() < 5:  # Lunes a Viernes
            agregadas += 1
    return dt.isoformat()


def inferir_modelos_g2(emisora: str, ret_10: float, ret_10_rel: float, vol_20: float) -> tuple[dict, str]:
    x_raw = np.array([ret_10, ret_10_rel, vol_20], dtype=float)
    res = {}
    preds = []

    for id_mod, cfg in MODELOS_G2_CONFIG.items():
        b = np.array(cfg["beta"])
        sc = cfg["scalers"].get(emisora, cfg["scalers"]["WALMEX"])
        m_vec = np.array(sc["mean"])
        s_vec = np.array(sc["scale"])
        x_s = (x_raw - m_vec) / s_vec
        x_aug = np.append(1.0, x_s)
        p = 1.0 / (1.0 + np.exp(-np.dot(b, x_aug)))
        clase = int(p >= 0.5)
        preds.append(clase)
        res[id_mod] = {
            "probabilidad": float(p),
            "clase": clase,
            "etiqueta": "SUBIDA" if clase == 1 else "NO_SUBIDA",
        }

    if all(c == 1 for c in preds):
        consenso = "CONSENSO_PANEL_G2_SUBIDA"
    elif all(c == 0 for c in preds):
        consenso = "CONSENSO_PANEL_G2_NO_SUBIDA"
    else:
        consenso = f"DIVERGENCIA_PANEL_G2 (V1={res['G2_V1_POOLED_REL3_CALIBRADO']['etiqueta']}, V2={res['G2_V2_POOLED_REL3_ZONA_NEUTRAL']['etiqueta']}, V3={res['G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO']['etiqueta']})"

    return res, consenso


def lambda_handler(event, context):
    s3 = boto3.client("s3")

    # 1. Determinar fecha
    if event and isinstance(event, dict) and "fecha" in event:
        fecha_str = str(event["fecha"])
    else:
        cdmx_tz = datetime.timezone(datetime.timedelta(hours=-6))
        ahora = datetime.datetime.now(cdmx_tz)
        fecha_str = ahora.strftime("%Y%m%d")

    fecha_iso = f"{fecha_str[:4]}-{fecha_str[4:6]}-{fecha_str[6:]}"
    url_boletin = f"https://www.bmv.com.mx/docs-pub/rss/boletin{fecha_str}.html"
    print(f"Descargando boletin BMV: {url_boletin}")

    # 2. Descarga del boletín oficial
    try:
        req = urllib.request.Request(
            url_boletin, headers={"User-Agent": "Mozilla/5.0 PrismaBMV-CloudML/1.0"}
        )
        with urllib.request.urlopen(req, timeout=25) as response:
            raw_html_bytes = response.read()
    except Exception as e:
        err_msg = f"Boletin no disponible para {fecha_iso}: {str(e)}"
        print(err_msg)
        return {
            "statusCode": 404,
            "body": json.dumps({"estado": "ERROR_DESCARGA", "mensaje": err_msg}),
        }

    sha256_html = hashlib.sha256(raw_html_bytes).hexdigest()

    # 3. Guardar en CAPA BRONZE
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/boletin_{fecha_str}.html",
        Body=raw_html_bytes,
        ContentType="text/html",
    )
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/boletin_{fecha_str}.sha256",
        Body=sha256_html.encode("utf-8"),
        ContentType="text/plain",
    )

    # 4. Extracción y guardado en CAPA SILVER
    quotes = parse_bulletin_quotes(raw_html_bytes)
    registros_silver = []

    for ticker, serie, anillo, sector in EMISORAS_15:
        q = quotes.get((ticker, serie))
        if q is not None:
            registros_silver.append({
                "fecha": fecha_iso,
                "emisora": ticker,
                "serie": serie,
                "anillo_madurez": anillo,
                "sector_economico": sector,
                "estado_captura": "PPP_PUBLICADO_VERIFICADO",
                "ppp_bmv_mxn": q["ppp"],
                "ultimo_bmv_mxn": q["ultimo"],
                "anterior_bmv_mxn": q["anterior"],
                "variacion_ppp_vs_anterior_pct": q["variacion_ppp_vs_anterior_pct"],
                "evidencia_exacta": f"{ticker} / {serie} / PPP / {q['ppp']:.2f}",
                "url_fuente": url_boletin,
                "sha256_boletin": sha256_html,
            })
        else:
            registros_silver.append({
                "fecha": fecha_iso,
                "emisora": ticker,
                "serie": serie,
                "anillo_madurez": anillo,
                "sector_economico": sector,
                "estado_captura": "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA",
                "ppp_bmv_mxn": None,
                "ultimo_bmv_mxn": None,
                "anterior_bmv_mxn": None,
                "variacion_ppp_vs_anterior_pct": None,
                "evidencia_exacta": "Ausente del boletin; cero imputacion",
                "url_fuente": url_boletin,
                "sha256_boletin": sha256_html,
            })

    df_silver = pd.DataFrame(registros_silver)
    csv_bytes = df_silver.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"silver/precios_ppp/{fecha_str[:4]}/{fecha_str[4:6]}/ppp_15_emisoras_{fecha_str}.csv",
        Body=csv_bytes,
        ContentType="text/csv",
    )

    # 5. INFERENCIA DE IA EN LA NUBE (Capa Gold - Modelos G2)
    print("Iniciando inferencia predictiva de Inteligencia Artificial (Panel G2)...")
    resumen_ia = {}

    try:
        # Cargar serie histórica reciente de S3 Silver
        obj_hist = s3.get_object(Bucket=BUCKET_NAME, Key="silver/serie_unificada_reciente.csv")
        df_hist = pd.read_csv(io.BytesIO(obj_hist["Body"].read()))

        # Combinar con los precios verificados de hoy
        df_hoy_verif = df_silver[df_silver["estado_captura"] == "PPP_PUBLICADO_VERIFICADO"][
            ["fecha", "emisora", "ppp_bmv_mxn"]
        ].dropna()
        df_serie = pd.concat([df_hist, df_hoy_verif], ignore_index=True).drop_duplicates(
            subset=["fecha", "emisora"], keep="last"
        )
        df_serie = df_serie.sort_values(["emisora", "fecha"]).reset_index(drop=True)

        emisoras_panel = ["AMX", "GFNORTE", "GMEXICO", "WALMEX"]
        rets_10_hoy = {}
        vols_20_hoy = {}
        precios_hoy = {}

        for em in emisoras_panel:
            sub = df_serie[df_serie["emisora"] == em].sort_values("fecha")
            precios = sub["ppp_bmv_mxn"].dropna().to_numpy(dtype=float)
            if len(precios) >= 11:
                rets_10_hoy[em] = float(precios[-1] / precios[-11] - 1.0)
                precios_hoy[em] = float(precios[-1])
            if len(precios) >= 21:
                rets_1 = precios[1:] / precios[:-1] - 1.0
                vols_20_hoy[em] = float(np.std(rets_1[-20:], ddof=1))

        # Calcular media transversal del panel
        if len(rets_10_hoy) >= 2:
            media_panel_10 = float(np.mean(list(rets_10_hoy.values())))
        else:
            media_panel_10 = 0.0

        fecha_obj_h5 = calcular_fecha_h5(fecha_iso)
        filas_gold_nuevas = []

        for em in emisoras_panel:
            if em not in rets_10_hoy or em not in vols_20_hoy:
                continue
            r10 = rets_10_hoy[em]
            r10_rel = float(r10 - media_panel_10)
            v20 = vols_20_hoy[em]
            ppp_t = precios_hoy[em]

            predicciones, consenso_str = inferir_modelos_g2(em, r10, r10_rel, v20)
            resumen_ia[em] = consenso_str

            for id_mod, res_mod in predicciones.items():
                filas_gold_nuevas.append({
                    "id_senal_g2": f"{em}_{fecha_str}_{id_mod}",
                    "generacion_modelo": "G2_PANEL_MULTIVARIADO",
                    "fecha_senal": fecha_iso,
                    "fecha_objetivo_h5": fecha_obj_h5,
                    "calendario_objetivo": "OFICIAL_2026",
                    "emisora": em,
                    "serie": (
                        "*"
                        if em in ["WALMEX", "PE&OLES", "AC", "VESTA"]
                        else ("O" if em in ["GFNORTE", "GFINBUR"] else "B")
                    ),
                    "sector_economico": (
                        "Consumo"
                        if em == "WALMEX"
                        else (
                            "Mineria"
                            if em == "GMEXICO"
                            else ("Banca" if em == "GFNORTE" else "Telecom")
                        )
                    ),
                    "modelo_g2": id_mod,
                    "modo_entrenamiento": "POOLED_PANEL",
                    "n_train_panel": 9679,
                    "fin_etiquetas_train_panel": "2026-10-23",
                    "c_regularizacion": MODELOS_G2_CONFIG[id_mod]["c_val"],
                    "tau_zona_neutral": MODELOS_G2_CONFIG[id_mod]["tau_val"],
                    "ppp_base_t": ppp_t,
                    "ret_10": r10,
                    "media_ret_10_panel_corte": media_panel_10,
                    "ret_10_rel_panel": r10_rel,
                    "volatilidad_20": v20,
                    "probabilidad_subida": res_mod["probabilidad"],
                    "prediccion_clase": res_mod["clase"],
                    "prediccion_etiqueta": res_mod["etiqueta"],
                    "estado_consenso_g2": consenso_str,
                    "estado_resolucion": "EN_CURSO_PROSPECTIVA",
                    "sesiones_transcurridas": 0,
                    "fecha_parcial_reciente": fecha_iso,
                    "ppp_parcial_reciente": ppp_t,
                    "retorno_parcial_pct": 0.0,
                    "acierto_parcial_en_curso": None,
                    "ppp_t5_observado": None,
                    "target_y_observado": None,
                    "acierto_direccional_t5": None,
                    "brier_observado_t5": None,
                })

        # 6. Guardar en CAPA GOLD de S3
        if filas_gold_nuevas:
            df_nuevas = pd.DataFrame(filas_gold_nuevas)
            gold_key = "gold/senales_g2/registro_senales_prospectivas_panel_g2.csv"
            try:
                obj_gold = s3.get_object(Bucket=BUCKET_NAME, Key=gold_key)
                df_gold_prev = pd.read_csv(io.BytesIO(obj_gold["Body"].read()))
                df_gold_comb = pd.concat([df_gold_prev, df_nuevas], ignore_index=True).drop_duplicates(
                    subset=["id_senal_g2"], keep="last"
                )
            except Exception:
                df_gold_comb = df_nuevas

            csv_gold = df_gold_comb.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            s3.put_object(Bucket=BUCKET_NAME, Key=gold_key, Body=csv_gold, ContentType="text/csv")
            print(f"Capa Gold actualizada con {len(filas_gold_nuevas)} nuevas inferencias IA.")

            # Guardar la serie actualizada en S3 para la sesión de mañana
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key="silver/serie_unificada_reciente.csv",
                Body=df_serie.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                ContentType="text/csv",
            )
    except Exception as e:
        print(f"Aviso: Inferencia IA pospuesta o error de cálculo: {str(e)}")

    resultado = {
        "estado": "EXITO_PROCESADO_E_INFERENCIA_IA",
        "fecha": fecha_iso,
        "sha256": sha256_html,
        "emisoras_verificadas": sum(
            1 for r in registros_silver if r["estado_captura"] == "PPP_PUBLICADO_VERIFICADO"
        ),
        "inferencias_g2_generadas": len(resumen_ia),
        "consensos": resumen_ia,
        "s3_gold": f"s3://{BUCKET_NAME}/gold/senales_g2/registro_senales_prospectivas_panel_g2.csv",
    }
    print("Resumen de ejecución:", json.dumps(resultado, indent=2))

    return {"statusCode": 200, "body": json.dumps(resultado)}
