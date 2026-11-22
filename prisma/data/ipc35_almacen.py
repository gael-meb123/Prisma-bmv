"""Almacenamiento versionado e inmutable para los 35 componentes provisionales del IPC en S3.

Vive completamente aislado bajo ``silver/ipc35_provisional/`` sin tocar
``silver/precios_ppp/``, ``silver/recolector_seguro/`` ni tablas Athena legadas.
No certifica pertenencia oficial al IPC ni habilita señales o inferencia.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from datetime import date, datetime, timezone

from prisma.data.captura_ampliada import extraer
from prisma.domain.catalogo_ipc import catalogo_naftrac_20261117

PREFIJO_IPC35_CAPTURAS = "silver/ipc35_provisional/capturas/"
PREFIJO_IPC35_PRECIOS = "silver/ipc35_provisional/precios_ppp/"
COLUMNAS_IPC35 = (
    "fecha",
    "emisora",
    "serie",
    "origen_catalogo",
    "alias_blackrock",
    "estado_composicion",
    "estado_mapeo",
    "estado_captura",
    "ppp_bmv_mxn",
    "ultimo_bmv_mxn",
    "anterior_bmv_mxn",
    "variacion_ppp_vs_anterior_pct",
    "url_fuente",
    "sha256_boletin",
    "version_catalogo",
)

# Símbolos Yahoo Finance (.MX) verificados en modo solo lectura (exchange=MEX, currency=MXN)
# el 2026-11-21. Nunca sustituyen PPP BMV ni alimentan Silver/modelos; requieren permiso aprobado.
SIMBOLOS_YAHOO_IPC35 = {
    # 15 emisoras base
    "WALMEX": "WALMEX.MX",
    "GMEXICO": "GMEXICOB.MX",
    "GFNORTE": "GFNORTEO.MX",
    "AMX": "AMXB.MX",
    "FEMSA": "FEMSAUBD.MX",
    "CEMEX": "CEMEXCPO.MX",
    "GAP": "GAPB.MX",
    "PE&OLES": "PE&OLES.MX",
    "AC": "AC.MX",
    "ASUR": "ASURB.MX",
    "BIMBO": "BIMBOA.MX",
    "VESTA": "VESTA.MX",
    "GFINBUR": "GFINBURO.MX",
    "GRUMA": "GRUMAB.MX",
    "LIVEPOL": "LIVEPOLC-1.MX",
    # 20 candidatos provisionales (verificados MEX/MXN 2026-11-21)
    "KOF": "KOFUBL.MX",
    "SIGMAF": "SIGMAFA.MX",
    "OMA": "OMAB.MX",
    "PINFRA": "PINFRA.MX",
    "KIMBER": "KIMBERA.MX",
    "BBAJIO": "BBAJIOO.MX",
    "Q": "Q.MX",
    "GENTERA": "GENTERA.MX",
    "CHDRAUI": "CHDRAUIB.MX",
    "GCARSO": "GCARSOA1.MX",
    "ALSEA": "ALSEA.MX",
    "ALPEK": "ALPEKA.MX",
    "MEGA": "MEGACPO.MX",
    "GCC": "GCC.MX",
    "R": "RA.MX",
    "ORBIA": "ORBIA.MX",
    "BOLSA": "BOLSAA.MX",
    "LACOMER": "LACOMERUBC.MX",
    "VOLAR": "VOLARA.MX",
    "LAB": "LABB.MX",
}

# Clasificación sectorial BMV provisional para los 20 candidatos NAFTRAC (2026-11-17).
# Se etiqueta explícitamente como provisional hasta validar composición y catálogo oficial S&P/BMV.
SECTORES_IPC35_PROVISIONAL = {
    "KOF": "Productos de consumo frecuente · Bebidas (provisional)",
    "SIGMAF": "Productos de consumo frecuente · Alimentos (provisional)",
    "OMA": "Industrial · Aeropuertos (provisional)",
    "PINFRA": "Industrial · Infraestructura (provisional)",
    "KIMBER": "Productos de consumo frecuente (provisional)",
    "BBAJIO": "Servicios financieros · Banca (provisional)",
    "Q": "Servicios financieros · Seguros (provisional)",
    "GENTERA": "Servicios financieros · Microfinanzas (provisional)",
    "CHDRAUI": "Productos de consumo frecuente · Autoservicios (provisional)",
    "GCARSO": "Industrial · Conglomerado (provisional)",
    "ALSEA": "Consumo no básico · Restaurantes (provisional)",
    "ALPEK": "Materiales · Petroquímica (provisional)",
    "MEGA": "Servicios de telecomunicaciones (provisional)",
    "GCC": "Materiales · Cemento y construcción (provisional)",
    "R": "Servicios financieros · Banca (provisional)",
    "ORBIA": "Materiales · Polímeros e infraestructura (provisional)",
    "BOLSA": "Servicios financieros · Infraestructura de mercado (provisional)",
    "LACOMER": "Productos de consumo frecuente · Autoservicios (provisional)",
    "VOLAR": "Industrial · Aerolíneas (provisional)",
    "LAB": "Salud · Farmacéutica y cuidado personal (provisional)",
}


class _CatalogoPresencia35:
    def __init__(self, base):
        self.base = base
        self.version = base.version

    def en_corte(self, _fecha):
        return self.base.componentes


def clave_manifiesto_ipc35(fecha: str) -> str:
    dia = date.fromisoformat(fecha)
    if dia.isoformat() != fecha:
        raise ValueError("Fecha no canónica")
    return f"{PREFIJO_IPC35_CAPTURAS}{dia:%Y/%m}/captura_{dia:%Y%m%d}.json"


def clave_silver_ipc35(fecha: str) -> str:
    dia = date.fromisoformat(fecha)
    if dia.isoformat() != fecha:
        raise ValueError("Fecha no canónica")
    return f"{PREFIJO_IPC35_PRECIOS}{dia:%Y/%m}/ppp_35_provisional_{dia:%Y%m%d}.csv"


def construir_corte_ipc35(raw_html: bytes, fecha: str, url_fuente: str) -> dict:
    """Extrae los 35 pares provisionales desde un boletín HTML Bronze sin imputación."""
    dia = date.fromisoformat(fecha)
    if dia.isoformat() != fecha:
        raise ValueError("Fecha no canónica")
    catalogo = catalogo_naftrac_20261117()
    extraido = extraer(raw_html, dia, _CatalogoPresencia35(catalogo), url_fuente)
    sha_bronze = extraido["sha256_boletin"]
    ymd = dia.strftime("%Y%m%d")

    filas = []
    observados = 0
    huecos = 0
    for r in extraido["filas"]:
        estado_raw = r["estado_captura"]
        ppp = r["ppp_bmv_mxn"]
        ult = r["ultimo_bmv_mxn"]
        ant = r["anterior_bmv_mxn"]
        if estado_raw == "PPP_OBSERVADO_MAPEO_PROVISIONAL" and ppp is not None and math.isfinite(ppp) and ppp > 0:
            estado = "PPP_OBSERVADO_MAPEO_PROVISIONAL"
            var = round((ppp / ant - 1.0) * 100.0, 2) if (ant is not None and math.isfinite(ant) and ant > 0) else ""
            observados += 1
        elif estado_raw == "NO_ENCONTRADO_EN_TABLAS":
            estado, ppp, ult, ant, var = "NO_ENCONTRADO_EN_TABLAS_BOLETIN", "", "", "", ""
            huecos += 1
        else:
            estado, ppp, ult, ant, var = "CONFLICTO_O_FILA_INVALIDA", "", "", "", ""
            huecos += 1
        filas.append({
            "fecha": fecha,
            "emisora": r["emisora_propuesta"],
            "serie": r["serie_propuesta"],
            "origen_catalogo": r["origen_catalogo"],
            "alias_blackrock": r["alias_blackrock"],
            "estado_composicion": r["estado_composicion"],
            "estado_mapeo": r["estado_mapeo"],
            "estado_captura": estado,
            "ppp_bmv_mxn": ppp,
            "ultimo_bmv_mxn": ult,
            "anterior_bmv_mxn": ant,
            "variacion_ppp_vs_anterior_pct": var,
            "url_fuente": url_fuente,
            "sha256_boletin": sha_bronze,
            "version_catalogo": catalogo.version,
        })

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(COLUMNAS_IPC35), lineterminator="\n")
    writer.writeheader()
    writer.writerows(filas)
    csv_bytes = buf.getvalue().encode("utf-8")
    sha_csv = hashlib.sha256(csv_bytes).hexdigest()

    bronze_key = f"bronze/{dia:%Y/%m}/boletin_{ymd}.html"
    silver_key = clave_silver_ipc35(fecha)
    manifiesto_key = clave_manifiesto_ipc35(fecha)
    manifiesto = {
        "version": 1,
        "fecha": fecha,
        "version_catalogo": catalogo.version,
        "estado_composicion": "PROVISIONAL_NO_OFICIAL",
        "bronze": bronze_key,
        "sha256_bronze": sha_bronze,
        "silver_ipc35": silver_key,
        "sha256_silver_ipc35": sha_csv,
        "total_filas": len(filas),
        "observados_ppp": observados,
        "huecos": huecos,
        "emision": "NO_HABILITADA",
    }
    return {
        "fecha": fecha,
        "silver_key": silver_key,
        "manifiesto_key": manifiesto_key,
        "csv_bytes": csv_bytes,
        "manifiesto": manifiesto,
        "manifiesto_bytes": json.dumps(manifiesto, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        "filas": filas,
    }


def _guardar_inmutable(s3, bucket: str, key: str, raw: bytes, content_type: str) -> str:
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=raw, ContentType=content_type, IfNoneMatch="*")
        return "CREADO"
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code not in ("PreconditionFailed", "412"):
            raise
        anterior = s3.get_object(Bucket=bucket, Key=key)["Body"].read(2_000_001)
        if anterior != raw:
            raise RuntimeError(f"Conflicto inmutable IPC-35 en {key}") from exc
        return "IDENTICO"


def guardar_corte_ipc35(s3, bucket: str, raw_html: bytes, fecha: str, url_fuente: str) -> dict:
    corte = construir_corte_ipc35(raw_html, fecha, url_fuente)
    est_csv = _guardar_inmutable(s3, bucket, corte["silver_key"], corte["csv_bytes"], "text/csv; charset=utf-8")
    est_man = _guardar_inmutable(s3, bucket, corte["manifiesto_key"], corte["manifiesto_bytes"], "application/json")
    return {
        "fecha": fecha,
        "silver_ipc35": est_csv,
        "manifiesto_ipc35": est_man,
        "observados_ppp": corte["manifiesto"]["observados_ppp"],
        "huecos": corte["manifiesto"]["huecos"],
        "sha256_silver_ipc35": corte["manifiesto"]["sha256_silver_ipc35"],
    }


def leer_manifiesto_ipc35(s3, bucket: str, fecha: str, opcional: bool = False) -> dict | None:
    key = clave_manifiesto_ipc35(fecha)
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except Exception as exc:
        if opcional and getattr(exc, "response", {}).get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    raw = obj["Body"].read(16_385)
    if len(raw) > 16_384:
        raise ValueError("Manifiesto IPC-35 demasiado grande")
    dato = json.loads(raw)
    dia = date.fromisoformat(fecha)
    esperados = {
        "version", "fecha", "version_catalogo", "estado_composicion",
        "bronze", "sha256_bronze", "silver_ipc35", "sha256_silver_ipc35",
        "total_filas", "observados_ppp", "huecos", "emision",
    }
    if (not isinstance(dato, dict) or set(dato) != esperados
            or dato["version"] != 1 or dato["fecha"] != fecha
            or dato["bronze"] != f"bronze/{dia:%Y/%m}/boletin_{dia:%Y%m%d}.html"
            or dato["silver_ipc35"] != clave_silver_ipc35(fecha)
            or dato["emision"] != "NO_HABILITADA"
            or any(not isinstance(dato[c], str) or not re.fullmatch(r"[0-9a-f]{64}", dato[c])
                   for c in ("sha256_bronze", "sha256_silver_ipc35"))):
        raise ValueError("Manifiesto IPC-35 inválido")
    return dato


def leer_captura_ipc35(s3, bucket: str, manifiesto: dict) -> tuple[dict, list[dict]]:
    obj = s3.get_object(Bucket=bucket, Key=manifiesto["silver_ipc35"])
    raw = obj["Body"].read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Silver IPC-35 demasiado grande")
    if hashlib.sha256(raw).hexdigest() != manifiesto["sha256_silver_ipc35"]:
        raise ValueError("Silver IPC-35 no coincide con su manifiesto")
    lector = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if not {"fecha", "emisora", "serie", "estado_captura", "ppp_bmv_mxn", "sha256_boletin"}.issubset(lector.fieldnames or []):
        raise ValueError("Contrato Silver IPC-35 inválido")
    filas = list(lector)
    if (not filas or any(r["fecha"] != manifiesto["fecha"] or r["sha256_boletin"] != manifiesto["sha256_bronze"] for r in filas)
            or len({(r["emisora"], r["serie"]) for r in filas}) != len(filas)):
        raise ValueError("Silver IPC-35 inconsistente o duplicado")
    return obj, filas


def pagina_mes_ipc35(s3, bucket: str, mes: str) -> list[str]:
    if not isinstance(mes, str) or not re.fullmatch(r"\d{4}-\d{2}", mes):
        raise ValueError("Mes inválido")
    date.fromisoformat(mes + "-01")
    prefix = PREFIJO_IPC35_CAPTURAS + mes.replace("-", "/") + "/"
    page = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=31)
    fechas = []
    for item in page.get("Contents", []):
        m = re.fullmatch(re.escape(prefix) + r"captura_(\d{8})\.json", item["Key"])
        if not m:
            raise ValueError("Clave IPC-35 inválida")
        ymd = m[1]
        fechas.append(date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:])).isoformat())
    return sorted(fechas)


def generar_resumen_avance_s3(
    s3,
    bucket: str,
    fecha_corte: str,
    sha_bronze: str,
    sha_silver: str,
    guardia_resumen: dict,
    *,
    desde_corte_limpio: str = "2026-11-20",
    meta_ventana: int = 21,
) -> dict:
    """Calcula y guarda resumen automático de avance de ventana limpia bajo ``evidencias/operacion/``."""
    from datetime import timedelta
    from infra.capturas_seguras import pagina_global
    from prisma.domain import bmv_core as core

    fechas = []
    cursor = None
    while True:
        lote, cursor = pagina_global(s3, bucket, limite=31, despues=cursor)
        fechas.extend(lote)
        if cursor is None:
            break
    fechas = sorted(set(fechas))
    posteriores = [f for f in fechas if f >= desde_corte_limpio]
    racha = []
    if posteriores:
        conj = set(posteriores)
        actual = date.fromisoformat(posteriores[-1])
        while actual.isoformat() >= desde_corte_limpio:
            if not core.calendario_verificado(actual.year):
                break
            if core.es_sesion_bmv(actual):
                iso = actual.isoformat()
                if iso in conj:
                    racha.append(iso)
                else:
                    break
            actual -= timedelta(days=1)
        racha.reverse()

    resumen = {
        "version": 1,
        "actualizado_en_utc": datetime.now(timezone.utc).isoformat(),
        "ultima_fecha_capturada": fecha_corte,
        "sha256_bronze": sha_bronze,
        "sha256_silver": sha_silver,
        "guardia_resumen": guardia_resumen,
        "capturas_seguras_totales": len(fechas),
        "ventana_limpia": {
            "desde_corte_limpio": desde_corte_limpio,
            "sesiones_consecutivas": len(racha),
            "meta": meta_ventana,
            "faltan": max(0, meta_ventana - len(racha)),
            "completa": len(racha) >= meta_ventana,
            "fechas_racha": racha,
        },
        "emision": "NO_HABILITADA",
    }
    raw = (json.dumps(resumen, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ymd = fecha_corte.replace("-", "")
    clave_corte = f"evidencias/operacion/cortes/avance_{ymd}.json"
    _guardar_inmutable(s3, bucket, clave_corte, raw, "application/json; charset=utf-8")
    # Puntero de último avance (sobrescribible explícitamente; el histórico por fecha es inmutable).
    try:
        s3.put_object(
            Bucket=bucket,
            Key="evidencias/operacion/avance_ventana_limpia.json",
            Body=raw,
            ContentType="application/json; charset=utf-8",
        )
    except TypeError:
        # Dobles de prueba estrictos exigen IfNoneMatch="*".
        _guardar_inmutable(s3, bucket, "evidencias/operacion/avance_ventana_limpia.json", raw, "application/json; charset=utf-8")
    return resumen
