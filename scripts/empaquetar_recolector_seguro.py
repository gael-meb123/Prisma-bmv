"""Empaqueta la variante segura; no despliega ni modifica recursos AWS."""
import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "infra/lambda/recolector_seguro/handler.py",
    "infra/lambda/recolector_seguro/prueba_aws.py",
    "infra/lambda/guardia_senales/handler.py",
    "infra/lambda_guardia_adapter.py",
    "infra/capturas_seguras.py",
    "infra/api_gateway_aislada/handler.py",
    "prisma/__init__.py",
    "prisma/data/__init__.py",
    "prisma/data/captura_ampliada.py",
    "prisma/data/ipc35_almacen.py",
    "prisma/data/yahoo_secundario.py",
    "prisma/domain/__init__.py",
    "prisma/domain/bmv_core.py",
    "prisma/domain/calendario_bmv.py",
    "prisma/domain/catalogo_ipc.py",
    "prisma/domain/catalogos/naftrac_2026-11-17_v1.json",
    "prisma/domain/elegibilidad_senales.py",
    "scripts/auditar_boletin_diario.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    with zipfile.ZipFile(args.salida, "w") as archivo:
        archivos = {nombre: (ROOT / nombre).read_bytes() for nombre in FILES}
        for nombre in ("infra/__init__.py", "infra/lambda/__init__.py",
                       "infra/api_gateway_aislada/__init__.py",
                       "infra/lambda/recolector_seguro/__init__.py",
                       "infra/lambda/guardia_senales/__init__.py", "scripts/__init__.py"):
            archivos[nombre] = b""
        for nombre, contenido in sorted(archivos.items()):
            info = zipfile.ZipInfo(nombre, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archivo.writestr(info, contenido)
    print(hashlib.sha256(args.salida.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
