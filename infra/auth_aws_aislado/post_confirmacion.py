"""Perfil mínimo tras confirmación Cognito; nunca acepta rol/plan del cliente."""
import os
from datetime import datetime, timezone


def ejecutar(evento, tabla, pool):
    if evento.get("userPoolId") != pool:
        raise ValueError("Pool no admitido")
    if evento.get("triggerSource") != "PostConfirmation_ConfirmSignUp":
        return evento  # Recuperar contraseña no debe crear ni alterar perfiles.
    atributos = evento.get("request", {}).get("userAttributes", {})
    sub, email, nombre = (atributos.get(x) for x in ("sub", "email", "name"))
    if (atributos.get("email_verified") != "true" or not isinstance(sub, str) or not sub
            or not isinstance(email, str) or "@" not in email
            or not isinstance(nombre, str) or not nombre.strip() or len(nombre) > 120):
        raise ValueError("Identidad confirmada incompleta")
    item = {"sub": sub, "email": email, "nombre": nombre.strip(), "rol": "user",
            "plan": "explorer", "creado_en": datetime.now(timezone.utc).isoformat()}
    try:
        tabla.put_item(Item=item, ConditionExpression="attribute_not_exists(#s)",
                       ExpressionAttributeNames={"#s": "sub"})
    except Exception as exc:
        if getattr(exc, "response", {}).get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        existente = tabla.get_item(Key={"sub": sub}, ConsistentRead=True).get("Item")
        if not existente or existente.get("email") != email:
            raise ValueError("Perfil existente incompatible") from exc
    return evento


def lambda_handler(event, context):
    import boto3
    from botocore.config import Config
    config = Config(connect_timeout=1, read_timeout=2, retries={"total_max_attempts": 1})
    return ejecutar(event, boto3.resource("dynamodb", config=config).Table(os.environ["PERFILES_TABLE"]),
                    os.environ["COGNITO_POOL_ID"])
