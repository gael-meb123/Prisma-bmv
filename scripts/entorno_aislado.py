"""Genera un stack aislado y migra/revierte un CSV sintético sin tocar producción.

El despliegue es explícito con CloudFormation; no instala el recolector de mercado.
Los cambios de versión solo actualizan una tabla Glue perteneciente al stack.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

try:
    from .verificar_contrato_aws import DDL, columnas_ddl
except ImportError:  # ejecución directa: python scripts/entorno_aislado.py
    from verificar_contrato_aws import DDL, columnas_ddl

STACK_PREFIX = "prisma-bmv-aislado-"
TABLE_NAME = "gold_g2_sintetico"
ALLOW_TABLE_FIELDS = ("Name", "Description", "Owner", "Retention", "StorageDescriptor",
                      "PartitionKeys", "ViewOriginalText", "ViewExpandedText", "TableType",
                      "Parameters", "TargetTable")


def plantilla():
    columnas = [{"Name": n, "Type": t} for n, t in columnas_ddl(DDL.read_text(encoding="utf-8"))]
    if len(columnas) != 42:
        raise ValueError("DDL Gold inesperado.")
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Prisma laboratorio aislado: exclusivamente datos sinteticos; sin Scheduler.",
        "Parameters": {"RoleArn": {"Type": "String", "Description": "Rol Lambda existente"}},
        "Resources": {
            "Bucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": "Retain",
                       "UpdateReplacePolicy": "Retain", "Properties": {
                           "VersioningConfiguration": {"Status": "Enabled"},
                           "PublicAccessBlockConfiguration": {
                               "BlockPublicAcls": True, "BlockPublicPolicy": True,
                               "IgnorePublicAcls": True, "RestrictPublicBuckets": True},
                           "BucketEncryption": {"ServerSideEncryptionConfiguration": [
                               {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}}},
            "Database": {"Type": "AWS::Glue::Database", "Properties": {
                "CatalogId": {"Ref": "AWS::AccountId"},
                "DatabaseInput": {
                    "Name": {"Fn::Join": ["_", {"Fn::Split": ["-", {"Ref": "AWS::StackName"}]}]},
                    "Description": "Laboratorio Prisma, datos sinteticos"}}},
            "GoldTable": {"Type": "AWS::Glue::Table", "Properties": {
                "CatalogId": {"Ref": "AWS::AccountId"}, "DatabaseName": {"Ref": "Database"},
                "TableInput": {"Name": TABLE_NAME, "TableType": "EXTERNAL_TABLE",
                               "Parameters": {"EXTERNAL": "TRUE", "skip.header.line.count": "1",
                                              "use.null.for.invalid.data": "true"},
                               "StorageDescriptor": {
                                   "Columns": columnas,
                                   "Location": {"Fn::Sub": "s3://${Bucket}/releases/bootstrap/"},
                                   "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                                   "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                                   "SerdeInfo": {"SerializationLibrary": "org.apache.hadoop.hive.serde2.OpenCSVSerde",
                                                 "Parameters": {"separatorChar": ",", "quoteChar": '"'}}}}}},
            "Health": {"Type": "AWS::Lambda::Function", "Properties": {
                "Runtime": "python3.11", "Handler": "index.handler", "Role": {"Ref": "RoleArn"},
                "Timeout": 10, "MemorySize": 128,
                "Code": {"ZipFile": "def handler(event, context):\n    return {'estado': 'AISLADO', 'fuentes_mercado': False}\n"}}},
        },
        "Outputs": {"Bucket": {"Value": {"Ref": "Bucket"}},
                    "Database": {"Value": {"Ref": "Database"}},
                    "Tabla": {"Value": TABLE_NAME},
                    "LambdaSalud": {"Value": {"Ref": "Health"}}},
    }


def validar_csv(contenido: bytes):
    texto = contenido.decode("utf-8-sig")
    lector = csv.DictReader(io.StringIO(texto, newline=""), restkey="_extra")
    esperado = [n for n, _ in columnas_ddl(DDL.read_text(encoding="utf-8"))]
    if lector.fieldnames != esperado:
        raise ValueError("Encabezado Gold no coincide exactamente con el contrato.")
    filas = list(lector)
    if not filas or any("_extra" in f or None in f.values() for f in filas):
        raise ValueError("CSV vacío o filas con columnas incompletas/adicionales.")
    ids = [f["id_senal_g2"] for f in filas]
    if any(not ident.startswith("SINTETICO_") for ident in ids) or len(ids) != len(set(ids)):
        raise ValueError("Solo se aceptan IDs sintéticos únicos con prefijo SINTETICO_.")
    return len(filas)


def recursos(cf, stack):
    if not re.fullmatch(r"prisma-bmv-aislado-[a-z0-9-]+", stack):
        raise ValueError(f"El stack debe comenzar con {STACK_PREFIX}.")
    s = cf.describe_stacks(StackName=stack)["Stacks"][0]
    if s["StackStatus"] not in ("CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"):
        raise ValueError("Stack no disponible o en estado transitorio.")
    recursos_ = {x["LogicalResourceId"]: x["PhysicalResourceId"] for x in
                 cf.describe_stack_resources(StackName=stack)["StackResources"]}
    if not {"Bucket", "Database", "GoldTable"} <= recursos_.keys():
        raise ValueError("El stack no contiene todos los recursos aislados.")
    return recursos_["Bucket"], recursos_["Database"]


def _tabla_input(tabla):
    return {k: tabla[k] for k in ALLOW_TABLE_FIELDS if k in tabla}


def migrar(s3, glue, bucket, database, release, contenido):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", release) or release == "bootstrap":
        raise ValueError("Versión inválida o reservada.")
    filas = validar_csv(contenido)
    tabla = glue.get_table(DatabaseName=database, Name=TABLE_NAME)["Table"]
    prefijo = f"s3://{bucket}/releases/"
    if not tabla["StorageDescriptor"]["Location"].startswith(prefijo):
        raise ValueError("La tabla no apunta al bucket aislado.")
    esperado = [{"Name": n, "Type": t} for n, t in columnas_ddl(DDL.read_text(encoding="utf-8"))]
    if tabla["StorageDescriptor"]["Columns"] != esperado:
        raise ValueError("El esquema Glue no coincide exactamente con el contrato.")
    key = f"releases/{release}/gold.csv"
    # Una versión no se sobrescribe; si falla el cambio de Glue queda un objeto
    # aislado huérfano, no se elimina automáticamente ni se toca producción.
    s3.put_object(Bucket=bucket, Key=key, Body=contenido, ContentType="text/csv; charset=utf-8",
                  IfNoneMatch="*")
    nuevo = _tabla_input(tabla)
    nuevo["StorageDescriptor"] = dict(tabla["StorageDescriptor"], Location=f"{prefijo}{release}/")
    glue.update_table(DatabaseName=database, TableInput=nuevo, VersionId=tabla["VersionId"])
    return {"filas": filas, "sha256": hashlib.sha256(contenido).hexdigest(),
            "version_glue_anterior": tabla["VersionId"], "ubicacion": nuevo["StorageDescriptor"]["Location"]}


def revertir(glue, bucket, database, version_anterior):
    actual = glue.get_table(DatabaseName=database, Name=TABLE_NAME)["Table"]
    previo = glue.get_table_version(DatabaseName=database, TableName=TABLE_NAME,
                                    VersionId=version_anterior)["TableVersion"]["Table"]
    prefijo = f"s3://{bucket}/releases/"
    if not all(t["StorageDescriptor"]["Location"].startswith(prefijo) for t in (actual, previo)):
        raise ValueError("Reversión rechazada: ubicación fuera del entorno aislado.")
    glue.update_table(DatabaseName=database, TableInput=_tabla_input(previo), VersionId=actual["VersionId"])
    return previo["StorageDescriptor"]["Location"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="accion", required=True)
    t = sub.add_parser("plantilla")
    t.add_argument("--salida", required=True)
    for nombre in ("migrar", "revertir"):
        x = sub.add_parser(nombre)
        x.add_argument("--stack", required=True)
        x.add_argument("--region", default="us-east-1")
        if nombre == "migrar":
            x.add_argument("--csv", required=True)
            x.add_argument("--version", required=True)
        else:
            x.add_argument("--version-glue", required=True)
    a = p.parse_args()
    if a.accion == "plantilla":
        Path(a.salida).write_text(json.dumps(plantilla(), indent=2), encoding="utf-8")
        print(f"Plantilla escrita en {a.salida}; no se modificó AWS.")
        return
    import boto3
    sesion = boto3.Session(region_name=a.region)
    bucket, database = recursos(sesion.client("cloudformation"), a.stack)
    glue = sesion.client("glue")
    if a.accion == "migrar":
        resultado = migrar(sesion.client("s3"), glue, bucket, database, a.version, Path(a.csv).read_bytes())
    else:
        resultado = revertir(glue, bucket, database, a.version_glue)
    print(json.dumps(resultado, ensure_ascii=False))


if __name__ == "__main__":
    main()
