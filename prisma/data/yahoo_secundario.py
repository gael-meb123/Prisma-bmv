"""Interpretación local de un cierre diario Yahoo; sin HTTP ni escrituras.

La salida es una observación secundaria no oficial, no un PPP BMV ni un dato
autorizado para redistribución o inferencia.
"""
import hashlib
import json
import math
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def interpretar_cierre(raw, simbolo, fecha):
    if not isinstance(raw, bytes) or not raw or len(raw) > 2_000_000:
        raise ValueError("Respuesta vacía o demasiado grande.")
    if not isinstance(simbolo, str) or not simbolo.strip() or len(simbolo) > 40:
        raise ValueError("Símbolo inválido.")
    if date.fromisoformat(fecha).isoformat() != fecha:
        raise ValueError("Fecha inválida.")
    try:
        respuesta = json.loads(raw)
        chart = respuesta["chart"]
        if chart.get("error") is not None or len(chart["result"]) != 1:
            raise ValueError("Respuesta Yahoo no disponible o ambigua.")
        resultado = chart["result"][0]
        meta = resultado["meta"]
        if meta["symbol"] != simbolo or meta.get("currency") != "MXN":
            raise ValueError("Símbolo o moneda no coinciden.")
        timestamps = resultado["timestamp"]
        quotes = resultado["indicators"]["quote"]
        if len(quotes) != 1:
            raise ValueError("Series de cotización ambiguas.")
        precios = quotes[0]["close"]
        if not isinstance(timestamps, list) or not isinstance(precios, list) or len(timestamps) != len(precios):
            raise ValueError("Serie de precios incompleta.")
        observaciones = []
        tz = ZoneInfo("America/Mexico_City")
        for instante, valor in zip(timestamps, precios):
            if isinstance(instante, bool) or not isinstance(instante, (int, float)) or not math.isfinite(instante):
                raise ValueError("Marca de tiempo inválida.")
            utc = datetime.fromtimestamp(instante, tz=timezone.utc)
            if utc.astimezone(tz).date().isoformat() != fecha:
                continue
            if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor <= 0:
                continue
            observaciones.append((utc, float(valor)))
    except (KeyError, TypeError, IndexError, OverflowError, OSError, json.JSONDecodeError) as exc:
        raise ValueError("Formato de respuesta Yahoo inválido.") from exc
    if len(observaciones) != 1:
        raise ValueError("No existe un único cierre válido para esa fecha.")
    instante, valor = observaciones[0]
    return {"fecha": fecha, "simbolo": simbolo, "moneda": "MXN",
            "valor": valor, "tipo": "CIERRE_DIARIO_REPORTADO",
            "fuente": "YAHOO_FINANCE_SECUNDARIA", "estado": "NO_OFICIAL_NO_VALIDADO",
            "timestamp_fuente_utc": instante.isoformat(),
            "sha256_respuesta": hashlib.sha256(raw).hexdigest(),
            "advertencia": "No es PPP BMV, no valida composición IPC ni autoriza redistribución o inferencia."}
