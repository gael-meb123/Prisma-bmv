"""Publicación programada y conexiones WebSocket de la cinta macroeconómica."""
import json
import math
import os
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import ClientError

SERIES = (
    ("usd_mxn", "SF43718", "USD/MXN FIX", "Tipo de cambio FIX", "MXN por dólar", "Tipo de cambio determinado por Banco de México. No es una cotización continua."),
    ("tasa_objetivo", "SF61745", "TASA BANXICO", "Tasa objetivo de política monetaria", "% anual", "Objetivo para la tasa de interés interbancaria a un día."),
    ("inflacion_mensual", "SP30577", "INFLACIÓN MENSUAL", "Variación mensual del INPC", "% mensual", "Variación mensual del Índice Nacional de Precios al Consumidor."),
    ("cetes_28", "SF43936", "CETES 28 DÍAS", "Rendimiento de CETES a 28 días", "% anual", "Tasa de rendimiento de CETES a 28 días en la subasta semanal."),
)


def _serie(identificador, token):
    url = f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{identificador}/datos/oportuno"
    with urlopen(Request(url, headers={"Bmx-Token": token, "Accept": "application/json"}), timeout=5) as response:
        datos = json.load(response)["bmx"]["series"][0]["datos"]
    for item in reversed(datos):
        try:
            valor = float(str(item["dato"]).replace(",", ""))
            fecha = datetime.strptime(item["fecha"], "%d/%m/%Y").date().isoformat()
            if math.isfinite(valor):
                return valor, fecha
        except (KeyError, ValueError, TypeError):
            continue
    raise ValueError("Sin datos válidos")


def conexiones(event, context):
    tabla = boto3.resource("dynamodb").Table(os.environ["CONNECTIONS_TABLE"])
    contexto = event["requestContext"]
    conexion = contexto["connectionId"]
    if contexto["routeKey"] == "$connect":
        tabla.put_item(Item={"connectionId": conexion, "expiresAt": int(time.time()) + 7200})
    elif contexto["routeKey"] == "$disconnect":
        tabla.delete_item(Key={"connectionId": conexion})
    return {"statusCode": 200}


def _anterior(s3, bucket, key):
    try:
        return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404", "NotFound"):
            return {}
        raise


def publicar(event, context):
    s3 = boto3.client("s3")
    bucket, key = os.environ["MACRO_BUCKET"], os.environ["MACRO_KEY"]
    token = boto3.client("secretsmanager").get_secret_value(SecretId=os.environ["BANXICO_SECRET_ARN"])["SecretString"].strip()
    if not token:
        raise ValueError("El secreto de Banxico está vacío")
    previos = {x["id"]: x for x in _anterior(s3, bucket, key).get("indicadores", [])}
    indicadores = []
    for id_, serie, simbolo, nombre, unidad, descripcion in SERIES:
        dato = {"id": id_, "serie": serie, "simbolo": simbolo, "nombre": nombre, "unidad": unidad,
                "descripcion": descripcion, "fuente": "Banco de México · Sistema de Información Económica",
                "url_fuente": "https://www.banxico.org.mx/SieInternet/"}
        try:
            valor, fecha = _serie(serie, token)
            dato.update(valor=valor, fecha_dato=fecha, consultado_en=datetime.now(timezone.utc).isoformat(), estado="disponible")
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            previo = previos.get(id_, {})
            dato.update(valor=previo.get("valor"), fecha_dato=previo.get("fecha_dato"),
                        consultado_en=previo.get("consultado_en"),
                        estado="ultima_consulta_fallida" if previo.get("valor") is not None else "no_disponible")
        indicadores.append(dato)
    contenido = {"indicadores": indicadores, "publicado_en": datetime.now(timezone.utc).isoformat()}
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(contenido, ensure_ascii=False).encode("utf-8"),
                  ContentType="application/json; charset=utf-8")
    tabla = boto3.resource("dynamodb").Table(os.environ["CONNECTIONS_TABLE"])
    gateway = boto3.client("apigatewaymanagementapi", endpoint_url=os.environ["WS_MANAGEMENT_URL"])
    scan_args = {"ProjectionExpression": "connectionId"}
    while True:
        pagina = tabla.scan(**scan_args)
        for item in pagina.get("Items", []):
            try:
                gateway.post_to_connection(ConnectionId=item["connectionId"], Data=b'{"tipo":"macro_actualizada"}')
            except ClientError as exc:
                if exc.response["Error"]["Code"] in ("GoneException", "410"):
                    tabla.delete_item(Key={"connectionId": item["connectionId"]})
                else:
                    print("No se pudo notificar una conexión:", exc.response["Error"]["Code"])
        if "LastEvaluatedKey" not in pagina:
            break
        scan_args["ExclusiveStartKey"] = pagina["LastEvaluatedKey"]
    return {"estado": "publicado", "series_disponibles": sum(x["estado"] == "disponible" for x in indicadores)}
