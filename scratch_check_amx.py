import urllib.request, re

dates = ['20161027', '20180430', '20201021', '20220420', '20221101', '20230417', '20240415', '20261028']
for dt in dates:
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{dt}.html"
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 PrismaBMV/1.0'})).read().decode('utf-8', errors='ignore')
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', raw, flags=re.DOTALL | re.IGNORECASE)
    amx_rows = []
    for r in rows:
        tds = [re.sub(r'<[^>]+>', '', td).strip() for td in re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL | re.IGNORECASE)]
        tds = [re.sub(r'\s+', ' ', td) for td in tds if td]
        if len(tds) >= 5 and tds[0] == 'AMX':
            amx_rows.append((tds[0], tds[1], tds[4]))
    print(f"{dt}: AMX entries = {amx_rows}")
