"""API experimental: perfil Cognito y mercado histórico, sin imputaciones."""
import csv
import hashlib
import io
import json
import logging
import math
import os
import re
import statistics
import unicodedata
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone
from infra.capturas_seguras import manifiesto, captura, pagina, pagina_global
from prisma.data.captura_ampliada import extraer as extraer_boletin_ipc
from prisma.data.ipc35_almacen import (
    SECTORES_IPC35_PROVISIONAL,
    SIMBOLOS_YAHOO_IPC35,
    leer_captura_ipc35,
    leer_manifiesto_ipc35,
    pagina_mes_ipc35,
)
from prisma.data.yahoo_secundario import interpretar_cierre
from prisma.domain.catalogo_ipc import catalogo_naftrac_20261117

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
_tabla = None
_s3 = None
_ddb = None
_cognito = None

PLANES = {
    "explorer": ["WALMEX"],
    "professional": ["WALMEX", "GMEXICO", "GFNORTE", "AMX", "FEMSA", "CEMEX",
                     "BIMBO", "GAP", "PE&OLES", "AC", "ASUR", "GFINBUR", "VESTA", "LIVEPOL", "GRUMA"],
    "enterprise": ["WALMEX", "GMEXICO", "GFNORTE", "AMX", "FEMSA", "CEMEX",
                   "BIMBO", "GAP", "PE&OLES", "AC", "ASUR", "GFINBUR", "VESTA", "LIVEPOL", "GRUMA"],
}


def respuesta(status, body):
    return {"statusCode": status, "headers": {"content-type": "application/json", "cache-control": "no-store"},
            "body": json.dumps(body, ensure_ascii=False)}


def _numero(valor):
    try:
        n = float(valor)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _capturas_seguras(s3, bucket, fecha_objetivo=None):
    """Descubre solo manifiestos finales y valida el CSV al que se refieren."""
    if os.environ.get("CAPTURAS_SEGURAS_HABILITADAS") != "true":
        return {}
    if fecha_objetivo is not None:
        dato = manifiesto(s3, bucket, fecha_objetivo, opcional=True)
        if dato is None:
            return {}
        obj, filas, _ = captura(s3, bucket, dato)
        return {fecha_objetivo: (obj, filas)}
    prefix = "silver/capturas_seguras/"
    token, claves = None, []
    for _ in range(20):
        args = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 100}
        if token:
            args["ContinuationToken"] = token
        page = s3.list_objects_v2(**args)
        claves.extend(x["Key"] for x in page.get("Contents", []))
        if len(claves) > 2000:
            raise ValueError("Demasiadas capturas; requiere paginación acotada")
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")
        if not token:
            raise ValueError("Paginación S3 inválida")
    else:
        raise ValueError("Paginación S3 incompleta")
    capturas = {}
    for key in claves:
        m = re.fullmatch(r"silver/capturas_seguras/(\d{4})/(\d{2})/captura_(\d{8})\.json", key)
        if not m:
            raise ValueError("Clave de manifiesto inválida")
        ymd = m.group(3)
        if ymd[:4] != m.group(1) or ymd[4:6] != m.group(2):
            raise ValueError("Ruta de manifiesto inconsistente")
        fecha = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:])).isoformat()
        if fecha in capturas:
            raise ValueError("Manifiestos duplicados")
        if fecha_objetivo is not None and fecha != fecha_objetivo:
            continue
        dato = manifiesto(s3, bucket, fecha)
        obj, filas, _ = captura(s3, bucket, dato)
        capturas[fecha] = (obj, filas)
    return capturas


def _pagina_capturas(evento, s3):
    """Contrato opt-in paginado; nunca aparenta contener todo el historial."""
    q = evento.get("queryStringParameters") or {}
    try:
        if set(q) - {"mes", "limite", "despues"}:
            raise ValueError("Parámetro no admitido")
        mes, limite, despues = q.get("mes"), int(q.get("limite", "20")), q.get("despues")
        # Validación independiente de S3 para distinguir errores del cliente.
        if not isinstance(mes, str) or not re.fullmatch(r"\d{4}-\d{2}", mes):
            raise ValueError()
        date.fromisoformat(mes + "-01")
        if not 1 <= limite <= 31 or (despues and (date.fromisoformat(despues).isoformat() != despues or not despues.startswith(mes + "-"))):
            raise ValueError()
    except (ValueError, TypeError):
        return respuesta(422, {"detail": "Indica mes YYYY-MM, límite 1..31 y cursor ISO del mismo mes."})
    if os.environ.get("CAPTURAS_SEGURAS_HABILITADAS") != "true":
        return respuesta(503, {"detail": "Descubrimiento seguro deshabilitado."})
    try:
        bucket = os.environ["MERCADO_BUCKET"]
        fechas, siguiente = pagina(s3, bucket, mes, limite, despues)
        for fecha in fechas:
            captura(s3, bucket, manifiesto(s3, bucket, fecha))
        return respuesta(200, {"fechas": fechas, "siguiente": siguiente, "mes": mes,
                               "orden": "ascendente", "cobertura": "capturas confirmadas del mes",
                               "solicitudes_s3": {"list": 1, "get": 2 * len(fechas)}})
    except Exception as exc:
        logger.warning("pagina_capturas_fallida tipo=%s", type(exc).__name__)
        return respuesta(503, {"detail": "Página de capturas inválida o no disponible."})


def _leer_mercado(s3, fecha_objetivo=None, paginacion=None, intervalo=None):
    bucket = os.environ.get("MERCADO_BUCKET", "")
    key = os.environ.get("MERCADO_KEY", "")
    if not bucket or not key or s3 is None:
        raise ValueError("Fuente no configurada")
    obj = s3.get_object(Bucket=bucket, Key=key)
    if obj.get("ContentLength", 0) > 10_000_000:
        raise ValueError("Archivo demasiado grande")
    data = obj["Body"].read(10_000_001)
    if len(data) > 10_000_000:
        raise ValueError("Archivo demasiado grande")
    lector = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    requeridas = {"fecha", "emisora", "serie", "estado_captura", "ppp_bmv_mxn"}
    if not requeridas.issubset(lector.fieldnames or []):
        raise ValueError("Contrato de mercado inválido")
    filas = list(lector)
    for fila in filas:
        fila["_procedencia"] = "INSTANTANEA_ESTADO_DECLARADO"
    obj["sha256_instantanea"] = hashlib.sha256(data).hexdigest()
    if paginacion is not None:
        fechas_pagina, siguiente = (pagina_global(s3, bucket, **paginacion)
                                   if os.environ.get("CAPTURAS_SEGURAS_HABILITADAS") == "true" else ([], None))
        capturas = {f: captura(s3, bucket, manifiesto(s3, bucket, f))[:2] for f in fechas_pagina}
        obj["siguiente"] = siguiente
    elif intervalo is not None:
        desde, hasta = intervalo
        desde = desde or min((r["fecha"] for r in filas), default=date.today().isoformat())
        hasta = hasta or date.today().isoformat()
        if (date.fromisoformat(hasta) - date.fromisoformat(desde)).days > 366:
            raise PeriodoExtenso("Selecciona un periodo de hasta 366 días para estadística.")
        capturas = {}
        mes = date.fromisoformat(desde).replace(day=1)
        while mes.isoformat() <= hasta:
            if os.environ.get("CAPTURAS_SEGURAS_HABILITADAS") == "true":
                fechas_mes, siguiente = pagina(s3, bucket, mes.strftime("%Y-%m"), limite=31)
                if siguiente:
                    raise ValueError("Mes con exceso de manifiestos")
                for f in fechas_mes:
                    if desde <= f <= hasta:
                        capturas[f] = captura(s3, bucket, manifiesto(s3, bucket, f))[:2]
            mes = date(mes.year + (mes.month == 12), mes.month % 12 + 1, 1)
        obj["intervalo_consultado"] = {"desde": desde, "hasta": hasta}
    else:
        capturas = _capturas_seguras(s3, bucket, fecha_objetivo)
    fechas_snapshot = {r["fecha"] for r in filas if r["fecha"]}
    for fecha, (_, nuevas) in capturas.items():
        # Nunca reemplazar silenciosamente el histórico de la instantánea.
        if fecha not in fechas_snapshot:
            for fila in nuevas:
                fila["_procedencia"] = "CAPTURA_HASH_VERIFICADO"
            filas.extend(nuevas)
        else:
            anteriores = {(r["emisora"], r["serie"]): r for r in filas if r["fecha"] == fecha}
            for nueva in nuevas:
                anterior = anteriores.get((nueva["emisora"], nueva["serie"]))
                if anterior is None:
                    continue
                if (anterior["estado_captura"] != nueva["estado_captura"]
                        or _numero(anterior.get("ppp_bmv_mxn")) != _numero(nueva.get("ppp_bmv_mxn"))):
                    raise ValueError("Instantánea y captura tienen valores incompatibles")
    fechas = sorted({r["fecha"] for r in filas if r["fecha"]}, reverse=True)
    for f in fechas:
        if date.fromisoformat(f).isoformat() != f:
            raise ValueError("Fecha inválida")
    obj["capturas_seguras"] = capturas
    return obj, filas, fechas


class PeriodoExtenso(ValueError):
    pass


def _parametros_pagina(evento):
    q = evento.get("queryStringParameters") or {}
    if q.get("paginado") != "true":
        return None
    limite = int(q.get("limite", "20"))
    despues = q.get("despues")
    if not 1 <= limite <= 31 or (despues is not None and date.fromisoformat(despues).isoformat() != despues):
        raise ValueError("Página inválida")
    return {"limite": limite, "despues": despues}


