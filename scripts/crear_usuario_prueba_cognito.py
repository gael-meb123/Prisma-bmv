"""Crea un usuario sintético aislado sin imprimir ni guardar su contraseña."""
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


def aws(*args, check=True):
    return subprocess.run(["aws", *args, "--region", "us-east-1", "--output", "json"],
                          capture_output=True, text=True, check=check)


def main():
    if sys.argv[1:] != ["--crear-usuario-sintetico"]:
        raise SystemExit("Requiere --crear-usuario-sintetico; no modifica usuarios existentes.")
    previo = aws("cognito-idp", "admin-get-user", "--user-pool-id", POOL, "--username", EMAIL, check=False)
    if previo.returncode == 0:
        raise SystemExit("El usuario de prueba ya existe; no se sobrescribe.")
    if "UserNotFoundException" not in previo.stderr:
        raise SystemExit("No se pudo verificar si existe el usuario de prueba.")
    password = "Pr1sma!" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(25)) + "#"
    try:
        creado = json.loads(aws("cognito-idp", "admin-create-user", "--user-pool-id", POOL,
                                "--username", EMAIL, "--user-attributes", "Name=email,Value=" + EMAIL,
                                "Name=email_verified,Value=true", "--message-action", "SUPPRESS").stdout)
        sub = next(x["Value"] for x in creado["User"]["Attributes"] if x["Name"] == "sub")
        aws("cognito-idp", "admin-set-user-password", "--user-pool-id", POOL, "--username", EMAIL,
            "--password", password, "--permanent")
        item = {k: {"S": v} for k, v in {"sub": sub, "email": EMAIL, "nombre": "Prueba aislada",
                                         "rol": "user", "plan": "explorer"}.items()}
        aws("dynamodb", "put-item", "--table-name", TABLE, "--item", json.dumps(item),
            "--condition-expression", "attribute_not_exists(#s)",
            "--expression-attribute-names", json.dumps({"#s": "sub"}))
    except subprocess.CalledProcessError:
        raise SystemExit("Falló AWS; el usuario o perfil de prueba podría existir parcialmente; revisar sin sobrescribir.") from None
    entorno = {**os.environ, "POOL": POOL, "CLIENT": CLIENT, "EMAIL": EMAIL, "PASS": password, "API": API}
    print("Usuario sintético creado; contraseña aleatoria no almacenada.")
    resultado = subprocess.run(["node", "scripts/probar_cognito.cjs"], cwd=ROOT / "frontend", env=entorno, timeout=60)
    return resultado.returncode


if __name__ == "__main__":
    raise SystemExit(main())
