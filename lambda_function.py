import datetime
import hashlib
import io
import json
import re
import urllib.request
import boto3
import pandas as pd

# ==============================================================================
# CONFIGURACIÓN DEL DATA LAKE
# ==============================================================================
# Escribe aqui el nombre exacto de tu bucket creado en S3:
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

YF_TICKER_MAP = {
    ("GMEXICO", "B"): "GMEXICOB.MX",
    ("GFNORTE", "O"): "GFNORTEO.MX",
    ("FEMSA", "UBD"): "FEMSAUBD.MX",
    ("AMX", "B"): "AMXB.MX",
    ("WALMEX", "*"): "WALMEX.MX",
    ("CEMEX", "CPO"): "CEMEXCPO.MX",
    ("PE&OLES", "*"): "PENOLES.MX",
    ("GAP", "B"): "GAPB.MX",
    ("AC", "*"): "AC.MX",
    ("ASUR", "B"): "ASURB.MX",
    ("BIMBO", "A"): "BIMBOA.MX",
    ("GFINBUR", "O"): "GFINBURO.MX",
    ("VESTA", "*"): "VESTA.MX",
    ("LIVEPOL", "C-1"): "LIVEPOLC-1.MX",
    ("GRUMA", "B"): "GRUMAB.MX",
}


