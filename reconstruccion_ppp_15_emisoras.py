"""
reconstruccion_ppp_15_emisoras.py
==================================
Reconstruccion historica estricta (10 anos, 2016-10-27 a 2026-10-28) de la serie
oficial de Precio Promedio Ponderado (PPP) de la Bolsa Mexicana de Valores (BMV)
para las 15 empresas del IPC acordadas con el usuario.

Principios rectores metodologicos de Prisma BMV:
1. Fuente exclusivamente publica, oficial y gratuita: Boletines diarios BMV
   (https://www.bmv.com.mx/docs-pub/rss/boletinYYYYMMDD.html).
2. Sin imputaciones, sin arrastre de ultimo precio (forward-fill prohibido),
   sin rellenar con ceros. Preservacion documental estricta de huecos.
3. Auditoria criptografica de integridad: SHA-256 de cada boletin HTML.
4. Validacion automatica contra el Ground Truth auditado de WALMEX * (9C y 9G).
5. Trazabilidad de transiciones corporativas oficiales: AMX serie L -> serie B (marzo 2023).
"""

import os
import sys
import re
import io
import time
import json
import zipfile
import hashlib
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

WORKSPACE = Path(r"D:\Universidad\7mo Semestre\Big Data\Proyecto final")
PARCIAL3 = Path(r"D:\Universidad\7mo Semestre\Big Data\Parcial 3")
CACHE_DIR = WORKSPACE / "cache_boletines"
CACHE_DIR.mkdir(exist_ok=True)

Z9C = PARCIAL3 / "Prisma_BMV_Etapa9C_WALMEX_Cierre_Uniforme.zip"
Z9G = PARCIAL3 / "Prisma_BMV_Etapa9G_Insumos_Prueba_Final_CORREGIDO.zip"

OUTPUT_SERIE_CSV = WORKSPACE / "serie_ppp_historica_15_emisoras_bmv.csv"
OUTPUT_REPORTE_JSON = WORKSPACE / "reporte_cobertura_y_huecos_15_emisoras.json"

# Las 15 empresas del IPC acordadas
# Formato: (ticker, serie_actual, sector, anillo, series_validas_historicas)
EMISORAS_15_DEF = [
    ("GMEXICO", "B", "Minería y materiales", "Plata", ["B"]),
    ("GFNORTE", "O", "Banca y servicios financieros", "Plata", ["O"]),
    ("FEMSA", "UBD", "Consumo y comercio", "Bronce", ["UBD"]),
    ("AMX", "B", "Telecomunicaciones", "Bronce", ["B", "L"]),  # Unificacion corporativa marzo 2023
    ("WALMEX", "*", "Comercio y autoservicio", "Oro", ["*"]),
    ("CEMEX", "CPO", "Cemento y construcción", "Bronce", ["CPO"]),
    ("PE&OLES", "*", "Minería y metales", "Bronce", ["*"]),
    ("GAP", "B", "Infraestructura aeroportuaria", "Bronce", ["B"]),
    ("AC", "*", "Bebidas y consumo", "Bronce", ["*"]),
    ("ASUR", "B", "Infraestructura aeroportuaria", "Bronce", ["B"]),
    ("BIMBO", "A", "Industria alimentaria", "Bronce", ["A"]),
    ("GFINBUR", "O", "Servicios financieros", "Bronce", ["O"]),
    ("VESTA", "*", "Inmuebles industriales", "Bronce", ["*"]),
    ("LIVEPOL", "C-1", "Comercio departamental", "Bronce", ["C-1", "C 1", "C1"]),
    ("GRUMA", "B", "Industria alimentaria", "Bronce", ["B"]),
]


def load_master_date_grid():
    """Carga las 2,515 fechas oficiales de la rejilla heredada (9C + 9G + 2026-10-28)."""
    with zipfile.ZipFile(Z9C) as z:
        df_9c = pd.read_csv(io.BytesIO(z.read("datos/WALMEX_cierre_PPP_BMV_uniforme.csv")))
    with zipfile.ZipFile(Z9G) as z:
        df_9g = pd.read_csv(io.BytesIO(z.read("datos/WALMEX_PPP_BMV_periodo_final.csv")))

    # Ground truth de WALMEX para validacion
    walmex_gt_9c = dict(zip(df_9c["fecha"], df_9c["Close_PPP_BMV"]))
    walmex_gt_9g = dict(zip(df_9g["fecha"], df_9g["Close_PPP_BMV"]))
    walmex_ground_truth = {**walmex_gt_9c, **walmex_gt_9g}
    walmex_ground_truth["2026-10-28"] = 48.40  # Auditado en etapa 10

    all_dates = sorted(list(set(df_9c["fecha"]).union(set(df_9g["fecha"])).union({"2026-10-28"})))
    return all_dates, walmex_ground_truth


