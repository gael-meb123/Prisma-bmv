import urllib.request, re

test_dates = ['20230301', '20230315', '20230331', '20230403', '20230410', '20230417']
for dt in test_dates:
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{dt}.html"
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 PrismaBMV/1.0'})).read().decode('utf-8', errors='ignore')
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', raw, flags=re.DOTALL | re.IGNORECASE)
        amx_entries = set()
        for r in rows:
            tds = [re.sub(r'<[^>]+>', '', td).strip() for td in re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL | re.IGNORECASE)]
            tds = [re.sub(r'\s+', ' ', td) for td in tds if td]
            if len(tds) >= 5 and tds[0] == 'AMX':
                amx_entries.add((tds[0], tds[1], tds[4]))
        print(f"{dt}: {amx_entries}")
    except Exception as e:
        print(f"{dt}: ERROR {e}")
