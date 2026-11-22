"""Empaqueta solo el código de captura provisional; no despliega ni modifica AWS."""
import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVOS = {
    "handler.py": "infra/lambda/captura_ampliada_aislada/handler.py",
    "prisma/__init__.py": "prisma/__init__.py",
    "prisma/data/__init__.py": "prisma/data/__init__.py",
    "prisma/data/captura_ampliada.py": "prisma/data/captura_ampliada.py",
    "prisma/domain/__init__.py": "prisma/domain/__init__.py",
    "prisma/domain/catalogo_ipc.py": "prisma/domain/catalogo_ipc.py",
    "prisma/domain/catalogos/naftrac_2026-11-17_v1.json": "prisma/domain/catalogos/naftrac_2026-11-17_v1.json",
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    destino = Path(a.salida)
    with destino.open("xb") as archivo:
        with zipfile.ZipFile(archivo, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for nombre, ruta in ARCHIVOS.items():
                z.writestr(nombre, (ROOT / ruta).read_bytes())
    print(f"ZIP: {destino}")
    print(f"SHA-256: {hashlib.sha256(destino.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
