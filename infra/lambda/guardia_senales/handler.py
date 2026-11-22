"""Lambda aislada para auditar elegibilidad; no genera señales ni escribe datos."""
import collections
import csv
import io
import os
import hashlib
from datetime import date, timedelta
from prisma.domain.calendario_bmv import FERIADOS_BMV as FERIADOS, ultimas_sesiones

try:
    from capturas_seguras import manifiesto, captura
except ImportError:
    from infra.capturas_seguras import manifiesto, captura

try:
    from elegibilidad_senales import evaluar_ventanas
except ImportError:
    from prisma.domain.elegibilidad_senales import evaluar_ventanas

try:
    from auditar_boletin_diario import auditar as auditar_boletin
except ImportError:
    from scripts.auditar_boletin_diario import auditar as auditar_boletin

EMISORAS_ADMITIDAS = frozenset({"AMX", "FEMSA", "GFNORTE", "GMEXICO", "WALMEX"})


def sesiones(corte):
    return ultimas_sesiones(corte, 21)


def ejecutar(evento):
    if not isinstance(evento, dict) or set(evento) != {"fecha", "emisoras", "filas"}:
        raise ValueError("Evento inválido.")
    nombres, filas = evento["emisoras"], evento["filas"]
    if (not isinstance(nombres, list) or not nombres or len(nombres) > 5
            or not all(isinstance(x, str) and x in EMISORAS_ADMITIDAS for x in nombres)
            or len(nombres) != len(set(nombres))):
        raise ValueError("Emisoras inválidas.")
    if not isinstance(filas, list) or len(filas) > 1000 or any(not isinstance(x, dict) for x in filas):
        raise ValueError("Filas inválidas.")
    fechas = sesiones(evento["fecha"])
    return {
        "fecha": evento["fecha"], "inicio_ventana": fechas[0], "fin_ventana": fechas[-1],
        "evaluacion": evaluar_ventanas(filas, fechas, nombres),
        "origen": "FILAS_DECLARADAS_NO_VERIFICADAS",
        "emision": "NO_HABILITADA",
        "limitacion": "Solo se revisan metadatos declarados; no se verifican documentos ni modelos.",
    }


def _leer_s3(s3, bucket, key, max_bytes):
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except Exception as exc:
        codigo = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if codigo in ("NoSuchKey", "404", "NotFound"):
            return None
        raise
    if obj.get("ContentLength", 0) > max_bytes:
        raise ValueError("Objeto demasiado grande.")
    raw = obj["Body"].read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Objeto demasiado grande.")
    return raw


def ejecutar_s3(evento, s3, bucket):
    """Lee Silver y Bronze existentes; no acepta fuentes arbitrarias ni escribe S3."""
    if (not isinstance(evento, dict) or set(evento) != {"fecha", "modo"}
            or evento["modo"] != "auditoria_s3"
            or bucket != "prisma-bmv-datalake-tunombre-2026"):
        raise ValueError("Evento o fuente no admitida.")
    fechas = sesiones(evento["fecha"])
    nombres = sorted(EMISORAS_ADMITIDAS)
    filas, resumen = [], collections.Counter()
    columnas = {"fecha", "emisora", "serie", "estado_captura", "ppp_bmv_mxn", "sha256_boletin", "url_fuente"}
    for fecha in fechas:
        dia = date.fromisoformat(fecha)
        silver_key = f"silver/precios_ppp/{dia:%Y/%m}/ppp_15_emisoras_{dia:%Y%m%d}.csv"
        silver = _leer_s3(s3, bucket, silver_key, 1_000_000)
        publicacion = manifiesto(s3, bucket, fecha, opcional=True)
        if publicacion is not None:
            _, _, seguro = captura(s3, bucket, publicacion)
            # Dos históricos incompatibles requieren conciliación, no prioridad silenciosa.
            if silver is not None and silver != seguro:
                raise ValueError("Silver legado y seguro en conflicto")
            silver = seguro
            resumen["CAPTURA_SEGURA_CONFIRMADA"] += 1
        if silver is None:
            resumen["SILVER_AUSENTE"] += 1
            continue
        lector = csv.DictReader(io.StringIO(silver.decode("utf-8-sig"), newline=""))
        if not columnas.issubset(lector.fieldnames or []):
            raise ValueError("Contrato diario inválido.")
        todas = list(lector)
        if not todas or any(r["fecha"] != fecha for r in todas):
            raise ValueError("Corte diario inválido.")
        diarias = [r.copy() for r in todas if r["emisora"] in EMISORAS_ADMITIDAS]
        verificadas = [r for r in diarias if r["estado_captura"] == "PPP_PUBLICADO_VERIFICADO"]
        if verificadas:
            bronze_key = f"bronze/{dia:%Y/%m}/boletin_{dia:%Y%m%d}.html"
            bronze = _leer_s3(s3, bucket, bronze_key, 1_000_000)
            if publicacion is not None and (bronze is None or hashlib.sha256(bronze).hexdigest() != publicacion["sha256_bronze"]):
                raise ValueError("Bronze no coincide con manifiesto")
            evidencia = {}
            if bronze is not None:
                try:
                    auditoria = auditar_boletin(bronze, diarias, fecha)
                    evidencia = {(r["emisora"], r["serie"]): r["resultado"] for r in auditoria["filas"]}
                except (ValueError, UnicodeError):
                    resumen["BRONZE_INVALIDO"] += 1
            else:
                resumen["BRONZE_AUSENTE"] += 1
            for r in verificadas:
                estado = evidencia.get((r["emisora"], r["serie"]), "EVIDENCIA_NO_VALIDADA")
                resumen[estado] += 1
                if estado != "COINCIDE_PPP_Y_HASH":
                    r["estado_captura"] = "EVIDENCIA_BRONZE_NO_VALIDADA"
        filas.extend(diarias)
    return {
        "fecha": evento["fecha"], "inicio_ventana": fechas[0], "fin_ventana": fechas[-1],
        "evaluacion": evaluar_ventanas(filas, fechas, nombres),
        "resumen_evidencia": dict(resumen), "origen": "SILVER_DIARIO_Y_BRONZE_S3",
        "emision": "NO_HABILITADA",
        "limitacion": "Coincidir con Bronze conservado no valida autenticidad independiente, ajustes, modelos ni derechos.",
    }


def lambda_handler(event, context):
    if isinstance(event, dict) and event.get("modo") == "auditoria_s3":
        import boto3
        return ejecutar_s3(event, boto3.client("s3"), os.environ.get("FUENTE_BUCKET"))
    return ejecutar(event)