def fetch_secondary_contingency_quotes(fecha_iso: str) -> tuple[dict, bytes, str, str]:
    target_dt = datetime.date.fromisoformat(fecha_iso)
    cdmx_tz = datetime.timezone(datetime.timedelta(hours=-6))
    p1 = int(datetime.datetime(target_dt.year, target_dt.month, target_dt.day, 0, 0, 0, tzinfo=cdmx_tz).timestamp()) - 86400 * 7
    p2 = int(datetime.datetime(target_dt.year, target_dt.month, target_dt.day, 23, 59, 59, tzinfo=cdmx_tz).timestamp()) + 86400

    quotes = {}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PrismaBMV-BigData/1.0"}

    for ticker, serie, _, _ in EMISORAS_15:
        yf_sym = YF_TICKER_MAP.get((ticker, serie))
        if not yf_sym:
            continue

        url_1d = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}?period1={p1}&period2={p2}&interval=1d"
        close_day = None
        prev_close = None
        try:
            req_1d = urllib.request.Request(url_1d, headers=headers)
            with urllib.request.urlopen(req_1d, timeout=15) as resp:
                data_1d = json.loads(resp.read().decode("utf-8", errors="ignore"))
            res_1d = data_1d.get("chart", {}).get("result", [])
            if res_1d:
                ts_list = res_1d[0].get("timestamp", []) or []
                closes = res_1d[0].get("indicators", {}).get("quote", [{}])[0].get("close", []) or []
                daily_pairs = []
                for ts, cl in zip(ts_list, closes):
                    if cl is not None:
                        d_str = datetime.datetime.fromtimestamp(ts, tz=cdmx_tz).strftime("%Y-%m-%d")
                        daily_pairs.append((d_str, float(cl)))
                for idx_d, (d_str, cl_val) in enumerate(daily_pairs):
                    if d_str == fecha_iso:
                        close_day = round(cl_val, 2)
                        if idx_d > 0:
                            prev_close = round(daily_pairs[idx_d - 1][1], 2)
                        break
        except Exception:
            pass

        if close_day is None:
            continue

        vwap_ppp = close_day
        p1_1m = int(datetime.datetime(target_dt.year, target_dt.month, target_dt.day, 7, 0, 0, tzinfo=cdmx_tz).timestamp())
        p2_1m = int(datetime.datetime(target_dt.year, target_dt.month, target_dt.day, 16, 0, 0, tzinfo=cdmx_tz).timestamp())
        url_1m = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}?period1={p1_1m}&period2={p2_1m}&interval=1m"
        try:
            req_1m = urllib.request.Request(url_1m, headers=headers)
            with urllib.request.urlopen(req_1m, timeout=15) as resp:
                data_1m = json.loads(resp.read().decode("utf-8", errors="ignore"))
            res_1m = data_1m.get("chart", {}).get("result", [])
            if res_1m:
                ts_1m = res_1m[0].get("timestamp", []) or []
                q_1m = res_1m[0].get("indicators", {}).get("quote", [{}])[0]
                c_1m = q_1m.get("close", []) or []
                h_1m = q_1m.get("high", []) or []
                l_1m = q_1m.get("low", []) or []
                v_1m = q_1m.get("volume", []) or []
                pv_sum = 0.0
                v_sum = 0.0
                fallback_prices = []
                for ts, c_v, h_v, l_v, vol_v in zip(ts_1m, c_1m, h_1m, l_1m, v_1m):
                    if c_v is None:
                        continue
                    dt_bar = datetime.datetime.fromtimestamp(ts, tz=cdmx_tz)
                    if dt_bar.strftime("%Y-%m-%d") != fecha_iso:
                        continue
                    hm = dt_bar.hour * 60 + dt_bar.minute
                    if 13 * 60 + 40 <= hm <= 14 * 60:
                        typ_p = (float(h_v) + float(l_v) + float(c_v)) / 3.0 if (h_v is not None and l_v is not None) else float(c_v)
                        vol_bar = float(vol_v) if (vol_v is not None and vol_v > 0) else 0.0
                        pv_sum += typ_p * vol_bar
                        v_sum += vol_bar
                        fallback_prices.append(float(c_v))
                if v_sum > 0:
                    vwap_ppp = round(pv_sum / v_sum, 2)
                elif fallback_prices:
                    vwap_ppp = round(sum(fallback_prices) / len(fallback_prices), 2)
        except Exception:
            pass

        ant = prev_close if (prev_close is not None and prev_close > 0) else close_day
        var_pct = round((vwap_ppp / ant - 1.0) * 100.0, 2) if ant > 0 else 0.0
        quotes[(ticker, serie)] = {
            "ultimo": close_day,
            "anterior": ant,
            "ppp": vwap_ppp,
            "variacion_ppp_vs_anterior_pct": var_pct,
        }

    payload = {
        "fecha": fecha_iso,
        "fuente": "CONTINGENCIA_FUENTE_SECUNDARIA_YAHOO_FINANCE_VWAP_1340_1400",
        "quotes": {f"{k[0]}|{k[1]}": v for k, v in sorted(quotes.items())},
    }
    raw_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    url_contingencia = f"https://query1.finance.yahoo.com/v8/finance/chart/WALMEX.MX?date={fecha_iso}#contingencia_bmv_404"
    return quotes, raw_bytes, sha256_hex, url_contingencia


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
        header_cols = []
        for r in rows:
            th_td = [re.sub(r"<[^>]+>", "", td).strip() for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, flags=re.DOTALL | re.IGNORECASE)]
            th_td = [c for c in th_td if c]
            if any("Emisora" in c for c in th_td):
                header_cols = th_td
                break

        expected_cols = len(header_cols)

        for r in rows:
            tds = re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.DOTALL | re.IGNORECASE)
            clean = [re.sub(r"<[^>]+>", "", td).strip() for td in tds]
            clean = [re.sub(r"\s+", " ", td) for td in clean if td]
            if len(clean) >= 5 and clean[0] not in ["Emisora", "M&aacute;s Negociadas", "Mayor Variaci&oacute;n a la Alza", "Mayor Variaci&oacute;n a la Baja"]:
                tk = clean[0]
                sr = clean[1]

                if expected_cols > 0 and len(clean) < expected_cols:
                    continue

                try:
                    ult = float(clean[2].replace(",", ""))
                    ant = float(clean[3].replace(",", ""))
                    candidate_ppp = float(clean[4].replace(",", ""))

                    if candidate_ppp <= 0:
                        continue
                    if ant > 0:
                        var_teorica = round((ult / ant - 1.0) * 100.0, 2)
                        if abs(candidate_ppp - var_teorica) < 0.05 and abs(candidate_ppp - ult) > 5.0:
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


