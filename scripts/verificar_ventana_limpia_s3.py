"""Verifica recuperación de boletines BMV y avance de ventana limpia (21 sesiones) hacia adelante.

Operación de solo lectura sobre BMV y S3 (con opción explícita ``--guardar-s3`` para
archivar el reporte inmutable bajo ``evidencias/auditorias/``). Nunca activa Scheduler ni señales.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infra.capturas_seguras import captura as leer_captura_segura, manifiesto as leer_manifiesto, pagina_global
from prisma.data.captura_ampliada import _Tablas, _fecha_documento
from prisma.data.evidencias_s3 import BUCKET_PRODUCTIVO, escribir_json_inmutable, sha256_bytes, timestamp_slug
from prisma.domain import bmv_core as core

CORTE_INICIO_VENTANA_LIMPIA = "2026-11-20"
META_SESIONES_VENTANA = 21


def diagnosticar_html_boletin(raw: bytes, fecha_esperada: str) -> dict:
    """Comprueba sin escribir si un HTML descargado de BMV es un boletín válido o mantenimiento."""
    texto = raw.decode("utf-8-sig", errors="replace")
    mantenimiento = "sitio grupo bmv no disponible" in texto.casefold()
    try:
        fecha_doc = _fecha_documento(texto).isoformat()
    except ValueError:
        fecha_doc = None
    parser = _Tablas()
    parser.feed(texto)
    tablas_validas = sum(
        1 for tabla in parser.tablas
        if any([c.casefold() for c in fila[:5]] == ["emisora", "serie", "último", "anterior", "ppp"] for fila in tabla)
    )
    valido = (not mantenimiento) and (fecha_doc == fecha_esperada) and (tablas_validas > 0)
    return {
        "fecha_esperada": fecha_esperada,
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "mantenimiento_detectado": mantenimiento,
        "fecha_documento": fecha_doc,
        "tablas_cotizaciones_reconocidas": tablas_validas,
        "boletin_valido": valido,
    }


def descargar_diagnostico(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PrismaBMV-DiagnosticoSoloLectura/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read(1_000_001)


def listar_capturas_seguras_validas(s3, bucket: str) -> tuple[list[str], list[dict]]:
    fechas_validas, invalidas = [], []
    cursor = None
    while True:
        lote, cursor = pagina_global(s3, bucket, limite=31, despues=cursor)
        for f in lote:
            try:
                man = leer_manifiesto(s3, bucket, f)
                leer_captura_segura(s3, bucket, man)
                fechas_validas.append(f)
            except Exception as exc:
                invalidas.append({"fecha": f, "error": str(exc)})
        if cursor is None:
            break
    return sorted(fechas_validas), invalidas


def calcular_racha_limpia(fechas_confirmadas: list[str], desde_iso: str = CORTE_INICIO_VENTANA_LIMPIA) -> dict:
    """Cuenta la racha consecutiva más reciente de sesiones BMV confirmadas a partir de ``desde_iso``."""
    posteriores = sorted(f for f in fechas_confirmadas if f >= desde_iso)
    if not posteriores:
        return {
            "desde_corte_limpio": desde_iso,
            "sesiones_consecutivas_confirmadas": 0,
            "meta_ventana": META_SESIONES_VENTANA,
            "faltan_para_ventana_limpia": META_SESIONES_VENTANA,
            "ventana_limpia_completa": False,
            "racha_fechas": [],
        }
    confirmadas_set = set(posteriores)
    ultima = date.fromisoformat(posteriores[-1])
    racha = []
    actual = ultima
    while actual.isoformat() >= desde_iso:
        if not core.calendario_verificado(actual.year):
            break
        if core.es_sesion_bmv(actual):
            iso = actual.isoformat()
            if iso in confirmadas_set:
                racha.append(iso)
            else:
                break
        actual -= timedelta(days=1)
    racha.reverse()
    conteo = len(racha)
    return {
        "desde_corte_limpio": desde_iso,
        "sesiones_consecutivas_confirmadas": conteo,
        "meta_ventana": META_SESIONES_VENTANA,
        "faltan_para_ventana_limpia": max(0, META_SESIONES_VENTANA - conteo),
        "ventana_limpia_completa": conteo >= META_SESIONES_VENTANA,
        "racha_fechas": racha,
    }


def evaluar_estado(
    s3,
    bucket: str,
    fecha_bmv: str,
    *,
    descargar_fn=descargar_diagnostico,
    desde_iso: str = CORTE_INICIO_VENTANA_LIMPIA,
) -> dict:
    url = core.url_boletin(fecha_bmv.replace("-", ""))
    try:
        diagnostico_bmv = diagnosticar_html_boletin(descargar_fn(url), fecha_bmv)
        diagnostico_bmv["url"] = url
        diagnostico_bmv["error_red"] = None
    except Exception as exc:
        diagnostico_bmv = {
            "fecha_esperada": fecha_bmv,
            "url": url,
            "boletin_valido": False,
            "mantenimiento_detectado": None,
            "error_red": str(exc),
        }

    fechas_ok, invalidas = listar_capturas_seguras_validas(s3, bucket)
    racha = calcular_racha_limpia(fechas_ok, desde_iso=desde_iso)

    if not diagnostico_bmv["boletin_valido"]:
        siguiente_paso = "ESPERAR_RECUPERACION_BMV_NO_ACTIVAR_SCHEDULER"
    elif racha["sesiones_consecutivas_confirmadas"] == 0:
        siguiente_paso = "EJECUTAR_PRUEBA_AISLADA_Y_PRIMERA_CAPTURA_SEGURA_PRODUCTIVA"
    elif not racha["ventana_limpia_completa"]:
        siguiente_paso = "CONTINUAR_CAPTURAS_SEGURAS_HASTA_21_DE_21"
    else:
        siguiente_paso = "EVALUAR_AUDITORIA_MODELOS_Y_EVENTOS_ANTES_DE_SENALES"

    return {
        "version": 1,
        "generado_en_utc": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "diagnostico_bmv": diagnostico_bmv,
        "capturas_seguras_totales": len(fechas_ok),
        "capturas_seguras_fechas": fechas_ok,
        "capturas_invalidas": invalidas,
        "ventana_limpia_hacia_adelante": racha,
        "siguiente_paso_operativo": siguiente_paso,
        "flujo_obligatorio_activacion": [
            "1. Diagnostico sin escrituras del boletin BMV.",
            "2. Prueba en Lambda aislada prisma-bmv-recolector-seguro-pruebas-2026.",
            "3. Captura segura productiva en prisma-bmv-recolector-seguro-operacion-202.",
            "4. Verificacion en API/frontend y revision de SQS/alarmas (0 errores).",
            "5. Evaluacion explicita de Scheduler; senales bloqueadas hasta validar 21/21, ajustes y modelos.",
        ],
        "scheduler_activado_por_script": False,
        "emision": "NO_HABILITADA",
    }


def ultima_sesion_hasta(hoy: date) -> str:
    actual = hoy
    while not (core.calendario_verificado(actual.year) and core.es_sesion_bmv(actual)):
        actual -= timedelta(days=1)
    return actual.isoformat()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--fecha-bmv", default=None, help="Sesión ISO a diagnosticar en BMV (por defecto última sesión hábil CDMX)")
    p.add_argument("--desde", default=CORTE_INICIO_VENTANA_LIMPIA)
    p.add_argument("--guardar-s3", action="store_true")
    args = p.parse_args()

    fecha_bmv = args.fecha_bmv or ultima_sesion_hasta(datetime.now(ZoneInfo("America/Mexico_City")).date())
    import boto3
    s3 = boto3.client("s3", region_name=args.region)
    reporte = evaluar_estado(s3, args.bucket, fecha_bmv, desde_iso=args.desde)
    if args.guardar_s3:
        clave = f"evidencias/auditorias/ventana_limpia_{timestamp_slug()}.json"
        reporte["reporte_s3"] = escribir_json_inmutable(s3, args.bucket, clave, reporte)
    print(json.dumps(reporte, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
