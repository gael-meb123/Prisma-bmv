"""Empaqueta la guardia aislada con entradas explícitas y reproducibles."""
import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", required=True, type=Path)
    args = p.parse_args()
    archivos = {
        "handler.py": ROOT / "infra/lambda/guardia_senales/handler.py",
        "capturas_seguras.py": ROOT / "infra/capturas_seguras.py",
        "elegibilidad_senales.py": ROOT / "prisma/domain/elegibilidad_senales.py",
        "auditar_boletin_diario.py": ROOT / "scripts/auditar_boletin_diario.py",
        "prisma/__init__.py": ROOT / "prisma/__init__.py",
        "prisma/data/__init__.py": ROOT / "prisma/data/__init__.py",
        "prisma/data/captura_ampliada.py": ROOT / "prisma/data/captura_ampliada.py",
        "prisma/domain/__init__.py": ROOT / "prisma/domain/__init__.py",
        "prisma/domain/catalogo_ipc.py": ROOT / "prisma/domain/catalogo_ipc.py",
        "prisma/domain/calendario_bmv.py": ROOT / "prisma/domain/calendario_bmv.py",
    }
    with zipfile.ZipFile(args.salida, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for nombre, archivo in archivos.items():
            info = zipfile.ZipInfo(nombre, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, archivo.read_bytes())
    print(hashlib.sha256(args.salida.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
