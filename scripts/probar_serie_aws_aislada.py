"""Renueva contraseña SOLO del usuario sintético y prueba autorización de la serie."""
import os
import secrets
import string
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = "us-east-1_mKU76i6gl"
CLIENT = "3k7iv4ebko2us1bbk78v07cg09"
EMAIL = "prisma-prueba-2026@example.invalid"
API = "https://j42hw8l6rl.execute-api.us-east-1.amazonaws.com"


def main():
    if sys.argv[1:] not in (["--renovar-solo-usuario-sintetico"],
                            ["--renovar-solo-usuario-sintetico", "--concurrencia"],
                            ["--renovar-solo-usuario-sintetico", "--senales-bloqueadas"]):
        raise SystemExit("Se requiere --renovar-solo-usuario-sintetico; opcional: --concurrencia o --senales-bloqueadas.")
    password = "Pr1sma!" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(25)) + "#"
    result = subprocess.run(["aws", "cognito-idp", "admin-set-user-password", "--region", "us-east-1",
                             "--user-pool-id", POOL, "--username", EMAIL, "--password", password, "--permanent"],
                            capture_output=True, text=True)
    if result.returncode:
        raise SystemExit("No fue posible renovar la contraseña del usuario sintético.")
    env = {**os.environ, "POOL": POOL, "CLIENT": CLIENT, "EMAIL": EMAIL, "PASS": password, "API": API}
    script = ("scripts/probar_concurrencia_cognito.cjs" if "--concurrencia" in sys.argv else
              "scripts/probar_senales_bloqueadas.cjs" if "--senales-bloqueadas" in sys.argv else
              "scripts/probar_serie_cognito.cjs")
    return subprocess.run(["node", script], cwd=ROOT / "frontend",
                          env=env, timeout=60).returncode


if __name__ == "__main__":
    raise SystemExit(main())