def _cobertura_pagina(obj):
    return {"siguiente": obj.get("siguiente"), "sha256_instantanea": obj["sha256_instantanea"],
            "cobertura": "instantánea y página de capturas; consumir hasta siguiente=null",
            "consistencia": "Manifiestos inmutables; repetir recorrido para capturas incorporadas tardíamente."}


def _leer_corte_diario(s3, fecha):
    """Lee Silver diario si existe; solo ausencia comprobada permite respaldo."""
    bucket = os.environ.get("MERCADO_BUCKET", "")
    if not bucket or s3 is None:
        raise ValueError("Fuente no configurada")
    f = date.fromisoformat(fecha)
    if f.isoformat() != fecha:
        raise ValueError("Fecha inválida")
    key = f"silver/precios_ppp/{f:%Y/%m}/ppp_15_emisoras_{f:%Y%m%d}.csv"
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except Exception as exc:
        codigo = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if codigo in ("NoSuchKey", "404", "NotFound"):
            return None
        raise
    if obj.get("ContentLength", 0) > 1_000_000:
        raise ValueError("Corte diario demasiado grande")
    data = obj["Body"].read(1_000_001)
    if len(data) > 1_000_000:
        raise ValueError("Corte diario demasiado grande")
    lector = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    requeridas = {"fecha", "emisora", "serie", "estado_captura", "ppp_bmv_mxn"}
    if not requeridas.issubset(lector.fieldnames or []):
        raise ValueError("Contrato diario inválido")
    filas = list(lector)
    if not filas or any(r["fecha"] != fecha or not r["emisora"] or not r["serie"] for r in filas):
        raise ValueError("Corte diario sin fecha o clave exacta")
    claves = [(r["emisora"], r["serie"]) for r in filas]
    if len(set(claves)) != len(claves):
        raise ValueError("Claves diarias duplicadas")
    return obj, filas, key


def _captura_iniciada(s3, fecha):
    if os.environ.get("CAPTURAS_SEGURAS_HABILITADAS") != "true":
        return False
    f = date.fromisoformat(fecha)
    key = f"silver/capturas_en_curso/{f:%Y/%m}/captura_{f:%Y%m%d}.json"
    try:
        obj = s3.get_object(Bucket=os.environ["MERCADO_BUCKET"], Key=key)
    except Exception as exc:
        if getattr(exc, "response", {}).get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
            return False
        raise
    raw = obj["Body"].read(1025)
    if len(raw) > 1024 or json.loads(raw) != {"version": 1, "fecha": fecha}:
        raise ValueError("Marcador de captura inválido")
    return True


class _CatalogoProvisionalLectura:
    """Envoltorio de solo lectura para proyectar los 35 pares provisionales sobre un boletín Bronze."""

    def __init__(self, base):
        self.base = base
        self.version = base.version

    def en_corte(self, _fecha):
        return self.base.componentes


def _cargar_candidatos_ipc35(s3, fecha):
    """Lee Bronze HTML del corte (si existe) para extraer los 20 candidatos provisionales sin imputación."""
    catalogo = catalogo_naftrac_20261117()
    candidatos = [c for c in catalogo.componentes if c.origen == "CANDIDATO_20"]
    dia = date.fromisoformat(fecha)
    bucket = os.environ.get("MERCADO_BUCKET", "")
    bronze_key = f"bronze/{dia:%Y/%m}/boletin_{dia:%Y%m%d}.html"
    bronze_raw = None
    try:
        obj = s3.get_object(Bucket=bucket, Key=bronze_key)
        if obj.get("ContentLength", 0) <= 1_500_000:
            raw = obj["Body"].read(1_500_001)
            if len(raw) <= 1_500_000:
                bronze_raw = raw
    except Exception as exc:
        codigo = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if codigo not in ("NoSuchKey", "404", "NotFound"):
            logger.warning("lectura_bronze_ipc35_fallida tipo=%s", type(exc).__name__)

    if bronze_raw is None:
        filas = [{
            "emisora": c.emisora,
            "serie": c.serie,
            "sector": SECTORES_IPC35_PROVISIONAL.get(c.emisora, "IPC provisional (sin clasificar)"),
            "estado_captura": "BOLETIN_BRONZE_NO_DISPONIBLE",
            "ppp_bmv_mxn": None,
            "anterior_bmv_mxn": None,
            "variacion_pct": None,
            "origen_catalogo": c.origen,
            "alias_blackrock": c.blackrock,
            "estado_composicion": c.estado_composicion,
            "estado_mapeo": c.estado_mapeo,
            "elegible_senales": False,
            "fuente_fila": "SIN_BRONZE_SESION",
        } for c in candidatos]
        return catalogo, filas, False, None

    sha_bronze = hashlib.sha256(bronze_raw).hexdigest()
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{dia:%Y%m%d}.html"
    extraidos = {}
    parse_valido = True
    try:
        resultado = extraer_boletin_ipc(bronze_raw, dia, _CatalogoProvisionalLectura(catalogo), url)
        extraidos = {(r["emisora_propuesta"], r["serie_propuesta"]): r for r in resultado["filas"]}
    except (ValueError, UnicodeError):
        parse_valido = False

    filas = []
    for c in candidatos:
        fila_ext = extraidos.get((c.emisora, c.serie))
        if not parse_valido or fila_ext is None:
            estado, ppp, ant, var = "CONFLICTO_O_FILA_INVALIDA", None, None, None
        elif fila_ext["estado_captura"] == "PPP_OBSERVADO_MAPEO_PROVISIONAL":
            ppp = _numero(fila_ext.get("ppp_bmv_mxn"))
            ant = _numero(fila_ext.get("anterior_bmv_mxn"))
            if ppp is not None and ppp > 0:
                estado = "PPP_OBSERVADO_MAPEO_PROVISIONAL"
                var = round((ppp / ant - 1.0) * 100.0, 2) if (ant is not None and ant > 0) else None
            else:
                estado, ppp, ant, var = "CONFLICTO_O_FILA_INVALIDA", None, None, None
        elif fila_ext["estado_captura"] == "NO_ENCONTRADO_EN_TABLAS":
            estado, ppp, ant, var = "NO_ENCONTRADO_EN_TABLAS_BOLETIN", None, None, None
        else:
            estado, ppp, ant, var = "CONFLICTO_O_FILA_INVALIDA", None, None, None
        filas.append({
            "emisora": c.emisora,
            "serie": c.serie,
            "sector": SECTORES_IPC35_PROVISIONAL.get(c.emisora, "IPC provisional (sin clasificar)"),
            "estado_captura": estado,
            "ppp_bmv_mxn": ppp,
            "anterior_bmv_mxn": ant,
            "variacion_pct": var,
            "origen_catalogo": c.origen,
            "alias_blackrock": c.blackrock,
            "estado_composicion": c.estado_composicion,
            "estado_mapeo": c.estado_mapeo,
            "elegible_senales": False,
            "fuente_fila": "BRONZE_HTML_PROVISIONAL",
        })
    return catalogo, filas, True, sha_bronze


