import urllib.request, re
from pathlib import Path

# Let's inspect boletin_20240820.html and 20170919.html in cache!
ROOT = Path(__file__).resolve().parent          # carpeta del proyecto

cache_dir = ROOT / "cache_boletines"
cache_dir.mkdir(exist_ok=True)
for dt in ['20240820', '20170919']:
    f = cache_dir / f"boletin_{dt}.html"
    if f.exists():
        raw = f.read_bytes().decode('utf-8', errors='ignore')
        # Find tables
        tables = re.findall(r'<table[^>]*>(.*?)</table>', raw, flags=re.DOTALL | re.IGNORECASE)
        print(f"=== Date {dt}: {len(tables)} tables ===")
        for idx, tbl in enumerate(tables):
            header = re.sub(r'<[^>]+>', ' ', tbl[:300])
            if any(k in header for k in ['Negociadas', 'Variac', 'Alza', 'Baja']):
                print(f"  Table {idx}: {header[:60].strip()}")
                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, flags=re.DOTALL | re.IGNORECASE)
                for r in rows:
                    tds = [re.sub(r'<[^>]+>', '', td).strip() for td in re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL | re.IGNORECASE)]
                    tds = [re.sub(r'\s+', ' ', td) for td in tds if td]
                    if len(tds) >= 4 and any(t in tds for t in ['WALMEX', 'GMEXICO', 'FEMSA', 'AMX']):
                        print(f"    Row: {tds}")
