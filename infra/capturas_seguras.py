"""Lectura acotada de publicaciones inmutables; sin caché ni escrituras."""
import csv
import hashlib
import io
import json
import re
from datetime import date

PREFIJO = "silver/capturas_seguras/"


def leer(s3, bucket, key, limite, opcional=False):
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except Exception as exc:
        if opcional and getattr(exc, "response", {}).get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    try:
        raw = obj["Body"].read(limite + 1)
    finally:
        obj["Body"].close()
    if len(raw) > limite:
        raise ValueError("Objeto demasiado grande")
    return obj, raw


def clave(fecha):
    dia = date.fromisoformat(fecha)
    if dia.isoformat() != fecha:
        raise ValueError("Fecha no canónica")
    return f"{PREFIJO}{dia:%Y/%m}/captura_{dia:%Y%m%d}.json"


def manifiesto(s3, bucket, fecha, opcional=False):
    resultado = leer(s3, bucket, clave(fecha), 16_384, opcional)
    if resultado is None:
        return None
    dato = json.loads(resultado[1])
    dia = date.fromisoformat(fecha)
    campos = {"version", "fecha", "bronze", "silver", "sha256_bronze", "sha256_silver", "guardia"}
    if (not isinstance(dato, dict) or set(dato) != campos or type(dato["version"]) is not int
            or dato["version"] != 1 or dato["fecha"] != fecha
            or dato["bronze"] != f"bronze/{dia:%Y/%m}/boletin_{dia:%Y%m%d}.html"
            or dato["silver"] != f"silver/recolector_seguro/precios_ppp/{dia:%Y/%m}/ppp_15_emisoras_{dia:%Y%m%d}.csv"
            or dato["guardia"] != "COMPLETADA_SIN_EMISION"
            or any(not isinstance(dato[c], str) or not re.fullmatch(r"[0-9a-f]{64}", dato[c])
                   for c in ("sha256_bronze", "sha256_silver"))):
        raise ValueError("Manifiesto inválido")
    return dato


def captura(s3, bucket, dato):
    obj, raw = leer(s3, bucket, dato["silver"], 1_000_000)
    if hashlib.sha256(raw).hexdigest() != dato["sha256_silver"]:
        raise ValueError("Silver no coincide con manifiesto")
    lector = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if not {"fecha", "emisora", "serie", "estado_captura", "ppp_bmv_mxn", "sha256_boletin"}.issubset(lector.fieldnames or []):
        raise ValueError("Contrato de captura inválido")
    filas = list(lector)
    if (not filas or any(r["fecha"] != dato["fecha"] or not r["emisora"] or not r["serie"]
                         or r["sha256_boletin"] != dato["sha256_bronze"] for r in filas)
            or len({(r["emisora"], r["serie"]) for r in filas}) != len(filas)):
        raise ValueError("Captura inconsistente o duplicada")
    return obj, filas, raw


def pagina(s3, bucket, mes, limite=20, despues=None):
    """Cursor por clave, no token S3 arbitrario. Una página no es todo el historial."""
    if not isinstance(mes, str) or not re.fullmatch(r"\d{4}-\d{2}", mes):
        raise ValueError("Mes inválido")
    date.fromisoformat(mes + "-01")
    if type(limite) is not int or not 1 <= limite <= 31:
        raise ValueError("Límite fuera de 1..31")
    prefix = PREFIJO + mes.replace("-", "/") + "/"
    args = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": limite}
    if despues is not None:
        if not despues.startswith(mes + "-"):
            raise ValueError("Cursor fuera del mes")
        args["StartAfter"] = clave(despues)
    page = s3.list_objects_v2(**args)
    keys = [x["Key"] for x in page.get("Contents", [])]
    if len(keys) > limite or keys != sorted(set(keys)):
        raise ValueError("Página duplicada o desordenada")
    fechas = []
    for key in keys:
        m = re.fullmatch(re.escape(prefix) + r"captura_(\d{8})\.json", key)
        if not m:
            raise ValueError("Clave inválida")
        ymd = m[1]
        fecha = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:])).isoformat()
        if clave(fecha) != key or (despues and fecha <= despues):
            raise ValueError("Página fuera del cursor")
        fechas.append(fecha)
    if page.get("IsTruncated") and not fechas:
        raise ValueError("Página truncada vacía")
    return fechas, fechas[-1] if page.get("IsTruncated") else None


def pagina_global(s3, bucket, limite=20, despues=None):
    """Página global ordenada; el cursor es una fecha canónica, nunca un token S3."""
    if type(limite) is not int or not 1 <= limite <= 31:
        raise ValueError("Límite fuera de 1..31")
    args = {"Bucket": bucket, "Prefix": PREFIJO, "MaxKeys": limite}
    if despues is not None:
        args["StartAfter"] = clave(despues)
    page = s3.list_objects_v2(**args)
    keys = [x["Key"] for x in page.get("Contents", [])]
    if len(keys) > limite or keys != sorted(set(keys)):
        raise ValueError("Página duplicada o desordenada")
    fechas = []
    for key in keys:
        m = re.fullmatch(re.escape(PREFIJO) + r"\d{4}/\d{2}/captura_(\d{8})\.json", key)
        if not m:
            raise ValueError("Clave inválida")
        ymd = m[1]
        fecha = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:])).isoformat()
        if clave(fecha) != key or (despues and fecha <= despues):
            raise ValueError("Página fuera del cursor")
        fechas.append(fecha)
    if page.get("IsTruncated") and not fechas:
        raise ValueError("Página truncada vacía")
    return fechas, fechas[-1] if page.get("IsTruncated") else None
