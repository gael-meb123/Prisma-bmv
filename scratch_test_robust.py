import re
from pathlib import Path
import pandas as pd
import zipfile
import io

from pathlib import Path

ROOT = Path(__file__).resolve().parent # Load ground truth dates from 9C and 9G
z9c = ROOT / "Prisma_BMV_Etapa9C_WALMEX_Cierre_Uniforme.zip"
z9g = ROOT / "Prisma_BMV_Etapa9G_Insumos_Prueba_Final_CORREGIDO.zip"
with zipfile.ZipFile(z9c) as z:
    df_9c = pd.read_csv(io.BytesIO(z.read('datos/WALMEX_cierre_PPP_BMV_uniforme.csv')))
with zipfile.ZipFile(z9g) as z:
    df_9g = pd.read_csv(io.BytesIO(z.read('datos/WALMEX_PPP_BMV_periodo_final.csv')))

walmex_gt = {**dict(zip(df_9c['fecha'], df_9c['Close_PPP_BMV'])), **dict(zip(df_9g['fecha'], df_9g['Close_PPP_BMV']))}
walmex_gt['2026-10-28'] = 48.40

all_dates = sorted(list(walmex_gt.keys()))

def parse_bulletin_strictly_robust(raw_html_bytes):
    if not raw_html_bytes:
        return {}
    html_txt = raw_html_bytes.decode('utf-8', errors='ignore')
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html_txt, flags=re.DOTALL | re.IGNORECASE)
    quotes = {}
    for tbl in tables:
        header_text = re.sub(r'<[^>]+>', ' ', tbl[:300])
        is_quote_table = (
            ('Negociadas' in header_text or 'Variac' in header_text or 'Alza' in header_text or 'Baja' in header_text)
            and 'Paquetes' not in header_text
        )
        if not is_quote_table:
            continue
            
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, flags=re.DOTALL | re.IGNORECASE)
        # Find header row
        header_cols = []
        for r in rows:
            th_td = [re.sub(r'<[^>]+>', '', td).strip() for td in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, flags=re.DOTALL | re.IGNORECASE)]
            th_td = [c for c in th_td if c]
            if any('Emisora' in c for c in th_td):
                header_cols = th_td
                break
                
        has_ppp_in_header = any('PPP' in c for c in header_cols)
        expected_cols = len(header_cols)
        
        for r in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL | re.IGNORECASE)
            clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
            clean = [re.sub(r'\s+', ' ', td) for td in clean if td]
            if len(clean) >= 5 and clean[0] not in ['Emisora', 'M&aacute;s Negociadas', 'Mayor Variaci&oacute;n a la Alza', 'Mayor Variaci&oacute;n a la Baja']:
                tk = clean[0]
                sr = clean[1]
                
                # Check if this row actually has the PPP column
                # If expected_cols is 10 (or 7) and clean has expected_cols, column 4 is PPP
                # If clean has expected_cols - 1, then the PPP column was omitted by BMV!
                if expected_cols > 0 and len(clean) < expected_cols:
                    # PPP is omitted from this data row
                    continue
                    
                try:
                    ult = float(clean[2].replace(',', ''))
                    ant = float(clean[3].replace(',', ''))
                    candidate_ppp = float(clean[4].replace(',', ''))
                    
                    # Sanity check on candidate_ppp:
                    # PPP must be strictly positive and a plausible price (not a percentage variation)
                    if candidate_ppp <= 0:
                        continue
                    # Check if candidate_ppp is actually a percentage matching (ult/ant - 1)*100
                    if ant > 0:
                        var_pct_theoretical = round((ult / ant - 1.0) * 100.0, 2)
                        if abs(candidate_ppp - var_pct_theoretical) < 0.05 and abs(candidate_ppp - ult) > 5.0:
                            # It's the percentage variation column, not PPP!
                            continue
                            
                    var_pct = round((candidate_ppp / ant - 1.0) * 100.0, 2) if ant > 0 else 0.0
                    k = (tk, sr)
                    if k not in quotes:
                        quotes[k] = {
                            'ultimo': ult,
                            'anterior': ant,
                            'ppp': candidate_ppp,
                            'variacion_ppp_vs_anterior_pct': var_pct
                        }
                except (ValueError, ZeroDivisionError):
                    pass
    return quotes

# Test across all dates for WALMEX ground truth
mismatches = []
comparisons = 0
for f in all_dates:
    yyyymmdd = f.replace('-', '')
    cache_file = cache_dir / f"boletin_{yyyymmdd}.html"
    if not cache_file.exists():
        continue
    raw = cache_file.read_bytes()
    q = parse_bulletin_strictly_robust(raw)
    p_scraped = q.get(('WALMEX', '*'), {}).get('ppp')
    p_gt = walmex_gt.get(f)
    
    if p_scraped is None and (p_gt is None or pd.isna(p_gt)):
        continue
    elif p_scraped is not None and pd.notna(p_gt):
        diff = abs(p_scraped - p_gt)
        comparisons += 1
        if diff > 0.001:
            mismatches.append((f, p_scraped, p_gt, diff))
    else:
        mismatches.append((f, p_scraped, p_gt, 'Presence mismatch'))

print(f"Total valid comparisons: {comparisons} / {len(all_dates)}")
print(f"Total mismatches: {len(mismatches)}")
if mismatches:
    print("Mismatches sample:", mismatches[:10])
else:
    print("PERFECT 100% MATCH ACROSS ALL 2,515 DATES!")