def _mercado(evento, s3):
    q = evento.get("queryStringParameters") or {}
    if evento.get("routeKey") == "GET /api/mercado/fechas" and q.get("mes") is not None:
        return _pagina_capturas(evento, s3)
    universo = q.get("universo")
    if evento.get("routeKey") == "GET /api/mercado/resumen" and universo not in (None, "", "base_15", "ipc35_provisional"):
        return respuesta(422, {"detail": "Universo no admitido; usa base_15 o ipc35_provisional."})
    es_ipc35 = evento.get("routeKey") == "GET /api/mercado/resumen" and universo == "ipc35_provisional"
    try:
        paginacion = _parametros_pagina(evento)
    except (ValueError, TypeError):
        return respuesta(422, {"detail": "Página inválida; límite 1..31 y cursor ISO."})
    try:
        objetivo = (q.get("fecha") if evento.get("routeKey") != "GET /api/mercado/fechas" else None)
        obj, filas, fechas = _leer_mercado(s3, objetivo, paginacion=paginacion)
    except Exception as exc:
        logger.warning("lectura_mercado_fallida tipo=%s", type(exc).__name__)
        return respuesta(503, {"detail": "Fuente de mercado temporalmente no disponible."})
    if evento.get("routeKey") == "GET /api/mercado/fechas":
        if paginacion is not None:
            return respuesta(200, {"fechas": fechas, **_cobertura_pagina(obj)})
        return respuesta(200, fechas)
    fecha = q.get("fecha") or (fechas[0] if fechas else None)
    if not fecha or fecha not in fechas:
        return respuesta(404, {"detail": "No hay datos para la fecha solicitada."})
    tipo_fuente = "instantanea_s3"
    try:
        captura = obj.get("capturas_seguras", {}).get(fecha)
        diario = (*captura, None) if captura else _leer_corte_diario(s3, fecha)
        # Comprobar después de leer el diario cierra la carrera con el inicio
        # concurrente: el marcador se escribe antes que cualquier Silver nuevo.
        if not captura and _captura_iniciada(s3, fecha):
            raise ValueError("Captura iniciada aún no confirmada")
        if diario is not None:
            obj, filas, _ = diario
            tipo_fuente = "silver_diario_s3"
    except Exception as exc:
        logger.warning("lectura_diaria_fallida tipo=%s", type(exc).__name__)
        return respuesta(503, {"detail": "Corte diario temporalmente no disponible o inválido."})
    cotizaciones = []
    claves = set()
    for r in filas:
        if r["fecha"] != fecha or r["emisora"] not in PLANES["professional"]:
            continue
        clave = (r["emisora"], r["serie"])
        if clave in claves:
            return respuesta(503, {"detail": "La sesión contiene claves duplicadas."})
        claves.add(clave)
        verificado = r["estado_captura"] == "PPP_PUBLICADO_VERIFICADO"
        precio = _numero(r.get("ppp_bmv_mxn")) if verificado else None
        if precio is not None and precio <= 0:
            precio = None
        entrada = {
            "emisora": r["emisora"], "serie": r["serie"],
            "sector": r.get("sector_economico", ""), "estado_captura": r["estado_captura"],
            "ppp_bmv_mxn": precio,
            "anterior_bmv_mxn": _numero(r.get("anterior_bmv_mxn")) if verificado else None,
            "variacion_pct": _numero(r.get("variacion_ppp_vs_anterior_pct")) if precio is not None else None,
        }
        if es_ipc35:
            entrada.update({
                "origen_catalogo": "ACTUAL_15",
                "estado_composicion": "PROVISIONAL_NO_OFICIAL",
                "estado_mapeo": "PANEL_BASE_15",
                "elegible_senales": False,
                "fuente_fila": "SILVER_BASE_15",
            })
        cotizaciones.append(entrada)
    if not cotizaciones:
        return respuesta(404, {"detail": "No hay cotizaciones disponibles para la sesión."})
    verificadas = [r for r in cotizaciones if r["ppp_bmv_mxn"] is not None]
    variaciones = [r for r in verificadas if r["variacion_pct"] is not None]
    alza = max(variaciones, key=lambda r: r["variacion_pct"], default=None)
    baja = min(variaciones, key=lambda r: r["variacion_pct"], default=None)
    catalogo_meta = None
    provisionales_con_ppp = 0
    total_base = len(cotizaciones)
    if es_ipc35:
        catalogo, filas_20, bronze_ok, sha_bronze = _cargar_candidatos_ipc35(s3, fecha)
        for fila_c in filas_20:
            clave_c = (fila_c["emisora"], fila_c["serie"])
            if clave_c in claves:
                continue
            claves.add(clave_c)
            cotizaciones.append(fila_c)
        provisionales_con_ppp = sum(1 for r in filas_20 if r["ppp_bmv_mxn"] is not None)
        catalogo_meta = {
            "version": catalogo.version,
            "fecha_corte_catalogo": catalogo.fecha_corte.isoformat(),
            "estado_composicion": "PROVISIONAL_NO_OFICIAL",
            "componentes_totales": len(catalogo.componentes),
            "bronze_disponible": bronze_ok,
            "sha256_bronze": sha_bronze,
            "senales_habilitadas": False,
            "alias_pendientes": ["RA -> R / A", "LIVEPOLC.1 -> LIVEPOL / C-1"],
            "advertencia": (
                "Composición provisional NAFTRAC de un solo corte; los huecos no se imputan "
                "y las señales permanecen bloqueadas."
            ),
        }
    total_ausentes = sum(1 for r in cotizaciones if r["ppp_bmv_mxn"] is None)
    kpis = {
        "fecha": fecha, "total_emisoras": len(cotizaciones),
        "total_verificadas": len(verificadas), "total_ausentes": total_ausentes,
        "conteo_alzas": sum(r["variacion_pct"] > 0 for r in variaciones) if variaciones else None,
        "conteo_bajas": sum(r["variacion_pct"] < 0 for r in variaciones) if variaciones else None,
        "total_con_variacion": len(variaciones),
        "top_alza_ticker": alza["emisora"] if alza else None,
        "top_alza_pct": alza["variacion_pct"] if alza else None,
        "top_baja_ticker": baja["emisora"] if baja else None,
        "top_baja_pct": baja["variacion_pct"] if baja else None,
    }
    if es_ipc35:
        kpis.update({
            "universo": "ipc35_provisional",
            "total_base_15": total_base,
            "total_candidatos_20": len(cotizaciones) - total_base,
            "total_provisionales_con_ppp": provisionales_con_ppp,
        })
    cuerpo = {
        "fecha": fecha, "kpis": kpis, "cotizaciones": cotizaciones,
        "fuente": {
            "tipo": tipo_fuente,
            "actualizada": str(obj.get("LastModified", "")),
            "cobertura": (
                "base 15 + 20 candidatos provisionales NAFTRAC (huecos sin imputación; sin señales)"
                if es_ipc35 else "filas disponibles; no acredita universo completo"
            ),
        },
    }
    if catalogo_meta is not None:
        cuerpo["catalogo_ipc"] = catalogo_meta
    return respuesta(200, cuerpo)


def _sectores(evento, s3):
    """Agrega únicamente variaciones disponibles de la misma instantánea."""
    q_limpio = {k: v for k, v in (evento.get("queryStringParameters") or {}).items() if k != "universo"}
    mercado = _mercado({**evento, "routeKey": "GET /api/mercado/resumen", "queryStringParameters": q_limpio}, s3)
    if mercado["statusCode"] != 200:
        return mercado
    data = json.loads(mercado["body"])
    grupos = {}
    for fila in data["cotizaciones"]:
        nombre = fila["sector"].strip() if isinstance(fila["sector"], str) else ""
        nombre = nombre or "Sin sector identificado"
        grupo = grupos.setdefault(nombre, {"sector": nombre, "emisoras": 0,
                                            "con_ppp": 0, "huecos": 0,
                                            "_variaciones": []})
        grupo["emisoras"] += 1
        if fila["ppp_bmv_mxn"] is not None:
            grupo["con_ppp"] += 1
        else:
            grupo["huecos"] += 1
        if fila["variacion_pct"] is not None:
            grupo["_variaciones"].append(fila["variacion_pct"])
    sectores = []
    for grupo in grupos.values():
        variaciones = grupo.pop("_variaciones")
        grupo["con_variacion"] = len(variaciones)
        grupo["variacion_media_pct"] = statistics.mean(variaciones) if variaciones else None
        sectores.append(grupo)
    sectores.sort(key=lambda x: (x["variacion_media_pct"] is None,
                                  -(x["variacion_media_pct"] or 0), x["sector"]))
    return respuesta(200, {"fecha": data["fecha"], "kpis": data["kpis"], "sectores": sectores,
                           "fuente": data["fuente"]})


def _serie(evento, s3, permitidas):
    ruta = evento["routeKey"]
    emisora = "WALMEX" if ruta == "GET /api/serie/walmex" else (evento.get("queryStringParameters") or {}).get("emisora", "")
    if not emisora:
        return respuesta(422, {"detail": "Indica la emisora."})
    if emisora not in permitidas:
        return respuesta(403, {"detail": "La emisora no está incluida en tu plan."})
    try:
        paginacion = _parametros_pagina(evento)
    except (ValueError, TypeError):
        return respuesta(422, {"detail": "Página inválida; límite 1..31 y cursor ISO."})
    try:
        obj, filas, _ = _leer_mercado(s3, paginacion=paginacion)
        filas = sorted((r for r in filas if r["emisora"] == emisora), key=lambda r: r["fecha"])
        if len({r["fecha"] for r in filas}) != len(filas):
            raise ValueError("Serie ambigua o duplicada")
    except Exception as exc:
        logger.warning("lectura_serie_fallida tipo=%s", type(exc).__name__)
        return respuesta(503, {"detail": "Serie temporal no disponible."})
    if not filas:
        return respuesta(404, {"detail": "Sin serie para la emisora."})
    puntos = []
    for r in filas:
        valor = _numero(r["ppp_bmv_mxn"]) if r["estado_captura"] == "PPP_PUBLICADO_VERIFICADO" else None
        puntos.append({"fecha": r["fecha"], "ppp": valor if valor is not None and valor > 0 else None,
                       "estado": r["estado_captura"]})
    if ruta == "GET /api/serie/walmex" and paginacion is None:
        return respuesta(200, puntos)
    return respuesta(200, {"emisora": emisora, "sector": filas[-1].get("sector_economico", ""),
                            "serie": filas[-1]["serie"], "puntos": puntos,
                            **(_cobertura_pagina(obj) if paginacion is not None else {}),
                           "fuente": {"tipo": "instantanea_y_capturas_seguras_s3" if obj.get("capturas_seguras") else "instantanea_s3",
                                      "actualizada": str(obj.get("LastModified", "")),
                                       "cobertura": "filas disponibles; no acredita historial completo"}})


def _cuantil(valores, q):
    if not valores:
        return None
    indice = (len(valores) - 1) * q
    i = int(indice)
    return valores[i] + (valores[min(i + 1, len(valores) - 1)] - valores[i]) * (indice - i)


def _medidas(valores, total, variable):
    valores = sorted(valores)
    n = len(valores)
    media = statistics.mean(valores) if n else None
    de = statistics.stdev(valores) if n > 1 else None
    q1, q3 = _cuantil(valores, .25), _cuantil(valores, .75)
    asimetria = (n / ((n - 1) * (n - 2)) * sum(((x - media) / de) ** 3 for x in valores)
                 if n >= 3 and de and de > 0 else None)
    curtosis = (n * (n + 1) / ((n - 1) * (n - 2) * (n - 3)) *
                sum(((x - media) / de) ** 4 for x in valores) -
                3 * (n - 1) ** 2 / ((n - 2) * (n - 3))
                if n >= 4 and de and de > 0 else None)
    return {"agrupacion": "total", "grupo": None, "variable": variable,
            "n_total": total, "n_valido": n, "faltantes": total - n,
            "faltantes_pct": (total - n) * 100 / total if total else None,
            "media": media, "mediana": statistics.median(valores) if n else None,
            "minimo": valores[0] if n else None, "maximo": valores[-1] if n else None,
            "desviacion_estandar_muestral": de, "q1": q1, "q3": q3,
            "rango_intercuartilico": q3 - q1 if n else None,
            "asimetria": asimetria, "exceso_curtosis": curtosis}


