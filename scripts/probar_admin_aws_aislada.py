"""Prueba admin con el perfil sintético; restaura rol/plan aunque falle la prueba."""
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
TABLE = "prisma-bmv-auth-aislado-2026-Perfiles-1JSFRU50XIG7B"
API = "https://j42hw8l6rl.execute-api.us-east-1.amazonaws.com"


def aws(*args):
    return subprocess.run(["aws", *args, "--region", "us-east-1", "--output", "json"],
                          capture_output=True, text=True)


def main():
    if sys.argv[1:] != ["--solo-usuario-sintetico"]:
        raise SystemExit("Se requiere --solo-usuario-sintetico.")
    user = aws("cognito-idp", "admin-get-user", "--user-pool-id", POOL, "--username", EMAIL)
    if user.returncode:
        raise SystemExit("No se pudo comprobar el usuario sintético.")
    data = json.loads(user.stdout)
    if data.get("UserMFASettingList"):
        raise SystemExit("El usuario sintético tiene MFA activo; no se modifica.")
    sub = next((x["Value"] for x in data["UserAttributes"] if x["Name"] == "sub"), None)
    if not sub:
        raise SystemExit("El usuario sintético no tiene sub.")
    key = json.dumps({"sub": {"S": sub}})
    perfil = aws("dynamodb", "get-item", "--table-name", TABLE, "--key", key, "--consistent-read")
    if perfil.returncode:
        raise SystemExit("No se pudo leer el perfil sintético.")
    item = json.loads(perfil.stdout).get("Item", {})
    if (item.get("email", {}).get("S"), item.get("rol", {}).get("S"), item.get("plan", {}).get("S")) != (EMAIL, "user", "explorer"):
        raise SystemExit("El perfil sintético no coincide con el estado esperado; no se modifica.")
    password = "Pr1sma!" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(25)) + "#"
    reset = aws("cognito-idp", "admin-set-user-password", "--user-pool-id", POOL, "--username", EMAIL,
                "--password", password, "--permanent")
    if reset.returncode:
        raise SystemExit("No se pudo renovar la contraseña sintética.")
    env = {**os.environ, "POOL": POOL, "CLIENT": CLIENT, "EMAIL": EMAIL, "PASS": password, "API": API}
    def prueba(role):
        script = ("scripts/probar_react_local_cdp.cjs" if role == "si" and os.environ.get("PRISMA_ADMIN_BROWSER") == "1"
                  else "scripts/probar_admin_cognito.cjs")
        return subprocess.run(["node", script], cwd=ROOT / "frontend",
                              env={**env, "TEST_ADMIN": role}, timeout=100).returncode
    if prueba("no"):
        return 1
    nombres = json.dumps({"#r": "rol", "#p": "plan"})
    valores = json.dumps({":user": {"S": "user"}, ":admin": {"S": "admin"}, ":plan": {"S": "explorer"}})
    promoted = aws("dynamodb", "update-item", "--table-name", TABLE, "--key", key,
                   "--update-expression", "SET #r = :admin",
                   "--condition-expression", "#r = :user AND #p = :plan",
                   "--expression-attribute-names", nombres, "--expression-attribute-values", valores)
    if promoted.returncode:
        raise SystemExit("No se pudo elevar temporalmente el perfil sintético.")
    try:
        return prueba("si")
    finally:
        restored = aws("dynamodb", "update-item", "--table-name", TABLE, "--key", key,
                       "--update-expression", "SET #r = :user, #p = :plan",
                       "--condition-expression", "#r = :admin",
                       "--expression-attribute-names", nombres, "--expression-attribute-values", valores)
        if restored.returncode:
            print("ATENCIÓN: no se pudo restaurar el perfil sintético; requiere revisión.", file=sys.stderr)
            raise SystemExit(1)
        print("Perfil sintético restaurado a user/explorer.")


if __name__ == "__main__":
    raise SystemExit(main())