def fetch_bulletin_cached(fecha_str: str, max_retries: int = 3) -> tuple:
    """
    Obtiene el boletin de la BMV. Si esta en cache local lo lee de disco;
    si no, lo descarga via HTTP con reintentos y lo guarda en cache.
    Retorna (fecha_str, raw_bytes, sha256_hex, url, error_msg).
    """
    yyyymmdd = fecha_str.replace("-", "")
    cache_file = CACHE_DIR / f"boletin_{yyyymmdd}.html"
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{yyyymmdd}.html"

    if cache_file.exists():
        raw = cache_file.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        return fecha_str, raw, sha, url, None

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PrismaBMV-Extractor/2.0"},
    )
    last_err = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                raw = response.read()
            sha = hashlib.sha256(raw).hexdigest()
            cache_file.write_bytes(raw)
            return fecha_str, raw, sha, url, None
        except Exception as e:
            last_err = str(e)
            time.sleep(0.4 * (attempt + 1))

    return fecha_str, b"", "", url, f"Error tras {max_retries} intentos: {last_err}"


def parse_bulletin_quotes(raw_html_bytes: bytes) -> dict:
    """
    Parsea de forma estricta los precios oficiales del boletin HTML de la BMV.
    Filtra UNICAMENTE las tablas de cotizacion bursatil:
      - 'Mayor Variación a la Alza'
      - 'Mayor Variación a la Baja'
      - 'Más Negociadas'
    y EXCLUYE 'Paquetes Negociados' e indices generales.
    Verifica que la columna PPP este presente y sea un precio positivo autentico.
    """
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

                # Si la fila tiene menos columnas que el encabezado (por ejemplo 9 en vez de 10, o 6 en vez de 7),
                # la BMV omitio la columna PPP en esa fecha particular.
                if expected_cols > 0 and len(clean) < expected_cols:
                    continue

                try:
                    ult = float(clean[2].replace(",", ""))
                    ant = float(clean[3].replace(",", ""))
                    candidate_ppp = float(clean[4].replace(",", ""))

                    # Regla estricta de precio:
                    # 1. Un precio bursatil jamas es negativo ni cero
                    if candidate_ppp <= 0:
                        continue
                    # 2. Si candidate_ppp coincide con la variacion porcentual teorica, es la columna Var %
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


def extract_all_15_issuers(all_dates, max_workers=14):
    """
    Descarga (con cache) y extrae las cotizaciones de las 15 emisoras para todas las fechas.
    """
    print(f"Iniciando lectura y parseo de {len(all_dates)} boletines oficiales BMV...")
    t0 = time.time()
    extracted_data = {}

    completed_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(fetch_bulletin_cached, d): d for d in all_dates}
        for future in as_completed(future_map):
            fecha_str, raw, sha, url, err = future.result()
            completed_count += 1
            if completed_count % 500 == 0 or completed_count == len(all_dates):
                elapsed = time.time() - t0
                rate = completed_count / elapsed if elapsed > 0 else 0
                print(f"  Progreso: {completed_count}/{len(all_dates)} boletines ({rate:.1f} bol/s)...")

            if raw:
                quotes = parse_bulletin_quotes(raw)
                extracted_data[fecha_str] = {
                    "sha256": sha,
                    "url": url,
                    "quotes": quotes,
                    "error": None,
                }
            else:
                extracted_data[fecha_str] = {
                    "sha256": "",
                    "url": url,
                    "quotes": {},
                    "error": err,
                }

    t1 = time.time()
    print(f"Lectura y parseo completados en {t1-t0:.2f} segundos.")
    return extracted_data