def _procesar_fecha_en_s3(s3, fecha_str: str) -> dict:
    fecha_iso = f"{fecha_str[:4]}-{fecha_str[4:6]}-{fecha_str[6:]}"
    url_boletin = f"https://www.bmv.com.mx/docs-pub/rss/boletin{fecha_str}.html"
    silver_key = f"silver/precios_ppp/{fecha_str[:4]}/{fecha_str[4:6]}/ppp_15_emisoras_{fecha_str}.csv"
    print(f"Iniciando descarga oficial BMV para {fecha_iso}: {url_boletin}")

    raw_html_bytes = None
    try:
        req = urllib.request.Request(
            url_boletin,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PrismaBMV-BigData/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            raw_html_bytes = response.read()
    except Exception as e:
        print(f"Boletin primario no disponible para {fecha_iso} ({e}). Evaluando contingencia secundaria...")

    if raw_html_bytes is not None:
        sha256_fuente = hashlib.sha256(raw_html_bytes).hexdigest()
        url_fuente = url_boletin
        estado_captura_ok = "PPP_PUBLICADO_VERIFICADO"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/boletin_{fecha_str}.html",
            Body=raw_html_bytes,
            ContentType="text/html"
        )
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/boletin_{fecha_str}.sha256",
            Body=sha256_fuente.encode("utf-8"),
            ContentType="text/plain"
        )
        quotes = parse_bulletin_quotes(raw_html_bytes)
    else:
        try:
            obj_prev = s3.get_object(Bucket=BUCKET_NAME, Key=silver_key)
            df_prev = pd.read_csv(io.BytesIO(obj_prev["Body"].read()))
            if "estado_captura" in df_prev.columns and (df_prev["estado_captura"] == "PPP_PUBLICADO_VERIFICADO").any():
                return {
                    "estado": "PRIMARIA_PREVIA_PRESERVADA",
                    "fecha": fecha_iso,
                    "s3_silver": f"s3://{BUCKET_NAME}/{silver_key}",
                }
        except Exception:
            pass

        quotes, raw_json_bytes, sha256_fuente, url_fuente = fetch_secondary_contingency_quotes(fecha_iso)
        if not quotes:
            raise RuntimeError(f"Sin datos primarios ni secundarios para {fecha_iso}")
        estado_captura_ok = "CONTINGENCIA_FUENTE_SECUNDARIA"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/contingencia_{fecha_str}.json",
            Body=raw_json_bytes,
            ContentType="application/json"
        )
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/contingencia_{fecha_str}.sha256",
            Body=sha256_fuente.encode("utf-8"),
            ContentType="text/plain"
        )

    registros = []
    for ticker, serie, anillo, sector in EMISORAS_15:
        q = quotes.get((ticker, serie))
        if q is not None:
            ev_str = (
                f"{ticker} / {serie} / PPP / {q['ppp']:.2f}"
                if estado_captura_ok == "PPP_PUBLICADO_VERIFICADO"
                else f"{ticker} / {serie} / VWAP_CONTINGENCIA_1340_1400 / {q['ppp']:.2f}"
            )
            registros.append({
                "fecha": fecha_iso,
                "emisora": ticker,
                "serie": serie,
                "anillo_madurez": anillo,
                "sector_economico": sector,
                "estado_captura": estado_captura_ok,
                "ppp_bmv_mxn": q["ppp"],
                "ultimo_bmv_mxn": q["ultimo"],
                "anterior_bmv_mxn": q["anterior"],
                "variacion_ppp_vs_anterior_pct": q["variacion_ppp_vs_anterior_pct"],
                "evidencia_exacta": ev_str,
                "url_fuente": url_fuente,
                "sha256_boletin": sha256_fuente,
            })
        else:
            registros.append({
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
                "evidencia_exacta": "Emisora ausente del boletin RSS de la fecha; hueco conservado, no se imputa valor",
                "url_fuente": url_fuente,
                "sha256_boletin": sha256_fuente,
            })

    df_silver = pd.DataFrame(registros)
    csv_bytes = df_silver.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=silver_key,
        Body=csv_bytes,
        ContentType="text/csv"
    )

    return {
        "estado": "EXITO_PROCESADO",
        "fecha": fecha_iso,
        "fuente": estado_captura_ok,
        "sha256": sha256_fuente,
        "emisoras_capturadas": sum(1 for r in registros if r["ppp_bmv_mxn"] is not None),
        "s3_silver": f"s3://{BUCKET_NAME}/{silver_key}",
    }


def lambda_handler(event, context):
    s3 = boto3.client("s3")

    if event and isinstance(event, dict) and "fecha" in event:
        fecha_str = str(event["fecha"]).replace("-", "")
    else:
        cdmx_tz = datetime.timezone(datetime.timedelta(hours=-6))
        ahora = datetime.datetime.now(cdmx_tz)
        fecha_str = ahora.strftime("%Y%m%d")

    cola_fechas = [fecha_str]
    if event and isinstance(event, dict) and "fechas" in event and isinstance(event["fechas"], list):
        for f_item in event["fechas"]:
            f_clean = str(f_item).replace("-", "")
            if len(f_clean) == 8 and f_clean not in cola_fechas:
                cola_fechas.append(f_clean)
    cola_fechas = sorted(cola_fechas)

    resultados = []
    for f_str in cola_fechas:
        try:
            resultados.append(_procesar_fecha_en_s3(s3, f_str))
        except Exception as e_f:
            print(f"Error procesando {f_str}: {e_f}")

    if not resultados:
        return {
            "statusCode": 404,
            "body": json.dumps({"estado": "ERROR_DESCARGA", "mensaje": f"Sin datos para {cola_fechas}"})
        }

    print("Resumen de ejecucion:", json.dumps(resultados, indent=2))
    return {
        "statusCode": 200,
        "body": json.dumps({"estado": "EXITO_PROCESADO", "resultados": resultados})
    }