def _histograma(valores):
    if not valores:
        return []
    valores = sorted(valores)
    minimo, maximo, n = valores[0], valores[-1], len(valores)
    if minimo == maximo:
        return [{"desde": minimo - .5, "hasta": maximo + .5, "n": n}]
    ancho_fd = 2 * (_cuantil(valores, .75) - _cuantil(valores, .25)) / n ** (1 / 3)
    sturges = math.ceil(math.log2(n) + 1)
    bins = max(sturges, math.ceil((maximo - minimo) / ancho_fd)) if ancho_fd > 0 else sturges
    # Un límite evita consumo excesivo en distribuciones degeneradas.
    bins = min(bins, 1000)
    ancho = (maximo - minimo) / bins
    conteos = [0] * bins
    for valor in valores:
        conteos[min(int((valor - minimo) / ancho), bins - 1)] += 1
    return [{"desde": minimo + i * ancho, "hasta": minimo + (i + 1) * ancho, "n": conteos[i]}
            for i in range(bins)]


def _estadistica_ipc35(s3, emisora, desde, hasta, permitidas):
    catalogo = catalogo_naftrac_20261117()
    por_em = {c.emisora: c for c in catalogo.componentes}
    comp = por_em.get(emisora)
    if comp is None:
        return respuesta(404, {"detail": "Emisora fuera del catálogo provisional de 35."})
    if comp.origen == "ACTUAL_15" and emisora not in permitidas:
        return respuesta(403, {"detail": "La emisora no está incluida en tu plan."})
    bucket = os.environ.get("MERCADO_BUCKET", "")
    if not bucket or s3 is None:
        return respuesta(503, {"detail": "Fuente IPC provisional no configurada."})
    desde_eff = desde or "2026-10-20"
    hasta_eff = hasta or date.today().isoformat()
    if (date.fromisoformat(hasta_eff) - date.fromisoformat(desde_eff)).days > 366:
        return respuesta(422, {"detail": "Selecciona un periodo de hasta 366 días para estadística."})
    filas = []
    manifiestos_leidos = 0
    mes = date.fromisoformat(desde_eff).replace(day=1)
    while mes.isoformat() <= hasta_eff:
        for f in pagina_mes_ipc35(s3, bucket, mes.strftime("%Y-%m")):
            if desde_eff <= f <= hasta_eff:
                man = leer_manifiesto_ipc35(s3, bucket, f)
                _, rows = leer_captura_ipc35(s3, bucket, man)
                manifiestos_leidos += 1
                for r in rows:
                    if r["emisora"] == emisora:
                        filas.append(r)
        mes = date(mes.year + (mes.month == 12), mes.month % 12 + 1, 1)
    filas.sort(key=lambda r: r["fecha"])
    if len({r["fecha"] for r in filas}) != len(filas):
        return respuesta(503, {"detail": "Serie IPC-35 ambigua o duplicada."})
    observadas = []
    for fila in filas:
        ppp = _numero(fila.get("ppp_bmv_mxn"))
        if fila["estado_captura"] == "PPP_OBSERVADO_MAPEO_PROVISIONAL" and ppp is not None and ppp > 0:
            observadas.append({
                "fecha": fila["fecha"], "emisora": emisora, "serie": fila["serie"],
                "ppp_bmv_mxn": ppp,
                "variacion_ppp_vs_anterior_pct": _numero(fila.get("variacion_ppp_vs_anterior_pct")),
            })
    precios = [r["ppp_bmv_mxn"] for r in observadas]
    variaciones = [r["variacion_ppp_vs_anterior_pct"] for r in observadas
                   if r["variacion_ppp_vs_anterior_pct"] is not None]
    estados = dict(Counter(r.get("estado_captura") or "SIN_ESTADO" for r in filas))
    direcciones = [
        ("alza", sum(v > 0 for v in variaciones)),
        ("baja", sum(v < 0 for v in variaciones)),
        ("sin_cambio", sum(v == 0 for v in variaciones)),
    ]
    reporte = {
        "metodologia": {
            "fuentes": ["almacenamiento versionado silver/ipc35_provisional/ (manifiestos SHA-256)"],
            "panel": "no disponible",
            "universo": "ipc35_provisional",
            "estado_composicion": "PROVISIONAL_NO_OFICIAL",
            "origen_catalogo": comp.origen,
            "alias_blackrock": comp.blackrock,
            "version_catalogo": catalogo.version,
            "advertencia": (
                "Estadística descriptiva sobre almacenamiento provisional IPC-35 (tablas parciales RSS); "
                "los huecos no se imputan, los ajustes corporativos no están validados y las señales siguen bloqueadas."
            ),
            "filtros": {"emisora": emisora, "desde": desde_eff, "hasta": hasta_eff, "universo": "ipc35_provisional"},
            "intervalo_consultado": {"desde": desde_eff, "hasta": hasta_eff},
            "procedencia_filas": {"SILVER_IPC35_HASH_VERIFICADO": len(filas)},
            "manifiestos_ipc35_leidos": manifiestos_leidos,
            "ajustes_corporativos": "NO_VALIDADOS",
            "inferencia_habilitada": False,
            "alcance_verificacion": "Hash de CSV IPC-35 y HTML Bronze validado contra manifiesto inmutable; no certifica composición oficial IPC.",
        },
        "cobertura_historico": {
            "registros": len(filas),
            "fecha_inicial": filas[0]["fecha"] if filas else None,
            "fecha_final": filas[-1]["fecha"] if filas else None,
            "estados": estados,
        },
        "cobertura_panel": None,
        "estadisticas_panel_verificado": [],
        "correlaciones_panel": [],
        "estadisticas_historico_verificado": [
            _medidas(precios, len(filas), "ppp_bmv_mxn"),
            _medidas(variaciones, len(filas), "variacion_ppp_vs_anterior_pct"),
        ],
        "frecuencias_direccion": [
            {"agrupacion": "total", "grupo": None, "direccion": d, "n": n,
             "porcentaje": n * 100 / len(variaciones) if variaciones else None}
            for d, n in direcciones
        ],
        "distribucion_variacion_pct": {
            "variable": "variacion_ppp_vs_anterior_pct",
            "n": len(variaciones),
            "histograma": _histograma(variaciones),
            "cajas": [],
        },
        "serie_historica_verificada": observadas,
    }
    return respuesta(200, reporte)


def _estadistica(evento, s3, permitidas):
    params = evento.get("queryStringParameters") or {}
    emisora = params.get("emisora", "")
    universo = params.get("universo")
    if universo not in (None, "", "base_15", "ipc35_provisional"):
        return respuesta(422, {"detail": "Universo no admitido; usa base_15 o ipc35_provisional."})
    if not emisora:
        return respuesta(422, {"detail": "Indica la emisora."})
    desde, hasta = params.get("desde") or None, params.get("hasta") or None
    try:
        for f in (desde, hasta):
            if f and date.fromisoformat(f).isoformat() != f:
                raise ValueError()
        if desde and hasta and desde > hasta:
            raise ValueError()
    except (TypeError, ValueError):
        return respuesta(422, {"detail": "Periodo inválido; usa fechas ISO en orden."})
    if universo == "ipc35_provisional":
        try:
            return _estadistica_ipc35(s3, emisora, desde, hasta, permitidas)
        except Exception as exc:
            logger.warning("estadistica_ipc35_fallida tipo=%s", type(exc).__name__)
            return respuesta(503, {"detail": "Estadística IPC provisional temporalmente no disponible."})
    if emisora not in permitidas:
        return respuesta(403, {"detail": "La emisora no está incluida en tu plan."})
    try:
        obj, filas, _ = _leer_mercado(s3, intervalo=(desde, hasta))
        desde = obj["intervalo_consultado"]["desde"]
        hasta = obj["intervalo_consultado"]["hasta"]
        filas = sorted((r for r in filas if r["emisora"] == emisora and
                        (not desde or r["fecha"] >= desde) and (not hasta or r["fecha"] <= hasta)),
                       key=lambda r: r["fecha"])
        if len({r["fecha"] for r in filas}) != len(filas):
            raise ValueError("Serie ambigua o duplicada")
        verificadas = []
        for fila in filas:
            ppp = _numero(fila.get("ppp_bmv_mxn"))
            if fila["estado_captura"] == "PPP_PUBLICADO_VERIFICADO" and ppp is not None and ppp > 0:
                verificadas.append({"fecha": fila["fecha"], "emisora": emisora, "serie": fila["serie"],
                                    "ppp_bmv_mxn": ppp,
                                    "variacion_ppp_vs_anterior_pct": _numero(fila.get("variacion_ppp_vs_anterior_pct"))})
        precios = [r["ppp_bmv_mxn"] for r in verificadas]
        variaciones = [r["variacion_ppp_vs_anterior_pct"] for r in verificadas
                       if r["variacion_ppp_vs_anterior_pct"] is not None]
        estados = dict(Counter(r.get("estado_captura") or "SIN_ESTADO" for r in filas))
        direcciones = [("alza", sum(v > 0 for v in variaciones)),
                       ("baja", sum(v < 0 for v in variaciones)),
                       ("sin_cambio", sum(v == 0 for v in variaciones))]
        reporte = {
            "metodologia": {"fuentes": (["instantánea S3 reciente", "capturas seguras S3"] if obj.get("capturas_seguras")
                                         else ["instantánea S3 reciente"]), "panel": "no disponible",
                            "advertencia": "Solo filas disponibles, no historial completo; el panel ajustado no está conectado.",
                             "filtros": {"emisora": emisora, "desde": desde, "hasta": hasta},
                             "intervalo_consultado": obj.get("intervalo_consultado"),
                            "actualizada": str(obj.get("LastModified", "")),
                            "procedencia_filas": dict(Counter(r.get("_procedencia", "NO_DETERMINADA") for r in filas)),
                            "sha256_instantanea": obj.get("sha256_instantanea"),
                            "ajustes_corporativos": "NO_VALIDADOS",
                            "inferencia_habilitada": False,
                            "alcance_verificacion": "Hash de captura contra manifiesto; estado declarado para instantánea. No certifica autenticidad independiente."},
            "cobertura_historico": {"registros": len(filas), "fecha_inicial": filas[0]["fecha"] if filas else None,
                                   "fecha_final": filas[-1]["fecha"] if filas else None, "estados": estados},
            "cobertura_panel": None, "estadisticas_panel_verificado": [], "correlaciones_panel": [],
            "estadisticas_historico_verificado": [
                _medidas(precios, len(verificadas), "ppp_bmv_mxn"),
                _medidas(variaciones, len(verificadas), "variacion_ppp_vs_anterior_pct")],
            "frecuencias_direccion": [{"agrupacion": "total", "grupo": None, "direccion": d, "n": n,
                                        "porcentaje": n * 100 / len(variaciones) if variaciones else None}
                                       for d, n in direcciones],
            "distribucion_variacion_pct": {"variable": "variacion_ppp_vs_anterior_pct",
                                           "n": len(variaciones), "histograma": _histograma(variaciones), "cajas": []},
            "serie_historica_verificada": verificadas,
        }
        return respuesta(200, reporte)
    except PeriodoExtenso as exc:
        return respuesta(422, {"detail": str(exc)})
    except Exception as exc:
        logger.warning("estadistica_fallida tipo=%s", type(exc).__name__)
        return respuesta(503, {"detail": "Análisis estadístico temporalmente no disponible."})