def build_tidy_dataset(all_dates, extracted_data):
    """
    Construye el DataFrame ordenado en formato panel largo para las 15 empresas.
    Conserva los huecos documentados de forma explicita (sin forward-fill, sin ceros).
    """
    rows = []
    for pos, fecha_str in enumerate(all_dates):
        day_info = extracted_data.get(fecha_str, {})
        day_quotes = day_info.get("quotes", {})
        sha = day_info.get("sha256", "")
        url = day_info.get("url", "")
        err = day_info.get("error", None)

        for ticker, serie_oficial, sector, anillo, series_validas in EMISORAS_15_DEF:
            match_quote = None
            serie_encontrada = serie_oficial
            for s_val in series_validas:
                if (ticker, s_val) in day_quotes:
                    match_quote = day_quotes[(ticker, s_val)]
                    serie_encontrada = s_val
                    break

            if match_quote is not None:
                rows.append({
                    "fecha": fecha_str,
                    "posicion_sesion": pos,
                    "emisora": ticker,
                    "serie": serie_encontrada,
                    "sector_economico": sector,
                    "anillo_madurez": anillo,
                    "estado_captura": "PPP_PUBLICADO_VERIFICADO",
                    "ppp_bmv_mxn": match_quote["ppp"],
                    "ultimo_bmv_mxn": match_quote["ultimo"],
                    "anterior_bmv_mxn": match_quote["anterior"],
                    "variacion_ppp_vs_anterior_pct": match_quote["variacion_ppp_vs_anterior_pct"],
                    "evidencia_exacta": f"{ticker} / {serie_encontrada} / PPP / {match_quote['ppp']}",
                    "sha256_boletin": sha,
                    "url_fuente": url,
                })
            else:
                estado = "BOLETIN_NO_DISPONIBLE_HTTP" if err else "NO_PUBLICADO_EN_BOLETIN_RSS_DEL_DIA"
                rows.append({
                    "fecha": fecha_str,
                    "posicion_sesion": pos,
                    "emisora": ticker,
                    "serie": serie_oficial,
                    "sector_economico": sector,
                    "anillo_madurez": anillo,
                    "estado_captura": estado,
                    "ppp_bmv_mxn": np.nan,
                    "ultimo_bmv_mxn": np.nan,
                    "anterior_bmv_mxn": np.nan,
                    "variacion_ppp_vs_anterior_pct": np.nan,
                    "evidencia_exacta": "Emisora ausente de las tablas del boletin RSS; hueco documental conservado",
                    "sha256_boletin": sha,
                    "url_fuente": url,
                })

    df = pd.DataFrame(rows)
    df = df.sort_values(["posicion_sesion", "emisora"]).reset_index(drop=True)
    return df


def validate_against_walmex_ground_truth(df, walmex_gt):
    """
    Compara fila a fila cada PPP de WALMEX con el ground truth auditado en 9C y 9G.
    """
    w_df = df[df["emisora"] == "WALMEX"].copy()
    diffs = []
    comparaciones_validas = 0
    huecos_coincidentes = 0
    discrepancias = []

    for _, row in w_df.iterrows():
        f = row["fecha"]
        p_scraped = row["ppp_bmv_mxn"]
        p_gt = walmex_gt.get(f)

        if pd.isna(p_scraped) and (p_gt is None or pd.isna(p_gt)):
            huecos_coincidentes += 1
        elif pd.notna(p_scraped) and pd.notna(p_gt):
            diff = abs(p_scraped - p_gt)
            diffs.append(diff)
            comparaciones_validas += 1
            if diff > 0.001:
                discrepancias.append((f, p_scraped, p_gt, diff))
        else:
            discrepancias.append((f, p_scraped, p_gt, "Mismatch presencia"))

    max_diff = max(diffs) if diffs else 0.0
    return {
        "total_sesiones_walmex": len(w_df),
        "comparaciones_validas": comparaciones_validas,
        "huecos_coincidentes": huecos_coincidentes,
        "max_discrepancia_mxn": round(float(max_diff), 6),
        "total_discrepancias_mayores_un_milavo": len(discrepancias),
        "discrepancias_detalle": discrepancias[:5],
    }


