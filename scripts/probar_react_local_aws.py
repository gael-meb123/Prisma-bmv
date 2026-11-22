"""Renueva solo usuario sintético y ejecuta prueba React local mediante CDP."""
import os
import secrets
import string
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = "us-east-1_mKU76i6gl"
EMAIL = "prisma-prueba-2026@example.invalid"


def main():
    if sys.argv[1:] != ["--solo-usuario-sintetico"]:
        raise SystemExit("Se requiere --solo-usuario-sintetico.")
    password = "Pr1sma!" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(25)) + "#"
    reset = subprocess.run(["aws", "cognito-idp", "admin-set-user-password", "--user-pool-id", POOL,
                            "--username", EMAIL, "--password", password, "--permanent", "--region", "us-east-1"],
                           capture_output=True, text=True)
    if reset.returncode:
        raise SystemExit("No se pudo renovar la contraseña sintética.")
    return subprocess.run(["node", "scripts/probar_react_local_cdp.cjs"], cwd=ROOT / "frontend",
                          env={**os.environ, "EMAIL": EMAIL, "PASS": password}, timeout=150).returncode


if __name__ == "__main__":
    raise SystemExit(main())
