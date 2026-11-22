"""Verificación de solo lectura del Gold de la Lambda activa.

Requiere AWS CLI y credenciales de lectura. No ejecuta Athena ni modifica S3,
Glue, Lambda o Scheduler. Verifica todos los archivos CSV del prefijo; no prueba
que el productor mantendrá el contrato en futuras ejecuciones.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DDL = ROOT / "infra/athena/11_gold_g2_lambda_activa_referencia.sql"
PREFIX = "gold/senales_g2/"


def columnas_ddl(texto: str) -> list[tuple[str, str]]:
    return [(nombre, tipo.lower()) for nombre, tipo in
            re.findall(r"`([^`]+)`\s+(STRING|INT|DOUBLE)", texto)]


def comparar_contrato(esperado, tabla, encabezados):
    errores = []
    actual = [(c["Name"], c["Type"].lower()) for c in tabla["StorageDescriptor"]["Columns"]]
    if actual != esperado:
        errores.append("El orden o los tipos de Glue no coinciden con el DDL activo.")
    sd = tabla["StorageDescriptor"]
    if sd.get("SerdeInfo", {}).get("SerializationLibrary") != "org.apache.hadoop.hive.serde2.OpenCSVSerde":
        errores.append("La tabla no usa OpenCSVSerde.")
    serde = sd.get("SerdeInfo", {}).get("Parameters", {})
    if serde.get("separatorChar", ",") != "," or serde.get("quoteChar", '"') != '"':
        errores.append("Los parámetros CSV de Glue son incompatibles.")
    if tabla.get("Parameters", {}).get("skip.header.line.count") != "1":
        errores.append("Glue no omite exactamente una fila de encabezado.")
    if tabla.get("Parameters", {}).get("use.null.for.invalid.data") != "true":
        errores.append("Glue no aplica el manejo esperado de datos numéricos vacíos.")
    if not encabezados:
        errores.append("No hay archivos CSV en el prefijo Gold.")
    for key, columnas in encabezados.items():
        if columnas != [nombre for nombre, _ in esperado]:
            errores.append(f"Encabezado incompatible: {key}")
    return errores


def aws_json(region: str, *args: str) -> dict:
    comando = ["aws", "--region", region, *args, "--output", "json"]
    salida = subprocess.run(comando, check=True, capture_output=True, text=True)
    return json.loads(salida.stdout)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--database", default="default")
    ap.add_argument("--tabla", default="bmv_gold_senales_g2")
    a = ap.parse_args()
    try:
        esperado = columnas_ddl(DDL.read_text(encoding="utf-8"))
        if len(esperado) != 42:
            raise ValueError("DDL local incompleto o modificado; se esperaban 42 columnas.")
        tabla = aws_json(a.region, "glue", "get-table", "--database-name", a.database,
                         "--name", a.tabla)["Table"]
        location = tabla["StorageDescriptor"]["Location"].rstrip("/")
        if location != f"s3://{a.bucket}/{PREFIX.rstrip('/')}":
            raise ValueError(f"Ubicación de tabla inesperada: {location}")
        listing = aws_json(a.region, "s3api", "list-objects-v2", "--bucket", a.bucket,
                           "--prefix", PREFIX)
        objetos = [obj for obj in listing.get("Contents", []) if obj["Size"] > 0]
        inesperados = [obj["Key"] for obj in objetos if not obj["Key"].lower().endswith(".csv")]
        if inesperados:
            raise ValueError(f"Archivos no CSV en el prefijo: {inesperados}")
        encabezados = {}
        with tempfile.TemporaryDirectory() as temp:
            for obj in objetos:
                destino = Path(temp) / "gold.csv"
                subprocess.run(
                    ["aws", "--region", a.region, "s3api", "get-object", "--bucket", a.bucket,
                     "--key", obj["Key"], str(destino)],
                    check=True, capture_output=True, text=True,
                )
                with destino.open(encoding="utf-8-sig", newline="") as f:
                    encabezados[obj["Key"]] = next(csv.reader(f), [])
        errores = comparar_contrato(esperado, tabla, encabezados)
        if errores:
            print("\n".join(f"ERROR: {error}" for error in errores))
            return 1
        print(f"OK: {a.database}.{a.tabla}, {len(esperado)} columnas, "
              f"{len(encabezados)} CSV compatible(s). Solo lectura; no se ejecutó Athena.")
        return 0
    except (subprocess.CalledProcessError, OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: no fue posible verificar el contrato: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
