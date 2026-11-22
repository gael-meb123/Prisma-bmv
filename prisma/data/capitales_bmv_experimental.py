"""Interpretación local de respuesta Capitales; no descarga ni habilita señales."""
import json
import math
import re
from datetime import datetime


def _precio(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor) if math.isfinite(valor) and valor > 0 else None


def interpretar(raw: str, observado_en: datetime):
    """Lee el objeto envuelto sin ejecutar JS; no infiere fecha de sesión."""
    if not isinstance(observado_en, datetime) or observado_en.utcoffset() is None:
        raise ValueError("La hora de observación debe incluir zona horaria.")
    texto = raw.strip()
    prefijo = "for(;;);("
    if not texto.startswith(prefijo):
        raise ValueError("Envoltura inesperada.")
    objeto, fin = json.JSONDecoder().raw_decode(texto[len(prefijo):])
    resto = texto[len(prefijo) + fin:].strip()
    if not re.fullmatch(r"\)\s*(?:<!--[\s\S]*?-->\s*)?", resto):
        raise ValueError("Contenido inesperado tras respuesta.")
    if objeto.get("success") is not True:
        raise ValueError("La fuente informó error.")
    try:
        acciones = objeto["response"]["resultado"]["A"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Falta grupo de acciones.") from exc
    if not isinstance(acciones, list):
        raise ValueError("Grupo de acciones inválido.")
    filas, vistos = [], set()
    for fila in acciones:
        if not isinstance(fila, dict):
            raise ValueError("Fila inválida.")
        emisora, serie, datos = fila.get("cveCorta"), fila.get("cveSerie"), fila.get("datosEstadistica")
        if not isinstance(emisora, str) or not emisora.strip() or not isinstance(serie, str) or not serie.strip() or not isinstance(datos, dict):
            raise ValueError("Fila incompleta.")
        par = (emisora.strip(), serie.strip())
        if par in vistos:
            raise ValueError("Par duplicado; requiere revisión.")
        vistos.add(par)
        ppp = _precio(datos.get("ppp"))
        filas.append({"emisora": par[0], "serie": par[1], "ppp": ppp,
                      "estado_ppp": "OBSERVADO_NO_VALIDADO" if ppp is not None else "NO_DISPONIBLE_O_INVALIDO",
                      "ultimo": _precio(datos.get("precioUltimoHecho")),
                      "fecha_fuente": datos.get("fecha"), "hora_fuente": datos.get("hora"),
                      "observado_en": observado_en.isoformat()})
    return filas
