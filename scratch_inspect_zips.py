import zipfile, pandas as pd, io
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # carpeta del proyecto

zpath = ROOT / "Prisma_BMV_Datos.zip"
with zipfile.ZipFile(zpath, 'r') as z:
    for name in z.namelist():
        df = pd.read_csv(io.BytesIO(z.read(name)))
        print(f"=== {name} ===")
        print(f"Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print(f"Date range: {df['Date'].min() if 'Date' in df.columns else (df['fecha'].min() if 'fecha' in df.columns else 'N/A')} to {df['Date'].max() if 'Date' in df.columns else (df['fecha'].max() if 'fecha' in df.columns else 'N/A')}")
        print(df.head(2))
