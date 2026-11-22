"""Prueba el alta real y trigger con identidad sintética. No acredita entrega de email."""
import json
import os
import secrets
import subprocess
import tempfile
import uuid
import argparse
from pathlib import Path

POOL = "us-east-1_v3pSALFxz"
CLIENT = "730sj9tfmfhk44ctctt0kaar9f"
TABLE = "prisma-bmv-auth-registro-pruebas-2026-Perfiles-THHZCNFY4J15"


def aws(servicio, operacion, datos):
    # No imprimir argumentos que contienen secretos ni respuestas de autenticación.
    with tempfile.TemporaryDirectory(dir=Path(os.environ["LOCALAPPDATA"]) / "Temp/opencode") as directory:
        path = Path(directory) / "input.json"
        path.write_text(json.dumps(datos), encoding="utf-8")
        p = subprocess.run(["aws", servicio, operacion, "--region", "us-east-1",
                            "--cli-input-json", "file://" + str(path), "--output", "json"],
                           capture_output=True, text=True, timeout=45)
    if p.returncode:
        # stderr de Cognito no contiene passwords ni tokens; evita stdout.
        raise RuntimeError(p.stderr.strip())
    return json.loads(p.stdout) if p.stdout.strip() else {}


def main():
    global POOL, CLIENT, TABLE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--principal-sintetico", action="store_true")
    args = parser.parse_args()
    if args.principal_sintetico:
        POOL, CLIENT, TABLE = ("us-east-1_mKU76i6gl", "3k7iv4ebko2us1bbk78v07cg09",
                               "prisma-bmv-auth-aislado-2026-Perfiles-1JSFRU50XIG7B")
    email = "registro-" + uuid.uuid4().hex + "@example.invalid"
    password = "Prisma!7" + secrets.token_hex(20)
    sub = None
    try:
        signup = aws("cognito-idp", "sign-up", {"ClientId": CLIENT, "Username": email,
                     "Password": password, "UserAttributes": [{"Name": "email", "Value": email},
                                                               {"Name": "name", "Value": "Prueba sintética"}]})
        sub = signup["UserSub"]
        assert signup["UserConfirmed"] is False
        assert not aws("dynamodb", "get-item", {"TableName": TABLE, "Key": {"sub": {"S": sub}},
                                              "ConsistentRead": True}).get("Item")
        try:
            aws("cognito-idp", "confirm-sign-up", {"ClientId": CLIENT, "Username": email, "ConfirmationCode": "000000"})
        except RuntimeError as exc:
            assert "CodeMismatchException" in str(exc) or "ExpiredCodeException" in str(exc)
        else:
            raise AssertionError("El código incorrecto fue aceptado")
        # Solo identidad sintética: no simula ni acredita propiedad de un correo humano.
        aws("cognito-idp", "admin-update-user-attributes", {"UserPoolId": POOL, "Username": email,
            "UserAttributes": [{"Name": "email_verified", "Value": "true"}]})
        aws("cognito-idp", "admin-confirm-sign-up", {"UserPoolId": POOL, "Username": email})
        item = aws("dynamodb", "get-item", {"TableName": TABLE, "Key": {"sub": {"S": sub}},
                                           "ConsistentRead": True})["Item"]
        assert item["plan"]["S"] == "explorer" and item["rol"]["S"] == "user"
        env = {**os.environ, "POOL": POOL, "CLIENT": CLIENT, "EMAIL": email, "PASS": password}
        if args.principal_sintetico:
            env["API_REGISTRO"] = "https://j42hw8l6rl.execute-api.us-east-1.amazonaws.com"
        result = subprocess.run(["node", "scripts/probar_login_registro.cjs"],
                                cwd=Path(__file__).resolve().parents[1] / "frontend",
                                env=env, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError("Falló acceso SRP del usuario registrado")
        aws("cognito-idp", "forgot-password", {"ClientId": CLIENT, "Username": email})
        try:
            aws("cognito-idp", "confirm-forgot-password", {"ClientId": CLIENT, "Username": email,
                "ConfirmationCode": "000000", "Password": "Prisma!8" + secrets.token_hex(20)})
        except RuntimeError as exc:
            assert "CodeMismatchException" in str(exc) or "ExpiredCodeException" in str(exc)
        else:
            raise AssertionError("Recuperación aceptó código incorrecto")
        print(json.dumps({"registro_real": "OK", "codigo_incorrecto_rechazado": "OK",
                          "trigger_post_confirmacion": "OK", "perfil": "user/explorer",
                          "login_srp": "OK", "api_me": "OK" if args.principal_sintetico else "NO_APLICA",
                          "recuperacion_codigo_incorrecto": "RECHAZADO",
                          "entrega_email": "PENDIENTE_VALIDACION_HUMANA"}))
    finally:
        if sub:
            aws("cognito-idp", "admin-delete-user", {"UserPoolId": POOL, "Username": email})
            aws("dynamodb", "delete-item", {"TableName": TABLE, "Key": {"sub": {"S": sub}}})


if __name__ == "__main__":
    main()
