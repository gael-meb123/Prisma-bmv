import urllib.request, re

url = "https://www.bmv.com.mx/docs-pub/rss/boletin20221101.html"
raw = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 PrismaBMV/1.0'})).read().decode('utf-8', errors='ignore')

tables = re.findall(r'<table[^>]*>(.*?)</table>', raw, flags=re.DOTALL | re.IGNORECASE)
for idx, tbl in enumerate(tables):
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, flags=re.DOTALL | re.IGNORECASE)
    txt = re.sub(r'<[^>]+>', ' ', tbl[:300])
    print(f"Table {idx} (rows: {len(rows)}): snippet: {txt[:120].strip()}")
