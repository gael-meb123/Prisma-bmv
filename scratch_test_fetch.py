import urllib.request
import re
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import zipfile
import io

# Load ground truth dates from 9C and 9G
z9c = r'D:\Universidad\7mo Semestre\Big Data\Parcial 3\Prisma_BMV_Etapa9C_WALMEX_Cierre_Uniforme.zip'
z9g = r'D:\Universidad\7mo Semestre\Big Data\Parcial 3\Prisma_BMV_Etapa9G_Insumos_Prueba_Final_CORREGIDO.zip'

with zipfile.ZipFile(z9c) as z:
    df_9c = pd.read_csv(io.BytesIO(z.read('datos/WALMEX_cierre_PPP_BMV_uniforme.csv')))
with zipfile.ZipFile(z9g) as z:
    df_9g = pd.read_csv(io.BytesIO(z.read('datos/WALMEX_PPP_BMV_periodo_final.csv')))

all_dates = sorted(list(set(df_9c['fecha']).union(set(df_9g['fecha'])).union({'2026-10-28'})))
print(f"Total dates in official grid: {len(all_dates)}")

# Let's test a sample of 20 dates across the 10 years
sample_dates = all_dates[::125]  # ~21 dates spread across 2016-2026
print(f"Testing {len(sample_dates)} dates: {sample_dates[0]} to {sample_dates[-1]}")

def fetch_and_parse(f_str):
    d_yyyymmdd = f_str.replace('-', '')
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{d_yyyymmdd}.html"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 PrismaBMV/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
        sha = hashlib.sha256(raw).hexdigest()
        html_txt = raw.decode('utf-8', errors='ignore')
        
        # Check tables 5, 6, 7 (Alza, Baja, Negociadas)
        # Parse all rows in tables
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html_txt, flags=re.DOTALL | re.IGNORECASE)
        found = {}
        for r in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL | re.IGNORECASE)
            clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
            clean = [re.sub(r'\s+', ' ', td) for td in clean if td]
            if len(clean) >= 5:
                tk = clean[0]
                serie = clean[1]
                # Check if tk is in our targets
                if tk in ['WALMEX', 'GMEXICO', 'GFNORTE', 'FEMSA', 'AMX', 'CEMEX', 'PE&OLES', 'GAP', 'AC', 'ASUR', 'BIMBO', 'GFINBUR', 'VESTA', 'LIVEPOL', 'GRUMA']:
                    try:
                        ult = float(clean[2].replace(',', ''))
                        ant = float(clean[3].replace(',', ''))
                        ppp = float(clean[4].replace(',', ''))
                        if tk not in found:
                            found[tk] = {'serie': serie, 'ultimo': ult, 'anterior': ant, 'ppp': ppp}
                    except:
                        pass
        return f_str, True, len(raw), sha, found, None
    except Exception as e:
        return f_str, False, 0, '', {}, str(e)

t0 = time.time()
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = [ex.submit(fetch_and_parse, d) for d in sample_dates]
    results = [f.result() for f in futs]

t1 = time.time()
print(f"Completed {len(results)} fetches in {t1-t0:.2f}s ({len(results)/(t1-t0):.1f} req/s)")

# Check WALMEX ground truth match on these dates
walmex_gt = dict(zip(df_9c['fecha'], df_9c['Close_PPP_BMV']))
walmex_gt.update(dict(zip(df_9g['fecha'], df_9g['Close_PPP_BMV'])))

matches = 0
for f_str, success, sz, sha, found, err in results:
    if success:
        w_res = found.get('WALMEX', {}).get('ppp')
        w_gt = walmex_gt.get(f_str)
        diff = abs(w_res - w_gt) if (w_res is not None and pd.notna(w_gt)) else None
        print(f"Date {f_str}: Found {len(found)} issuers | WALMEX scraped={w_res}, GT={w_gt}, diff={diff}")
        if diff is not None and diff < 1e-4:
            matches += 1
    else:
        print(f"Date {f_str}: ERROR {err}")

print(f"WALMEX exact matches: {matches} / {len(results)}")