def _admin_listar(tabla):
    try:
        items = []
        ultima = None
        while True:
            opciones = {"ConsistentRead": True, "Limit": 100,
                        "ProjectionExpression": "#s, #e, #n, #r, #p, #c",
                        "ExpressionAttributeNames": {"#s": "sub", "#e": "email", "#n": "nombre",
                                                     "#r": "rol", "#p": "plan", "#c": "creado_en"}}
            if ultima:
                opciones["ExclusiveStartKey"] = ultima
            pagina = tabla.scan(**opciones)
            items.extend(pagina.get("Items", []))
            ultima = pagina.get("LastEvaluatedKey")
            if len(items) > 1000 or (len(items) >= 1000 and ultima):
                raise ValueError("Listado requiere paginación")
            if not ultima:
                break
        salida = []
        for item in items:
            if not isinstance(item.get("sub"), str):
                raise ValueError("Perfil inválido")
            salida.append({k: item.get(k) for k in ("email", "nombre", "rol", "plan", "creado_en")} |
                          {"id": item["sub"]})
        return respuesta(200, salida)
    except Exception as exc:
        logger.warning("admin_listado_fallido tipo=%s", type(exc).__name__)
        return respuesta(503, {"detail": "No se pudo completar el listado de perfiles."})


def _admin_actualizar(evento, tabla, ddb, actor):
    uid = (evento.get("pathParameters") or {}).get("uid")
    if not isinstance(uid, str) or not uid.strip() or len(uid) > 128:
        return respuesta(422, {"detail": "Identificador inválido."})
    try:
        body = evento.get("body")
        if evento.get("isBase64Encoded") or not isinstance(body, str) or len(body) > 2048:
            raise ValueError()
        cambios = json.loads(body)
        if not isinstance(cambios, dict) or not cambios or not set(cambios).issubset({"rol", "plan", "nombre"}):
            raise ValueError()
        if "rol" in cambios and cambios["rol"] not in ("user", "admin"):
            raise ValueError()
        if "plan" in cambios and cambios["plan"] not in PLANES:
            raise ValueError()
        if "nombre" in cambios:
            if not isinstance(cambios["nombre"], str) or not cambios["nombre"].strip() or len(cambios["nombre"]) > 120:
                raise ValueError()
            cambios["nombre"] = cambios["nombre"].strip()
    except (TypeError, ValueError):
        return respuesta(422, {"detail": "Cambios de perfil inválidos."})
    if uid == actor and cambios.get("rol", "admin") != "admin":
        return respuesta(400, {"detail": "No puedes quitarte tu propio rol de administrador."})
    table_name = os.environ.get("PERFILES_TABLE")
    if not table_name or ddb is None:
        return respuesta(503, {"detail": "Administración temporalmente no disponible."})
    nombres = {f"#f{i}": k for i, k in enumerate(cambios)}
    valores = {f":v{i}": {"S": v} for i, v in enumerate(cambios.values())}
    update = {"TableName": table_name, "Key": {"sub": {"S": uid}},
              "UpdateExpression": "SET " + ", ".join(f"#f{i} = :v{i}" for i in range(len(cambios))),
              "ExpressionAttributeNames": nombres,
              "ExpressionAttributeValues": valores,
              "ConditionExpression": "attribute_exists(#sub)"}
    update["ExpressionAttributeNames"]["#sub"] = "sub"
    if uid == actor:
        update["ConditionExpression"] += " AND #actorrol = :admin"
        update["ExpressionAttributeNames"]["#actorrol"] = "rol"
        update["ExpressionAttributeValues"][":admin"] = {"S": "admin"}
        acciones = [{"Update": update}]
    else:
        acciones = [{"ConditionCheck": {"TableName": table_name, "Key": {"sub": {"S": actor}},
                                         "ConditionExpression": "#rol = :admin",
                                         "ExpressionAttributeNames": {"#rol": "rol"},
                                         "ExpressionAttributeValues": {":admin": {"S": "admin"}}}},
                    {"Update": update}]
    try:
        ddb.transact_write_items(TransactItems=acciones)
        actor_hash = hashlib.sha256(actor.encode("utf-8")).hexdigest()[:16]
        uid_hash = hashlib.sha256(uid.encode("utf-8")).hexdigest()[:16]
        logger.info("admin_cambio actor_hash=%s objetivo_hash=%s campos=%s",
                    actor_hash, uid_hash, ",".join(sorted(cambios)))
        item = tabla.get_item(Key={"sub": uid}, ConsistentRead=True).get("Item")
        if not item:
            raise ValueError("Perfil no disponible después del cambio")
        return respuesta(200, {"id": uid, **{k: item.get(k) for k in ("email", "nombre", "rol", "plan", "creado_en")}})
    except Exception as exc:
        logger.warning("admin_cambio_fallido tipo=%s", type(exc).__name__)
        codigo = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if codigo in ("TransactionCanceledException", "ConditionalCheckFailedException"):
            return respuesta(409, {"detail": "El perfil no existe o el permiso cambió; vuelve a consultar."})
        return respuesta(503, {"detail": "No se pudo confirmar el cambio; consulta el perfil antes de reintentar."})


def _admin_crear(evento, ddb, cognito, actor):
    """Crea primero sin invitación; nunca elimina usuarios ante resultados inciertos."""
    try:
        body = evento.get("body")
        if evento.get("isBase64Encoded") or not isinstance(body, str) or len(body) > 2048:
            raise ValueError()
        datos = json.loads(body)
        if not isinstance(datos, dict) or set(datos) != {"email", "nombre", "rol", "plan"}:
            raise ValueError()
        email, nombre, rol, plan = (datos[k] for k in ("email", "nombre", "rol", "plan"))
        if not isinstance(email, str) or not isinstance(nombre, str):
            raise ValueError()
        email, nombre = email.strip().lower(), nombre.strip()
        if (len(email) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+", email)
                or not nombre or len(nombre) > 120 or rol not in ("user", "admin") or plan not in PLANES):
            raise ValueError()
    except (TypeError, ValueError):
        return respuesta(422, {"detail": "Datos de invitación inválidos."})
    table_name, pool = os.environ.get("PERFILES_TABLE"), os.environ.get("COGNITO_POOL_ID")
    if not table_name or not pool or ddb is None or cognito is None:
        return respuesta(503, {"detail": "Alta temporalmente no disponible."})
    try:
        creado = cognito.admin_create_user(
            UserPoolId=pool, Username=email, MessageAction="SUPPRESS",
            UserAttributes=[{"Name": "email", "Value": email}, {"Name": "name", "Value": nombre}])
        sub = next(x["Value"] for x in creado["User"]["Attributes"] if x["Name"] == "sub")
        if not isinstance(sub, str) or not sub.strip():
            raise ValueError("sub inválido")
    except Exception as exc:
        codigo = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if codigo == "UsernameExistsException":
            return respuesta(409, {"detail": "La cuenta ya existe; consulta su estado antes de reintentar."})
        logger.warning("admin_alta_cognito_incierta tipo=%s", type(exc).__name__)
        return respuesta(503, {"detail": "No se pudo confirmar la cuenta; revisa Cognito antes de reintentar."})
    item = {"sub": {"S": sub}, "email": {"S": email}, "nombre": {"S": nombre},
            "rol": {"S": rol}, "plan": {"S": plan},
            "creado_en": {"S": datetime.now(timezone.utc).isoformat()}}
    try:
        ddb.transact_write_items(TransactItems=[
            {"ConditionCheck": {"TableName": table_name, "Key": {"sub": {"S": actor}},
                                "ConditionExpression": "#r = :admin",
                                "ExpressionAttributeNames": {"#r": "rol"},
                                "ExpressionAttributeValues": {":admin": {"S": "admin"}}}},
            {"Put": {"TableName": table_name, "Item": item,
                     "ConditionExpression": "attribute_not_exists(#s)",
                     "ExpressionAttributeNames": {"#s": "sub"}}},
        ])
    except Exception as exc:
        logger.warning("admin_alta_perfil_incierto tipo=%s usuario_hash=%s",
                       type(exc).__name__, hashlib.sha256(sub.encode()).hexdigest()[:16])
        return respuesta(503, {"detail": "Cuenta creada sin invitación; confirma el perfil en Cognito y DynamoDB antes de reintentar."})
    try:
        cognito.admin_create_user(UserPoolId=pool, Username=email, MessageAction="RESEND",
                                  DesiredDeliveryMediums=["EMAIL"])
    except Exception as exc:
        logger.warning("admin_alta_envio_incierto tipo=%s usuario_hash=%s",
                       type(exc).__name__, hashlib.sha256(sub.encode()).hexdigest()[:16])
        return respuesta(202, {"id": sub, "invitacion": "ENVIO_NO_CONFIRMADO",
                               "detail": "Perfil creado; revisa la invitación antes de reintentar."})
    logger.info("admin_alta actor_hash=%s usuario_hash=%s", hashlib.sha256(actor.encode()).hexdigest()[:16],
                hashlib.sha256(sub.encode()).hexdigest()[:16])
    return respuesta(201, {"id": sub, "invitacion": "ACEPTADA_POR_COGNITO",
                           "detail": "Cognito aceptó el envío; la entrega y verificación del correo están pendientes."})


