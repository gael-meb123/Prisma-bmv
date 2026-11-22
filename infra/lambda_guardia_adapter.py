"""Adaptador explícito para compartir la guardia sin invocaciones remotas."""
from importlib import import_module


def auditar_s3(evento, s3, bucket):
    guardia = import_module("infra.lambda.guardia_senales.handler")
    return guardia.ejecutar_s3(evento, s3, bucket)
