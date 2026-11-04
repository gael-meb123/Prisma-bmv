import urllib.request
import re
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import zipfile
import io

z9c = r'D:\Universidad\7mo Semestre\Big Data\Parcial 3\Prisma_BMV_Etapa9C_WALMEX_Cierre_Uniforme.zip'
z9g = r'D:\Universidad\7mo Semestre\Big Data\Parcial 3\Prisma_BMV_Etapa9G_Insumos_Prueba_Final_CORREGIDO.zip'

with zipfile.ZipFile(z9c) as z:
    df_9c = pd.read_csv(io.BytesIO(z.read('datos/WALMEX_cierre_PPP_BMV_uniforme.csv')))
with zipfile.ZipFile(z9g) as z:
    df_9g = pd.read_csv(io.BytesIO(z.read('datos/WALMEX_PPP_BMV_periodo_final.csv')))

all_dates = sorted(list(set(df_9c['fecha']).union(set(df_9g['fecha'])).union({'2026-10-28'})))
sample_dates = all_dates[::125]

def fetch_and_parse(f_str):
    d_yyyymmdd = f_str.replace('-', '')
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{d_yyyymmdd}.html"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 PrismaBMV/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
        sha = hashlib.sha256(raw).hexdigest()
        html_txt = raw.decode('utf-8', errors='ignore')
        
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html_txt, flags=re.DOTALL | re.IGNORECASE)
        found = {}
        for r in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL | re.IGNORECASE)
            clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
            clean = [re.sub(r'\s+', ' ', td) for td in clean if td]
            if len(clean) >= 5:
                tk = clean[0]
                serie = clean[1]
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

with ThreadPoolExecutor(max_workers=8) as ex:
    futs = [ex.submit(fetch_and_parse, d) for d in sample_dates]
    results = [f.result() for f in futs]

counts = {}
for _, success, _, _, found, _ in results:
    if success:
        for tk in found:
            counts[tk] = counts.get(tk, 0) + 1

print("Issuer appearance frequency across 21 sample dates:")
for tk, c in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {tk}: {c} / {len(results)} ({c/len(results)*100:.1f}%)")