def generate_coverage_report(df, all_dates):
    """
    Calcula estadisticas de cobertura y huecos para cada una de las 15 emisoras.
    """
    total_dates = len(all_dates)
    report = {
        "periodo_historico": {
            "fecha_inicio": all_dates[0],
            "fecha_fin": all_dates[-1],
            "total_sesiones_rejilla": total_dates,
        },
        "emisoras": {},
    }

    for ticker, serie, sector, anillo, _ in EMISORAS_15_DEF:
        sub = df[df["emisora"] == ticker]
        validos = sub[sub["estado_captura"] == "PPP_PUBLICADO_VERIFICADO"]
        n_validos = len(validos)
        n_huecos = total_dates - n_validos
        pct_cobertura = round(n_validos / total_dates * 100.0, 2)
        pct_huecos = round(n_huecos / total_dates * 100.0, 2)

        min_p = float(validos["ppp_bmv_mxn"].min()) if n_validos > 0 else np.nan
        max_p = float(validos["ppp_bmv_mxn"].max()) if n_validos > 0 else np.nan
        ultimo_p = float(validos.iloc[-1]["ppp_bmv_mxn"]) if n_validos > 0 else np.nan
        primera_fecha = str(validos.iloc[0]["fecha"]) if n_validos > 0 else "N/A"
        ultima_fecha = str(validos.iloc[-1]["fecha"]) if n_validos > 0 else "N/A"

        report["emisoras"][ticker] = {
            "ticker": ticker,
            "serie_oficial": serie,
            "sector": sector,
            "anillo": anillo,
            "sesiones_publicadas": n_validos,
            "huecos_documentados": n_huecos,
            "porcentaje_cobertura": pct_cobertura,
            "porcentaje_huecos": pct_huecos,
            "precio_minimo_mxn": min_p,
            "precio_maximo_mxn": max_p,
            "ultimo_ppp_mxn": ultimo_p,
            "primera_fecha_verificada": primera_fecha,
            "ultima_fecha_verificada": ultima_fecha,
        }

    return report


def main():
    print("=" * 70)
    print("PRISMA BMV - RECONSTRUCCION OFICIAL MULTI-EMISORA (15 EMPRESAS IPC)")
    print("=" * 70)

    # 1. Cargar rejilla oficial
    all_dates, walmex_gt = load_master_date_grid()
    print(f"Rejilla oficial cargada: {len(all_dates)} sesiones ({all_dates[0]} a {all_dates[-1]}).")

    # 2. Parsear boletines (usando cache local)
    extracted_data = extract_all_15_issuers(all_dates, max_workers=14)

    # 3. Construir dataset panel largo
    print("\nConstruyendo dataset panel de precios...")
    df_panel = build_tidy_dataset(all_dates, extracted_data)
    print(f"Dataset construido: {df_panel.shape[0]} filas ({len(all_dates)} fechas x 15 empresas).")

    # 4. Validar WALMEX contra Ground Truth
    print("\nValidando WALMEX contra Ground Truth oficial (9C + 9G)...")
    val_walmex = validate_against_walmex_ground_truth(df_panel, walmex_gt)
    print(f"  Total comparaciones validas: {val_walmex['comparaciones_validas']}")
    print(f"  Huecos coincidentes: {val_walmex['huecos_coincidentes']}")
    print(f"  Discrepancia maxima: ${val_walmex['max_discrepancia_mxn']} MXN")
    print(f"  Discrepancias > $0.001: {val_walmex['total_discrepancias_mayores_un_milavo']}")
    if val_walmex["total_discrepancias_mayores_un_milavo"] == 0:
        print("  -> VALIDACION WALMEX: PERFECTA (0.00 MXN de diferencia en toda la serie de 10 anos).")
    else:
        print(f"  -> ADVERTENCIA: {val_walmex['discrepancias_detalle']}")

    # 5. Generar reporte de cobertura
    print("\nGenerando reporte de cobertura y huecos para las 15 empresas...")
    reporte = generate_coverage_report(df_panel, all_dates)
    reporte["validacion_walmex"] = val_walmex

    # 6. Guardar salidas
    df_panel.to_csv(OUTPUT_SERIE_CSV, index=False, encoding="utf-8-sig")
    print(f"Guardado: {OUTPUT_SERIE_CSV} ({OUTPUT_SERIE_CSV.stat().st_size} bytes)")

    with open(OUTPUT_REPORTE_JSON, "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)
    print(f"Guardado: {OUTPUT_REPORTE_JSON}")

    print("\n" + "=" * 70)
    print("RESUMEN DE COBERTURA HISTORICA BMV (VERTICAL):")
    print("=" * 70)
    for ticker, info in reporte["emisoras"].items():
        print(f"* {info['ticker']} ({info['serie_oficial']}) - {info['sector']} [Anillo {info['anillo']}]:")
        print(f"    - Sesiones con PPP publicado: {info['sesiones_publicadas']} / {len(all_dates)} ({info['porcentaje_cobertura']}%)")
        print(f"    - Huecos documentados: {info['huecos_documentados']} ({info['porcentaje_huecos']}%)")
        print(f"    - Rango de precios: ${info['precio_minimo_mxn']:.2f} a ${info['precio_maximo_mxn']:.2f} MXN (Ultimo: ${info['ultimo_ppp_mxn']:.2f})")
        print(f"    - Ventana temporal: {info['primera_fecha_verificada']} a {info['ultima_fecha_verificada']}")


if __name__ == "__main__":
    main()
