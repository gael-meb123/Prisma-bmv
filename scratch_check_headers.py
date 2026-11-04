import re
from pathlib import Path

cache_dir = Path(r"D:\Universidad\7mo Semestre\Big Data\Proyecto final\cache_boletines")

for dt in ['20161027', '20170919', '20240820', '20261028']:
    f = cache_dir / f"boletin_{dt}.html"
    raw = f.read_bytes().decode('utf-8', errors='ignore')
    tables = re.findall(r'<table[^>]*>(.*?)</table>', raw, flags=re.DOTALL | re.IGNORECASE)
    for idx, tbl in enumerate(tables):
        if 'Negociadas' in tbl:
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, flags=re.DOTALL | re.IGNORECASE)
            print(f"\n=== Date {dt} Table {idx}: {len(rows)} rows ===")
            for r in rows[:3]:
                clean_r = [re.sub(r'<[^>]+>', '', col).strip() for col in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, flags=re.DOTALL | re.IGNORECASE)]
                clean_r = [c for c in clean_r if c]
                print("  ", clean_r)