def _senales_bloqueadas(evento, permitidas):
    """No exponer Gold sin validar series, hashes y ventanas completas."""
    ruta = evento["routeKey"]
    emisora = (evento.get("queryStringParameters") or {}).get("emisora")
    if ruta in ("GET /api/terminal/senal", "GET /api/terminal/seguimiento") and not emisora:
        return respuesta(422, {"detail": "Indica la emisora."})
    if emisora and emisora not in permitidas:
        return respuesta(403, {"detail": "La emisora no está incluida en tu plan."})
    return respuesta(503, {"detail": "Señales y seguimiento no disponibles: procedencia y ventanas pendientes de validación."})


def _yahoo(evento, s3, permitidas):
    q = evento.get("queryStringParameters") or {}
    emisora, fecha = q.get("emisora"), q.get("fecha")
    es_ipc35 = q.get("universo") == "ipc35_provisional"
    candidatos_20 = set(SIMBOLOS_YAHOO_IPC35) - set(PLANES["professional"])
    if emisora not in permitidas and not (es_ipc35 and emisora in candidatos_20):
        return respuesta(403, {"detail": "La emisora no está incluida en tu plan."})
    simbolos = SIMBOLOS_YAHOO_IPC35
    try:
        if not isinstance(fecha, str) or date.fromisoformat(fecha).isoformat() != fecha:
            raise ValueError()
    except ValueError:
        return respuesta(422, {"detail": "Indica fecha ISO."})
    if emisora not in simbolos:
        return respuesta(404, {"detail": "Símbolo secundario no configurado."})
    if os.environ.get("YAHOO_OBSERVACIONES_HABILITADAS") != "true":
        return respuesta(503, {"detail": "Observaciones secundarias deshabilitadas."})
    try:
        simbolo = simbolos[emisora]
        key = f"observaciones/yahoo/{simbolo}/{fecha}.json"
        obj = s3.get_object(Bucket=os.environ["MERCADO_BUCKET"], Key=key)
        data = interpretar_cierre(obj["Body"].read(2_000_001), simbolo, fecha)
        return respuesta(200, {**data, "inferencia_habilitada": False,
                               "objeto_fuente": key, "capturado_en": str(obj.get("LastModified", ""))})
    except Exception as exc:
        if getattr(exc, "response", {}).get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return respuesta(404, {"detail": "Sin observación secundaria conservada para ese corte."})
        logger.warning("observacion_secundaria_fallida tipo=%s", type(exc).__name__)
        return respuesta(503, {"detail": "Observación secundaria inválida o no disponible."})


_MENSAJE_FRONTERA_PRISMI = (
    "Mi alcance se limita a Prisma BMV: el PPP oficial de la BMV, las emisoras del IPC monitoreadas, "
    "la metodología de modelos G2, las observaciones secundarias separadas, la gobernanza en AWS "
    "y el funcionamiento de la plataforma. No tengo información sobre temas externos."
)
_MENSAJE_NO_ASESORIA_PRISMI = (
    "No doy recomendaciones ni órdenes de compra, venta o inversión. Puedo explicarte el PPP oficial, "
    "la cobertura de los datos y el estado de validación de los modelos."
)
_TEMAS_EXTERNOS_PRISMI = (
    "receta", "cocina", "futbol", "pelicula", "serie de tv", "cancion", "poema", "chiste",
    "politica", "elecciones", "presidente", "clima", "horoscopo", "bitcoin", "cripto",
    "ethereum", "tesla", "nvidia", "apple", "microsoft", "nasdaq", "dow jones",
    "tarea", "ensayo", "traduce", "javascript",
)
_PIDE_ASESORIA_PRISMI = re.compile(
    r"\b(debo|deberia|conviene|me recomiendas|recomiendas|que hago)\b.*\b(comprar|vender|invertir|entrar|salir)\b"
    r"|\b(compro|vendo|invierto)\b",
)
_SALIDA_IMPERATIVA_PRISMI = re.compile(
    r"\b(compre|venda|compra ya|vende ya|le recomiendo (comprar|vender)|te recomiendo (comprar|vender)|"
    r"debes (comprar|vender))\b",
    re.IGNORECASE,
)


def _norm_texto(texto):
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_acentos.lower().strip()


def _leer_json_s3_opcional(s3, bucket, key, max_bytes=500_000):
    if not bucket or s3 is None:
        return None
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        raw = obj["Body"].read(max_bytes + 1)
        if len(raw) > max_bytes:
            return None
        return json.loads(raw.decode("utf-8-sig"))
    except Exception:
        return None


def _contar_cortes_ipc35(s3, bucket):
    try:
        page = s3.list_objects_v2(Bucket=bucket, Prefix="silver/ipc35_provisional/capturas/", MaxKeys=100)
        return sum(1 for x in page.get("Contents", []) if x["Key"].endswith(".json"))
    except Exception:
        return None


def _gobernanza(s3):
    """Devuelve topología real del lakehouse y estado vivo de compuertas desde S3."""
    bucket = os.environ.get("MERCADO_BUCKET", "")
    if not bucket or s3 is None:
        return respuesta(503, {"detail": "Gobernanza en S3 no configurada."})
    avance = _leer_json_s3_opcional(s3, bucket, "evidencias/operacion/avance_ventana_limpia.json") or {}
    permiso_yahoo = _leer_json_s3_opcional(s3, bucket, "evidencias/observaciones_yahoo/estado_permiso.json") or {}
    cal_2027 = _leer_json_s3_opcional(s3, bucket, "evidencias/calendario_bmv/2027/estado.json") or {}
    declaracion = (
        _leer_json_s3_opcional(s3, bucket, "evidencias/gobernanza/declaracion_fuentes_v2.json")
        or _leer_json_s3_opcional(s3, bucket, "evidencias/gobernanza/declaracion_fuentes.json")
        or {}
    )
    cortes_ipc35 = _contar_cortes_ipc35(s3, bucket)
    ventana = avance.get("ventana_limpia") or {}
    sesiones = ventana.get("sesiones_consecutivas")
    meta = ventana.get("meta", 21)
    ultima_fecha = avance.get("ultima_fecha_capturada")
    capturas_totales = avance.get("capturas_seguras_totales")
    sha_bronze = avance.get("sha256_bronze")
    sha_silver = avance.get("sha256_silver")
    guardia = avance.get("guardia_resumen") or {}
    yahoo_habilitada_api = os.environ.get("YAHOO_OBSERVACIONES_HABILITADAS") == "true"
    yahoo_estado = permiso_yahoo.get("estado", "DESCONOCIDO")
    cal_estado = cal_2027.get("estado", "PENDIENTE_FUENTE_OFICIAL")
    emision = avance.get("emision", "NO_HABILITADA")

    resumen_ventana = (
        f"{sesiones}/{meta} sesiones consecutivas desde {ventana.get('desde_corte_limpio', '2026-11-20')}"
        if sesiones is not None else "En seguimiento en evidencias/operacion/"
    )
    nodos = [
        {"nombre": "EventBridge Scheduler",
         "detalle": "DisparadorDiarioBMV (ENABLED) · cron(45 16 ? * MON-FRI *) America/Mexico_City"},
        {"nombre": "Lambda recolector-seguro",
         "detalle": "Captura diaria idempotente con validación estricta, IfNoneMatch='*' y cero imputación"},
        {"nombre": "Boletín BMV (RSS)",
         "detalle": f"Último corte capturado: {ultima_fecha or 'en consulta'} · SHA-256 {(sha_bronze or '')[:12] or 'pendiente'}"},
        {"nombre": "S3 Bronze inmutable",
         "detalle": "bronze/YYYY/MM/boletin_YYYYMMDD.html · integridad SHA-256 verificada"},
        {"nombre": "S3 Silver (15 + IPC-35)",
         "detalle": f"Capturas seguras: {capturas_totales if capturas_totales is not None else '—'} · Cortes IPC-35 provisionales: {cortes_ipc35 if cortes_ipc35 is not None else '—'}"},
        {"nombre": "Compuerta Señales Gold",
         "detalle": f"BLOQUEADA ({emision}) · Ventana limpia {resumen_ventana}"},
        {"nombre": "Yahoo Observaciones",
         "detalle": f"Separado en observaciones/yahoo/ · Permiso {yahoo_estado} · API {'ACTIVA' if yahoo_habilitada_api else 'DESHABILITADA'} · Nunca alimenta Silver/modelos"},
        {"nombre": "API Gateway + Cognito",
         "detalle": "Identidad exclusiva Amazon Cognito + DynamoDB (Supabase retirado)"},
        {"nombre": "CloudWatch + SQS DLQ",
         "detalle": "Alarmas de errores/duración/DLQ activas con notificación SNS"},
        {"nombre": "IAM LabRole",
         "detalle": (declaracion.get("iam") or {}).get("decision", "Rol operativo adoptado bajo restricción educativa AWS Academy")},
    ]
    enlaces = [
        {"origen": 0, "destino": 1, "valor": 3},
        {"origen": 2, "destino": 1, "valor": 3},
        {"origen": 1, "destino": 3, "valor": 3},
        {"origen": 3, "destino": 4, "valor": 3},
        {"origen": 4, "destino": 5, "valor": 2},
        {"origen": 4, "destino": 7, "valor": 3},
        {"origen": 6, "destino": 7, "valor": 1},
        {"origen": 1, "destino": 8, "valor": 1},
        {"origen": 9, "destino": 1, "valor": 1},
    ]
    return respuesta(200, {
        "nodos": nodos,
        "enlaces": enlaces,
        "estado_operativo": {
            "actualizado_en_utc": avance.get("actualizado_en_utc"),
            "scheduler": {
                "nombre": "DisparadorDiarioBMV",
                "estado": "ENABLED",
                "expresion": "cron(45 16 ? * MON-FRI *)",
                "zona_horaria": "America/Mexico_City",
            },
            "ventana_limpia": {
                "desde_corte_limpio": ventana.get("desde_corte_limpio", "2026-11-20"),
                "sesiones_consecutivas": sesiones,
                "meta": meta,
                "faltan": ventana.get("faltan"),
                "completa": bool(ventana.get("completa", False)),
                "ultima_fecha_capturada": ultima_fecha,
                "fechas_racha": ventana.get("fechas_racha") or [],
            },
            "integridad": {
                "capturas_seguras_totales": capturas_totales,
                "cortes_ipc35_provisionales": cortes_ipc35,
                "sha256_bronze": sha_bronze,
                "sha256_silver": sha_silver,
                "guardia_resumen": guardia,
                "capturas_seguras_habilitadas": os.environ.get("CAPTURAS_SEGURAS_HABILITADAS") == "true",
            },
            "compuertas": {
                "emision_senales": emision,
                "yahoo_observaciones": {
                    "estado_permiso": yahoo_estado,
                    "habilitada_api": yahoo_habilitada_api,
                    "separacion": "CIERRE_DIARIO_REPORTADO separado de PPP BMV y modelos",
                },
                "calendario_bmv_2027": {
                    "estado": cal_estado,
                    "habilita_operacion": bool(cal_2027.get("habilita_operacion", False)),
                },
                "ipc_35": {
                    "estado_composicion": "PROVISIONAL_NO_OFICIAL",
                    "componentes": 35,
                    "alias_pendientes": ["RA -> R / A", "LIVEPOLC.1 -> LIVEPOL / C-1"],
                },
            },
            "identidad": "Amazon Cognito + DynamoDB (Supabase retirado)",
        },
    })


