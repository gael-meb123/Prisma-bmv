"""Empaqueta API y dependencias explícitas reproduciblemente; no despliega en AWS."""
import argparse
import hashlib
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", required=True)
    destino = Path(parser.parse_args().salida)
    handler = Path(__file__).resolve().parent.parent / "infra/api_gateway_aislada/handler.py"
    with destino.open("xb") as archivo:
        with zipfile.ZipFile(archivo, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            raiz = handler.parents[2]
            archivos = {
                "handler.py": handler.read_bytes(),
                "infra/__init__.py": b"",
                "infra/capturas_seguras.py": (handler.parents[1] / "capturas_seguras.py").read_bytes(),
                "prisma/__init__.py": b"",
                "prisma/data/__init__.py": b"",
                "prisma/data/yahoo_secundario.py": (raiz / "prisma/data/yahoo_secundario.py").read_bytes(),
                "prisma/data/captura_ampliada.py": (raiz / "prisma/data/captura_ampliada.py").read_bytes(),
                "prisma/data/ipc35_almacen.py": (raiz / "prisma/data/ipc35_almacen.py").read_bytes(),
                "prisma/data/gold_evaluacion.py": (raiz / "prisma/data/gold_evaluacion.py").read_bytes(),
                "prisma/domain/__init__.py": b"",
                "prisma/domain/calendario_bmv.py": (raiz / "prisma/domain/calendario_bmv.py").read_bytes(),
                "prisma/domain/catalogo_ipc.py": (raiz / "prisma/domain/catalogo_ipc.py").read_bytes(),
                "prisma/domain/catalogos/naftrac_2026-11-17_v1.json": (
                    raiz / "prisma/domain/catalogos/naftrac_2026-11-17_v1.json"
                ).read_bytes(),
            }
            for nombre, raw in sorted(archivos.items()):
                info = zipfile.ZipInfo(nombre, (2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                zipf.writestr(info, raw)
    print("SHA-256:", hashlib.sha256(destino.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
