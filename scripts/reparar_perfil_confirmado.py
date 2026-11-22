"""Repara perfil faltante sin cambiar contraseña, correo verificado ni permisos existentes.

Ejecutar como módulo: python -m scripts.reparar_perfil_confirmado --usuario ... .
Requiere boto3 en el entorno del operador. Por defecto solo diagnostica.
"""
import argparse
import os
from infra.auth_aws_aislado.post_confirmacion import ejecutar


def main():
    import boto3
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--usuario", required=True)
    p.add_argument("--aplicar", action="store_true")
    args = p.parse_args()
    pool = os.environ["COGNITO_POOL_ID"]
    user = boto3.client("cognito-idp").admin_get_user(UserPoolId=pool, Username=args.usuario)
    if user["UserStatus"] != "CONFIRMED":
        raise ValueError("El usuario todavía no está confirmado")
    attrs = {a["Name"]: a["Value"] for a in user["UserAttributes"]}
    if attrs.get("email_verified") != "true":
        raise ValueError("Correo no verificado")
    if not args.aplicar:
        print("Identidad confirmada; usar --aplicar para crear únicamente el perfil faltante.")
        return
    evento = {"userPoolId": pool, "triggerSource": "PostConfirmation_ConfirmSignUp",
              "request": {"userAttributes": attrs}}
    ejecutar(evento, boto3.resource("dynamodb").Table(os.environ["PERFILES_TABLE"]), pool)
    print("Perfil mínimo creado o perfil existente conservado.")


if __name__ == "__main__":
    main()
