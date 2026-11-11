import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # carpeta del proyecto

cache_dir = ROOT / "cache_boletines"
cache_dir.mkdir(exist_ok=True)
# Let's inspect 20240820 and 20170919 table structure in raw HTML
for dt in ['20170919', '20240820']:
    f = cache_dir / f"boletin_{dt}.html"
    raw = f.read_bytes().decode('utf-8', errors='ignore')
    tables = re.findall(r'<table[^>]*>(.*?)</table>', raw, flags=re.DOTALL | re.IGNORECASE)
    for idx, tbl in enumerate(tables):
        if 'Negociadas' in tbl or 'Variac' in tbl:
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, flags=re.DOTALL | re.IGNORECASE)
            print(f"=== Date {dt} Table {idx} ===")
            for r in rows:
                cols = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, flags=re.DOTALL | re.IGNORECASE)]
                cols = [c for c in cols if c]
                if any(t in cols for t in ['WALMEX', 'GMEXICO']) or any('Emisora' in c for c in cols):
                    print("  Row:", cols)
