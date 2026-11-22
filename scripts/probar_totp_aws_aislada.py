"""Prueba TOTP únicamente con el usuario sintético; restablece la preferencia MFA."""
import json
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
BASE = ["aws", "cognito-idp"]


def aws(*args):
    return subprocess.run([*BASE, *args, "--region", "us-east-1"], capture_output=True, text=True)


def main():
    if sys.argv[1:] != ["--solo-usuario-sintetico"]:
        raise SystemExit("Se requiere --solo-usuario-sintetico.")
    before = aws("admin-get-user", "--user-pool-id", POOL, "--username", EMAIL, "--output", "json")
    if before.returncode:
        raise SystemExit("No fue posible revisar el usuario sintético.")
    user = json.loads(before.stdout)
    if user.get("UserMFASettingList") or user.get("PreferredMfaSetting"):
        raise SystemExit("El usuario sintético ya tiene MFA; no se modifica su configuración.")
    password = "Pr1sma!" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(25)) + "#"
    reset = aws("admin-set-user-password", "--user-pool-id", POOL, "--username", EMAIL,
                "--password", password, "--permanent")
    if reset.returncode:
        raise SystemExit("No fue posible renovar la contraseña sintética.")
    try:
        env = {**os.environ, "POOL": POOL, "CLIENT": CLIENT, "EMAIL": EMAIL, "PASS": password}
        result = subprocess.run(["node", "scripts/probar_totp_cognito.cjs"], cwd=ROOT / "frontend",
                                env=env, timeout=100)
        return result.returncode
    finally:
        cleanup = aws("admin-set-user-mfa-preference", "--user-pool-id", POOL, "--username", EMAIL,
                      "--software-token-mfa-settings", "Enabled=false,PreferredMfa=false")
        if cleanup.returncode:
            print("ATENCIÓN: no se pudo restablecer la preferencia MFA del usuario sintético.", file=sys.stderr)
            raise SystemExit(1)
        print("Preferencia MFA del usuario sintético restablecida a deshabilitada.")


if __name__ == "__main__":
    raise SystemExit(main())
