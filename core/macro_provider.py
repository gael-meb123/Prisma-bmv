"""Indicadores oficiales de Banxico; caché en memoria, sin datos simulados."""
from __future__ import annotations

import json
import math
import os
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

INDICADORES = (
    {
        "id": "usd_mxn", "serie": "SF43718", "simbolo": "USD/MXN FIX",
        "nombre": "Tipo de cambio FIX", "unidad": "MXN por dólar",
        "descripcion": "Tipo de cambio determinado por Banco de México. Su publicación no es una cotización en tiempo real.",
    },
    {
        "id": "tasa_objetivo", "serie": "SF61745", "simbolo": "TASA BANXICO",
        "nombre": "Tasa objetivo de política monetaria", "unidad": "% anual",
        "descripcion": "Objetivo para la tasa de interés interbancaria a un día, fijado por Banco de México.",
    },
    {
        "id": "inflacion_mensual", "serie": "SP30577", "simbolo": "INFLACIÓN MENSUAL",
        "nombre": "Variación mensual del INPC", "unidad": "% mensual",
        "descripcion": "Variación mensual del Índice Nacional de Precios al Consumidor, consultada en el SIE de Banco de México.",
    },
    {
        "id": "cetes_28", "serie": "SF43936", "simbolo": "CETES 28 DÍAS",
        "nombre": "Rendimiento de CETES a 28 días", "unidad": "% anual",
        "descripcion": "Tasa de rendimiento de CETES a 28 días en la subasta semanal, publicada por Banco de México.",
    },
)
FUENTE = "Banco de México · Sistema de Información Económica"
URL_FUENTE = "https://www.banxico.org.mx/SieInternet/"
TTL_SEGUNDOS = 900
_lock = threading.Lock()
_cache: dict[str, dict[str, Any]] = {}


def _descargar(serie: str, token: str) -> tuple[float, str]:
    url = f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{serie}/datos/oportuno"
    req = urllib.request.Request(url, headers={"Bmx-Token": token, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as respuesta:
        datos = json.load(respuesta)["bmx"]["series"][0]["datos"]
    for dato in reversed(datos):
        try:
            valor = float(str(dato["dato"]).replace(",", ""))
            fecha = datetime.strptime(dato["fecha"], "%d/%m/%Y").date().isoformat()
            if math.isfinite(valor):
                return valor, fecha
        except (ValueError, TypeError, KeyError):
            continue
    raise ValueError("Serie sin observaciones válidas")


def obtener_indicadores() -> dict[str, Any]:
    token = os.environ.get("BANXICO_TOKEN", "").strip()
    indicadores = []
    with _lock:
        for config in INDICADORES:
            serie = config["serie"]
            entrada = _cache.get(serie)
            if entrada is None or time.monotonic() - entrada["intento"] >= TTL_SEGUNDOS:
                previo = entrada.get("dato") if entrada else None
                dato = previo
                error = True
                if token:
                    try:
                        valor, fecha = _descargar(serie, token)
                        dato = {
                            "valor": valor, "fecha_dato": fecha,
                            "consultado_en": datetime.now(timezone.utc).isoformat(),
                        }
                        error = False
                    except (OSError, ValueError, KeyError, IndexError, TypeError):
                        pass
                entrada = {"intento": time.monotonic(), "dato": dato, "error": error}
                _cache[serie] = entrada
            dato = entrada["dato"]
            indicadores.append({
                **config, "fuente": FUENTE, "url_fuente": URL_FUENTE,
                "valor": dato["valor"] if dato else None,
                "fecha_dato": dato["fecha_dato"] if dato else None,
                "consultado_en": dato["consultado_en"] if dato else None,
                "estado": "no_disponible" if not dato else "ultima_consulta_fallida" if entrada["error"] else "disponible",
            })
    return {"indicadores": indicadores}


def obtener_desde_s3(bucket: str, key: str = "macro/indicadores.json") -> dict[str, Any]:
    """Lee la instantánea de AWS sin hacerla pública ni ocultar fallos de S3."""
    import boto3

    respuesta = boto3.client("s3").get_object(Bucket=bucket, Key=key)
    contenido = json.load(respuesta["Body"])
    indicadores = contenido["indicadores"]
    if not isinstance(indicadores, list):
        raise ValueError("Formato de indicadores inválido")
    limite = datetime.now(timezone.utc) - timedelta(minutes=35)
    for item in indicadores:
        try:
            consultado = datetime.fromisoformat(item["consultado_en"])
            if consultado.tzinfo is None or consultado < limite:
                raise ValueError("Consulta desactualizada")
        except (KeyError, ValueError, TypeError):
            if item.get("valor") is not None:
                item["estado"] = "ultima_consulta_fallida"
    return contenido
