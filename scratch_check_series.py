import urllib.request, re
from collections import defaultdict

# Let's inspect ticker and serie combinations found across our sample
url_dates = ['20161027', '20180430', '20201021', '20220420', '20240415', '20261028']
series_found = defaultdict(set)

for dt in url_dates:
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{dt}.html"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 PrismaBMV/1.0'})
    raw = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', raw, flags=re.DOTALL | re.IGNORECASE)
    for r in rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL | re.IGNORECASE)
        clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
        clean = [re.sub(r'\s+', ' ', td) for td in clean if td]
        if len(clean) >= 5:
            tk = clean[0]
            serie = clean[1]
            if tk in ['WALMEX', 'GMEXICO', 'GFNORTE', 'FEMSA', 'AMX', 'CEMEX', 'PE&OLES', 'GAP', 'AC', 'ASUR', 'BIMBO', 'GFINBUR', 'VESTA', 'LIVEPOL', 'GRUMA']:
                series_found[tk].add(serie)

print("Series found for each ticker:")
for tk, sers in sorted(series_found.items()):
    print(f"  {tk}: {sers}")
