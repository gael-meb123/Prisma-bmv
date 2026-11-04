import datetime
import hashlib
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


def lambda_handler(event, context):
    s3 = boto3.client("s3")

    if event and isinstance(event, dict) and "fecha" in event:
        fecha_str = str(event["fecha"])
    else:
        cdmx_tz = datetime.timezone(datetime.timedelta(hours=-6))
        ahora = datetime.datetime.now(cdmx_tz)
        fecha_str = ahora.strftime("%Y%m%d")

    fecha_iso = f"{fecha_str[:4]}-{fecha_str[4:6]}-{fecha_str[6:]}"
    url_boletin = f"https://www.bmv.com.mx/docs-pub/rss/boletin{fecha_str}.html"
    print(f"Iniciando descarga oficial BMV para {fecha_iso}: {url_boletin}")

    try:
        req = urllib.request.Request(
            url_boletin,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PrismaBMV-BigData/1.0"}
        )
        with urllib.request.urlopen(req, timeout=25) as response:
            raw_html_bytes = response.read()
    except Exception as e:
        err_msg = f"Boletin no disponible para {fecha_iso}: {str(e)}"
        print(err_msg)
        return {
            "statusCode": 404,
            "body": json.dumps({"estado": "ERROR_DESCARGA", "mensaje": err_msg})
        }

    sha256_html = hashlib.sha256(raw_html_bytes).hexdigest()
    print(f"Descarga exitosa ({len(raw_html_bytes)} bytes). SHA256: {sha256_html}")

    # 1. Guardar en CAPA BRONZE
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/boletin_{fecha_str}.html",
        Body=raw_html_bytes,
        ContentType="text/html"
    )
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/boletin_{fecha_str}.sha256",
        Body=sha256_html.encode("utf-8"),
        ContentType="text/plain"
    )

    # 2. Extraccion oficial de las 15 emisoras (Cero imputacion)
    quotes = parse_bulletin_quotes(raw_html_bytes)
    registros = []

    for ticker, serie, anillo, sector in EMISORAS_15:
        q = quotes.get((ticker, serie))
        if q is not None:
            registros.append({
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
                "url_fuente": url_boletin,
                "sha256_boletin": sha256_html,
            })

    df_silver = pd.DataFrame(registros)
    csv_bytes = df_silver.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

    # 3. Guardar en CAPA SILVER
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"silver/precios_ppp/{fecha_str[:4]}/{fecha_str[4:6]}/ppp_15_emisoras_{fecha_str}.csv",
        Body=csv_bytes,
        ContentType="text/csv"
    )

    verificadas = sum(1 for r in registros if r["estado_captura"] == "PPP_PUBLICADO_VERIFICADO")
    ausentes = sum(1 for r in registros if r["estado_captura"] == "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA")

    resultado = {
        "estado": "EXITO_PROCESADO",
        "fecha": fecha_iso,
        "sha256": sha256_html,
        "emisoras_verificadas": verificadas,
        "emisoras_ausentes": ausentes,
        "s3_bronze": f"s3://{BUCKET_NAME}/bronze/{fecha_str[:4]}/{fecha_str[4:6]}/boletin_{fecha_str}.html",
        "s3_silver": f"s3://{BUCKET_NAME}/silver/precios_ppp/{fecha_str[:4]}/{fecha_str[4:6]}/ppp_15_emisoras_{fecha_str}.csv",
    }
    print("Resumen de ejecucion:", json.dumps(resultado, indent=2))

    return {
        "statusCode": 200,
        "body": json.dumps(resultado)
    }