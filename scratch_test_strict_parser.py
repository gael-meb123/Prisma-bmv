import urllib.request, re, html

def parse_bulletin_strictly(raw_html):
    # Find all tables
    tables = re.findall(r'<table[^>]*>(.*?)</table>', raw_html, flags=re.DOTALL | re.IGNORECASE)
    quotes = {}
    for tbl in tables:
        # Check if table is Alza, Baja, or Negociadas
        header_text = re.sub(r'<[^>]+>', ' ', tbl[:300])
        is_quote_table = (
            ('Negociadas' in header_text or 'Variac' in header_text or 'Alza' in header_text or 'Baja' in header_text)
            and 'Paquetes' not in header_text
        )
        if not is_quote_table:
            continue
            
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, flags=re.DOTALL | re.IGNORECASE)
        for r in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL | re.IGNORECASE)
            clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
            clean = [re.sub(r'\s+', ' ', td) for td in clean if td]
            if len(clean) >= 5:
                tk = clean[0]
                sr = clean[1]
                try:
                    ult = float(clean[2].replace(',', ''))
                    ant = float(clean[3].replace(',', ''))
                    ppp = float(clean[4].replace(',', ''))
                    # Store quote
                    k = (tk, sr)
                    if k not in quotes:
                        quotes[k] = {'ultimo': ult, 'anterior': ant, 'ppp': ppp}
                except:
                    pass
    return quotes

# Test on 20221101 where AMX had Paquetes
url = "https://www.bmv.com.mx/docs-pub/rss/boletin20221101.html"
raw = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 PrismaBMV/1.0'})).read().decode('utf-8', errors='ignore')
quotes = parse_bulletin_strictly(raw)

print("Quotes on 2022-11-01:")
for (tk, sr), q in sorted(quotes.items()):
    if tk in ['AMX', 'WALMEX', 'GFNORTE', 'GMEXICO', 'FEMSA']:
        print(f"  {tk} {sr}: PPP = {q['ppp']} | Ultimo = {q['ultimo']} | Anterior = {q['anterior']}")
