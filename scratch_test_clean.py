import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent          # carpeta del proyecto

cache_dir = ROOT / "cache_boletines"
cache_dir.mkdir(exist_ok=True)
def parse_bulletin_quotes_updated(raw_html_bytes: bytes) -> dict:
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
                # BMV omitio la columna PPP en esa fecha
                if expected_cols > 0 and len(clean) < expected_cols:
                    continue

                try:
                    ult = float(clean[2].replace(",", ""))
                    ant = float(clean[3].replace(",", ""))
                    candidate_ppp = float(clean[4].replace(",", ""))

                    # Validaciones estrictas de precio PPP:
                    # 1. Un precio bursatil jamas es negativo ni cero
                    if candidate_ppp <= 0:
                        continue
                    # 2. Si candidate_ppp coincide con la variacion porcentual teorica ((ult/ant - 1)*100),
                    # significa que se desplazo la columna y no es precio
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

for dt in ['20161027', '20170919', '20240820', '20261028']:
    raw = (cache_dir / f"boletin_{dt}.html").read_bytes()
    q = parse_bulletin_quotes_updated(raw)
    walmex_entry = q.get(('WALMEX', '*'))
    gmexico_entry = q.get(('GMEXICO', 'B'))
    print(f"Date {dt}:")
    print(f"  WALMEX *: {walmex_entry}")
    print(f"  GMEXICO B: {gmexico_entry}")
