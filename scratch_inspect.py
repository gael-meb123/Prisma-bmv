import urllib.request
import re

url = 'https://www.bmv.com.mx/docs-pub/rss/boletin20240220.html'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 PrismaBMV/1.0'})
raw = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')

# Print all table tags and classes/widths
print("File length:", len(raw))

# Find all occurrences of <table>
tables = re.findall(r'<table[^>]*>(.*?)</table>', raw, flags=re.DOTALL | re.IGNORECASE)
print(f"Total tables: {len(tables)}")

for idx, tbl in enumerate(tables):
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, flags=re.DOTALL | re.IGNORECASE)
    print(f"\n--- Table {idx}: {len(rows)} rows ---")
    for r in rows[:4]:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL | re.IGNORECASE)
        clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
        clean = [c for c in clean if c]
        if clean:
            print("   Row:", clean[:6])
