"""ZIP reproducible del trigger; no habilita el registro público."""
import argparse
import hashlib
import zipfile
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", type=Path, required=True)
    args = p.parse_args()
    raw = (Path(__file__).resolve().parents[1] / "infra/auth_aws_aislado/post_confirmacion.py").read_bytes()
    with args.salida.open("xb") as f, zipfile.ZipFile(f, "w") as z:
        info = zipfile.ZipInfo("post_confirmacion.py", (2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, raw)
    print(hashlib.sha256(args.salida.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
