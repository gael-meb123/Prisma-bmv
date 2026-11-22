"""Verifica operaciones de lectura para el laboratorio, sin ejecutar consultas ni despliegues."""
from __future__ import annotations

import argparse
import json


def diagnosticar(session, region, bucket, database, tabla, funcion, scheduler):
    """Cada resultado acredita solo la operación de lectura indicada."""
    pruebas = [
        ("identidad", lambda: session.client("sts", region_name=region).get_caller_identity()),
        ("s3_head_bucket", lambda: session.client("s3", region_name=region).head_bucket(Bucket=bucket)),
        ("glue_get_table", lambda: session.client("glue", region_name=region).get_table(DatabaseName=database, Name=tabla)),
        ("athena_get_work_group", lambda: session.client("athena", region_name=region).get_work_group(WorkGroup="primary")),
        ("lambda_get_configuration", lambda: session.client("lambda", region_name=region).get_function_configuration(FunctionName=funcion)),
        ("scheduler_get_schedule", lambda: session.client("scheduler", region_name=region).get_schedule(Name=scheduler)),
    ]
    resultados = {}
    for nombre, operacion in pruebas:
        try:
            operacion()
            resultados[nombre] = {"estado": "LECTURA_OK"}
        except Exception as exc:
            codigo = getattr(exc, "response", {}).get("Error", {}).get("Code", type(exc).__name__)
            resultados[nombre] = {"estado": "NO_VERIFICADO", "codigo": str(codigo)}
    return {"region": region, "resultados": resultados,
            "limites": "No prueba permisos de escritura, invocación, consulta Athena, contenido ni costos."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--bucket", required=True)
    p.add_argument("--database", default="default")
    p.add_argument("--tabla", default="bmv_silver_ppp")
    p.add_argument("--funcion", default="recolector-diario-bmv")
    p.add_argument("--scheduler", default="DisparadorDiarioBMV")
    a = p.parse_args()
    try:
        import boto3
    except ImportError:
        p.exit(2, "Falta boto3. Instale las dependencias del proyecto antes de ejecutar el diagnóstico.\n")
    resultado = diagnosticar(boto3.Session(), a.region, a.bucket, a.database, a.tabla, a.funcion, a.scheduler)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if all(x["estado"] == "LECTURA_OK" for x in resultado["resultados"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