def _contexto_prismi_s3(s3, permitidas):
    """Construye contexto real desde S3 respetando el plan del usuario y sin inventar cifras."""
    bucket = os.environ.get("MERCADO_BUCKET", "")
    avance = _leer_json_s3_opcional(s3, bucket, "evidencias/operacion/avance_ventana_limpia.json") or {}
    permiso_yahoo = _leer_json_s3_opcional(s3, bucket, "evidencias/observaciones_yahoo/estado_permiso.json") or {}
    ultima_fecha = None
    por_emisora = {}
    verificadas = 0
    ausentes = 0
    try:
        _, filas, fechas = _leer_mercado(s3)
        if fechas:
            ultima_fecha = fechas[0]
            sesion = [r for r in filas if r["fecha"] == ultima_fecha and r["emisora"] in PLANES["professional"]]
            for r in sesion:
                ok = r["estado_captura"] == "PPP_PUBLICADO_VERIFICADO"
                ppp = _numero(r.get("ppp_bmv_mxn")) if ok else None
                var = _numero(r.get("variacion_ppp_vs_anterior_pct")) if ok else None
                if ppp is not None and ppp > 0:
                    verificadas += 1
                else:
                    ausentes += 1
                if r["emisora"] in permitidas:
                    por_emisora[r["emisora"]] = {
                        "serie": r.get("serie", ""),
                        "sector": r.get("sector_economico", ""),
                        "estado": r["estado_captura"],
                        "ppp": ppp if (ppp is not None and ppp > 0) else None,
                        "var": var,
                    }
    except Exception:
        pass
    ventana = avance.get("ventana_limpia") or {}
    return {
        "ultima_fecha": ultima_fecha or avance.get("ultima_fecha_capturada"),
        "verificadas": verificadas,
        "ausentes": ausentes,
        "por_emisora": por_emisora,
        "ventana": ventana,
        "capturas_totales": avance.get("capturas_seguras_totales"),
        "sha_bronze": avance.get("sha256_bronze"),
        "yahoo_estado": permiso_yahoo.get("estado", "DESCONOCIDO"),
        "yahoo_api_activa": os.environ.get("YAHOO_OBSERVACIONES_HABILITADAS") == "true",
    }


def _responder_prismi_local(pregunta, ctx, plan, permitidas):
    p = _norm_texto(pregunta)
    aviso = "Información estadística y de gobernanza; no constituye asesoría de inversión."

    for em in PLANES["professional"]:
        if re.search(rf"\b{re.escape(em.lower())}\b", p):
            if em not in permitidas:
                return (
                    f"{em} no está incluida en tu plan actual ({plan}). El plan Explorer cubre WALMEX y "
                    "el monitor público; Professional y Enterprise habilitan las 15 emisoras base y el universo "
                    f"ampliado de 35 componentes IPC en análisis descriptivo. {aviso}"
                )
            d = ctx["por_emisora"].get(em)
            if d and d["ppp"] is not None:
                var_txt = f" ({d['var']:+.2f}% vs. sesión anterior)" if d["var"] is not None else ""
                return (
                    f"En la última sesión registrada ({ctx['ultima_fecha']}), {em} {d['serie']} registró un PPP "
                    f"oficial verificado de ${d['ppp']:,.2f} MXN{var_txt}. Las señales G2 permanecen bloqueadas "
                    f"hasta completar la ventana limpia 21/21 y las validaciones de eventos corporativos. {aviso}"
                )
            if d:
                return (
                    f"En la última sesión registrada ({ctx['ultima_fecha']}), {em} {d['serie']} no reportó PPP "
                    f"verificado (estado: {d['estado']}). Prisma BMV aplica cero imputación y no estima el precio. {aviso}"
                )

    if any(k in p for k in ("ppp", "precio promedio")):
        return (
            "El PPP (Precio Promedio Ponderado) es el precio oficial que publica la BMV ponderando el volumen "
            "de todas las operaciones de la sesión. A diferencia del último hecho, refleja dónde se negoció "
            "realmente el volumen del día. En Prisma BMV cada boletín se verifica con huella SHA-256."
        )
    if any(k in p for k in ("yahoo", "secundaria", "cierre diario")):
        estado = "activa" if ctx["yahoo_api_activa"] else "deshabilitada"
        return (
            f"La observación secundaria de Yahoo Finance está {estado} (permiso: {ctx['yahoo_estado']}) "
            "como CIERRE_DIARIO_REPORTADO en los 35 símbolos .MX verificados. Vive separada en "
            "observaciones/yahoo/, nunca se etiqueta como PPP oficial BMV y nunca entra a Silver ni a modelos."
        )
    if any(k in p for k in ("ipc", "35", "provisional", "naftrac", "candidato")):
        return (
            "El universo ampliado de 35 componentes del IPC usa la referencia provisional NAFTRAC (2026-11-17) "
            "con almacenamiento versionado e inmutable en silver/ipc35_provisional/. Muestra PPP observado "
            "cuando aparece en las tablas RSS y documenta los huecos sin imputar; las señales siguen bloqueadas "
            "hasta validar la composición oficial fechada S&P/BMV y los alias pendientes (RA y LIVEPOLC.1)."
        )
    if any(k in p for k in ("ventana", "21", "gobernanza", "sha", "hash", "aws", "scheduler", "lambda")):
        v = ctx["ventana"]
        ses = v.get("sesiones_consecutivas")
        meta = v.get("meta", 21)
        progreso = f"{ses}/{meta} sesiones consecutivas" if ses is not None else "en seguimiento"
        return (
            f"La ingesta automatizada corre en AWS mediante DisparadorDiarioBMV (lunes a viernes 16:45 CDMX) "
            f"hacia el recolector seguro con escrituras inmutables y validación SHA-256. La ventana limpia "
            f"actual lleva {progreso} (última sesión: {ctx['ultima_fecha'] or '—'}, capturas seguras: "
            f"{ctx['capturas_totales'] if ctx['capturas_totales'] is not None else '—'}). Las señales G2 "
            "permanecen bloqueadas hasta cerrar las compuertas de validación."
        )
    if any(k in p for k in ("hueco", "imputa", "ausente", "faltante", "no publicada")):
        return (
            "Prisma BMV aplica política estricta de cero imputación: si una emisora no aparece en las tablas "
            "del boletín RSS del día, se registra el hueco explícitamente sin rellenar ni interpolar precios."
        )
    if any(k in p for k in ("senal", "g2", "modelo", "consenso", "t+5", "predic")):
        v = ctx["ventana"]
        ses = v.get("sesiones_consecutivas")
        meta = v.get("meta", 21)
        progreso = f"{ses}/{meta}" if ses is not None else "pendiente"
        return (
            f"Las señales de 2ª generación (G2), el consenso y el seguimiento t+5 permanecen bloqueados por "
            f"gobernanza en AWS hasta completar la ventana limpia ({progreso}), conciliar los avisos oficiales "
            "de eventos corporativos, ejecutar la auditoría temporal sin fuga (excluyendo las 13 filas de "
            f"unificación AMX L→B de 2023) y cerrar el periodo shadow de 20 sesiones. {aviso}"
        )
    if any(k in p for k in ("plan", "precio", "suscrip", "explorer", "professional", "enterprise")):
        return (
            "Planes institucionales de Prisma BMV: Explorer ($0 MXN/mes: monitor BMV de 35 componentes provisionales, "
            "serie y estadística de WALMEX, verificación SHA-256 y Prismi); Professional ($399 MXN/mes, ~$20 USD: "
            "panel completo, estadística ampliada, observación secundaria Yahoo y acceso a señales G2 cuando "
            "completen validación); Enterprise ($3,490 MXN/mes, ~$175 USD: capacidades institucionales, API/Athena "
            "y gestión de equipos). Los cambios de plan se administran sobre Cognito y DynamoDB."
        )
    resumen = (
        f"Última sesión en el lakehouse: {ctx['ultima_fecha']} ({ctx['verificadas']} PPP verificados, "
        f"{ctx['ausentes']} huecos en el panel base). "
        if ctx["ultima_fecha"] else ""
    )
    return (
        f"{resumen}Tu plan actual es {plan}. Puedo explicarte el PPP oficial de la BMV, la cobertura provisional "
        "de los 35 componentes del IPC, el avance de la ventana limpia 21/21, las observaciones secundarias "
        "Yahoo Finance, la política de cero imputación o los planes disponibles."
    )


def _prismi(evento, s3, plan, permitidas):
    try:
        body = evento.get("body")
        if evento.get("isBase64Encoded") or not isinstance(body, str) or len(body) > 12_000:
            raise ValueError()
        datos = json.loads(body)
        if not isinstance(datos, dict):
            raise ValueError()
        pregunta = datos.get("pregunta")
        if not isinstance(pregunta, str) or not pregunta.strip() or len(pregunta) > 1500:
            raise ValueError()
        historial = datos.get("historial") or []
        if not isinstance(historial, list):
            raise ValueError()
        contexto_grafica = datos.get("contexto_grafica")
        if contexto_grafica is not None and (not isinstance(contexto_grafica, str) or len(contexto_grafica) > 4000):
            raise ValueError()
    except (TypeError, ValueError):
        return respuesta(422, {"detail": "Indica una pregunta válida (1..1500 caracteres)."})

    pregunta_limpia = pregunta.strip()
    norm = _norm_texto(pregunta_limpia)
    if any(re.search(rf"\b{re.escape(t)}", norm) for t in _TEMAS_EXTERNOS_PRISMI):
        return respuesta(200, {"respuesta": _MENSAJE_FRONTERA_PRISMI, "origen": "GUARDRAIL"})

    ctx = _contexto_prismi_s3(s3, permitidas)
    if _PIDE_ASESORIA_PRISMI.search(norm):
        detalle = _responder_prismi_local(pregunta_limpia, ctx, plan, permitidas)
        return respuesta(200, {"respuesta": f"{_MENSAJE_NO_ASESORIA_PRISMI}\n\n{detalle}", "origen": "GUARDRAIL"})

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        try:
            lineas_ctx = [
                f"Última sesión BMV: {ctx['ultima_fecha'] or 'sin fecha'} "
                f"({ctx['verificadas']} verificadas, {ctx['ausentes']} huecos).",
                f"Plan del usuario: {plan}. Señales G2: BLOQUEADAS hasta cerrar ventana limpia 21/21 y validaciones.",
                f"Ventana limpia: {(ctx['ventana'] or {}).get('sesiones_consecutivas', '—')}/"
                f"{(ctx['ventana'] or {}).get('meta', 21)}.",
                f"Yahoo Finance secundario: permiso {ctx['yahoo_estado']}, separado de PPP BMV.",
            ]
            for em, d in list(ctx["por_emisora"].items())[:15]:
                val = f"${d['ppp']:,.2f} MXN" if d["ppp"] is not None else d["estado"]
                lineas_ctx.append(f"{em} ({d['serie']}): {val}")
            if contexto_grafica:
                lineas_ctx.append(f"Gráfica actual en terminal: {contexto_grafica[:1200]}")
            sys_prompt = (
                "Eres Prismi, asistente cuantitativo institucional de Prisma BMV. Responde en español en <=160 palabras. "
                "Solo responde sobre Prisma BMV, PPP BMV, IPC-35, gobernanza AWS, Yahoo secundario separado y planes. "
                f"Si preguntan temas externos responde exactamente: {_MENSAJE_FRONTERA_PRISMI} "
                "Nunca recomiendes comprar ni vender. Nunca inventes precios ni digas que las señales G2 están activas "
                "mientras estén bloqueadas. Nunca menciones proyectos escolares ni universidades.\nCONTEXTO:\n"
                + "\n".join(lineas_ctx)
            )
            mensajes = []
            for h in historial[-6:]:
                if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
                    mensajes.append({"role": h["role"], "content": h["content"][:800]})
            while mensajes and mensajes[0]["role"] != "user":
                mensajes.pop(0)
            mensajes.append({"role": "user", "content": pregunta_limpia})
            payload = {
                "model": os.environ.get("PRISMI_MODELO", "claude-3-5-sonnet-20241022"),
                "max_tokens": 450,
                "system": sys_prompt,
                "messages": mensajes,
            }
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read(100_000).decode("utf-8"))
            texto = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
            if texto:
                if _SALIDA_IMPERATIVA_PRISMI.search(texto):
                    detalle = _responder_prismi_local(pregunta_limpia, ctx, plan, permitidas)
                    return respuesta(200, {"respuesta": f"{_MENSAJE_NO_ASESORIA_PRISMI}\n\n{detalle}", "origen": "GUARDRAIL"})
                return respuesta(200, {"respuesta": texto, "origen": "CLAUDE"})
        except Exception as exc:
            logger.warning("prismi_claude_fallido tipo=%s", type(exc).__name__)

    return respuesta(200, {
        "respuesta": _responder_prismi_local(pregunta_limpia, ctx, plan, permitidas),
        "origen": "LOCAL_AWS",
    })


def ejecutar(evento, tabla, s3=None, ddb=None, cognito=None):
    ruta = evento.get("routeKey")
    if ruta == "GET /health":
        return respuesta(200, {"status": "ok", "service": "prisma-api-experimental"})
    if ruta in ("GET /api/mercado/fechas", "GET /api/mercado/resumen"):
        return _mercado(evento, s3)
    if ruta == "GET /api/terminal/sectores":
        return _sectores(evento, s3)
    if ruta == "GET /api/terminal/gobernanza":
        return _gobernanza(s3)
    admin_rutas = ("GET /api/admin/usuarios", "PATCH /api/admin/usuarios/{uid}", "POST /api/admin/usuarios")
    senal_rutas = ("GET /api/senales/panel", "GET /api/terminal/senal", "GET /api/terminal/seguimiento",
                   "GET /api/terminal/consenso", "GET /api/terminal/marcador")
    if ruta not in ("GET /api/me", "GET /api/terminal/serie", "GET /api/serie/walmex", "GET /api/terminal/estadistica", "GET /api/observaciones/yahoo", "POST /api/terminal/prismi", *admin_rutas, *senal_rutas):
        return respuesta(404, {"detail": "Ruta no disponible."})
    claims = evento.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    sub = claims.get("sub")
    # API Gateway verifica firma, emisor, cliente y expiración; ID tokens no se admiten.
    if claims.get("token_use") != "access" or not isinstance(sub, str) or not sub.strip():
        return respuesta(401, {"detail": "Sesión inválida."})
    try:
        item = tabla.get_item(Key={"sub": sub}, ConsistentRead=True).get("Item")
    except Exception as exc:
        logger.warning("lectura_perfil_fallida tipo=%s", type(exc).__name__)
        return respuesta(503, {"detail": "Perfil temporalmente no disponible."})
    if not isinstance(item, dict):
        return respuesta(403, {"detail": "Perfil no autorizado."})
    plan, rol = item.get("plan"), item.get("rol")
    email, nombre = item.get("email"), item.get("nombre")
    if not isinstance(plan, str) or plan not in PLANES or rol not in ("user", "admin") or not isinstance(email, str) or not email.strip() or not isinstance(nombre, str):
        return respuesta(403, {"detail": "Perfil no autorizado."})
    if ruta in admin_rutas:
        if rol != "admin":
            return respuesta(403, {"detail": "Se requiere rol administrador."})
        if ruta.startswith("GET "):
            return _admin_listar(tabla)
        if ruta.startswith("POST "):
            return _admin_crear(evento, ddb, cognito, sub)
        return _admin_actualizar(evento, tabla, ddb, sub)
    if ruta in senal_rutas:
        return _senales_bloqueadas(evento, PLANES[plan])
    if ruta == "POST /api/terminal/prismi":
        return _prismi(evento, s3, plan, PLANES[plan])
    if ruta == "GET /api/observaciones/yahoo":
        return _yahoo(evento, s3, PLANES[plan])
    if ruta == "GET /api/terminal/estadistica":
        return _estadistica(evento, s3, PLANES[plan])
    if ruta != "GET /api/me":
        return _serie(evento, s3, PLANES[plan])
    return respuesta(200, {"id": sub, "email": email, "nombre": nombre,
                           "rol": rol, "plan": plan, "emisoras": PLANES[plan]})


def lambda_handler(event, context):
    import boto3
    global _tabla, _s3, _ddb, _cognito
    if _tabla is None:
        _tabla = boto3.resource("dynamodb").Table(os.environ["PERFILES_TABLE"])
    if _s3 is None:
        _s3 = boto3.client("s3")
    if _ddb is None:
        _ddb = boto3.client("dynamodb")
    if _cognito is None:
        _cognito = boto3.client("cognito-idp")
    return ejecutar(event, _tabla, _s3, _ddb, _cognito)
