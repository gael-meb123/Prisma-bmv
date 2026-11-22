"""Capa compartida e inmutable de evidencias y gobernanza en S3.

Centraliza evidencias bajo ``evidencias/`` dentro del bucket del proyecto,
sin crear carpetas de datos locales ni modificar históricos previos.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

BUCKET_PRODUCTIVO = "prisma-bmv-datalake-tunombre-2026"
PREFIJO_EVIDENCIAS = "evidencias/"
PREFIJOS_ADMITIDOS = (
    "evidencias/",
    "bronze/",
    "silver/recolector_seguro/precios_ppp/",
    "silver/capturas_seguras/",
    "silver/capturas_en_curso/",
)
MAX_BYTES_EVIDENCIA = 5_000_000


class ConflictoEvidenciaS3(RuntimeError):
    """Se lanza si ya existe un objeto con contenido distinto en una clave inmutable."""


def _validar_clave(key: str) -> None:
    if not isinstance(key, str) or not key or key.startswith("/") or ".." in key.split("/"):
        raise ValueError(f"Clave S3 inválida: {key!r}")
    if not any(key.startswith(prefijo) for prefijo in PREFIJOS_ADMITIDOS):
        raise ValueError(f"Prefijo S3 no autorizado para escritura inmutable: {key!r}")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def escribir_inmutable(
    s3,
    bucket: str,
    key: str,
    raw: bytes,
    content_type: str,
    *,
    max_bytes: int = MAX_BYTES_EVIDENCIA,
) -> dict:
    """Guarda un objeto con ``IfNoneMatch='*'``; idempotente solo si es idéntico byte a byte."""
    _validar_clave(key)
    if not isinstance(raw, bytes) or not raw or len(raw) > max_bytes:
        raise ValueError(f"Contenido inválido o excede límite ({max_bytes} bytes): {key}")
    huella = sha256_bytes(raw)
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=raw, ContentType=content_type, IfNoneMatch="*")
        return {"key": key, "estado": "CREADO", "sha256": huella, "bytes": len(raw)}
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code not in ("PreconditionFailed", "412"):
            raise
        actual = s3.get_object(Bucket=bucket, Key=key)
        anterior = actual["Body"].read(max_bytes + 1)
        if anterior != raw:
            raise ConflictoEvidenciaS3(
                f"Conflicto inmutable en {key}: sha existente {sha256_bytes(anterior)} != {huella}"
            ) from exc
        return {"key": key, "estado": "IDENTICO", "sha256": huella, "bytes": len(raw)}


def serializar_json(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def escribir_json_inmutable(s3, bucket: str, key: str, payload: dict) -> dict:
    return escribir_inmutable(s3, bucket, key, serializar_json(payload), "application/json; charset=utf-8")


def leer_json(s3, bucket: str, key: str, *, opcional: bool = False, max_bytes: int = MAX_BYTES_EVIDENCIA):
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if opcional and code in ("NoSuchKey", "404", "NotFound"):
            return None
        raise
    raw = obj["Body"].read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f"JSON excede límite permitido: {key}")
    return json.loads(raw.decode("utf-8-sig"))


def declaracion_gobernanza(fecha_iso: str) -> dict:
    """Declaración auditable sin almacenar correspondencia privada ni credenciales."""
    return {
        "version": 1,
        "actualizado_en_utc": fecha_iso,
        "ubicacion_evidencias": f"s3://{BUCKET_PRODUCTIVO}/{PREFIJO_EVIDENCIAS}",
        "politica_almacenamiento": "SOLO_S3_SIN_CARPETAS_LOCALES_NUEVAS",
        "bmv": {
            "autorizacion_reportada_por_operador": "USO_ACADEMICO_PRIVADO_CORREO_CONFIDENCIAL",
            "alcance_objetivo_solicitado": "PUBLICO_AMPLIFY_Y_REDISTRIBUCION_PPP",
            "estado_alineacion_alcance": "REQUIERE_CONFIRMACION_REDISTRIBUCION_PUBLICA",
            "correspondencia_almacenada_en_chat_o_s3": False,
            "canal_alterno_mantenimiento": None,
            "nota": (
                "No se almacena ni solicita el correo confidencial de BMV. "
                "Confirmar que el permiso cubre redistribución pública antes de habilitar señales o publicación definitiva."
            ),
        },
        "ipc_35": {
            "estado": "PROVISIONAL_NO_OFICIAL",
            "composicion_oficial_fechada": "PENDIENTE",
            "alias_pendientes": ["RA -> R / A", "LIVEPOLC.1 -> LIVEPOL / C-1"],
            "prefijo_catalogo": "evidencias/catalogo_ipc/",
        },
        "eventos_corporativos": {
            "estado": "PENDIENTE_CRUCE_OFICIAL",
            "estrategia": "MUESTRA_PRIORITARIA_5_EMISORAS_G2_2024_2026",
            "prefijo": "evidencias/eventos_corporativos/v1/",
            "panel_ajustado_habilitado": False,
        },
        "calendario_bmv_2027": {
            "estado": "PENDIENTE_FUENTE_OFICIAL",
            "habilita_operacion": False,
            "prefijo": "evidencias/calendario_bmv/2027/",
        },
        "observaciones_yahoo": {
            "estado_permiso": "EN_TRAMITE",
            "habilitacion_productiva": False,
            "prefijo": "evidencias/observaciones_yahoo/",
            "separacion_estricta": "NUNCA_PPP_BMV_NI_SILVER_NI_INFERENCIA",
        },
        "operacion": {
            "scheduler_habilitado": False,
            "emision_senales": "NO_HABILITADA",
            "estrategia_ventana_21": "ESPERAR_SESIONES_OFICIALES_BMV_HACIA_ADELANTE",
        },
        "iam": {
            "rol_adoptado": "arn:aws:iam::886457183564:role/LabRole",
            "decision": "CONSERVAR_LABROLE_POR_RESTRICCION_CUENTA_EDUCATIVA",
            "motivo": "La cuenta educativa AWS Academy deniega iam:CreateRole y no permite crear roles dedicados.",
            "minimo_privilegio_efectivo": False,
            "propuestas_conservadas": [
                "infra/iam/confianza_recolector_seguro.json",
                "infra/iam/recolector_seguro_minimo.json",
            ],
        },
    }


def estado_permiso_yahoo(fecha_iso: str) -> dict:
    return {
        "version": 1,
        "actualizado_en_utc": fecha_iso,
        "proveedor": "Yahoo Finance",
        "estado": "EN_TRAMITE",
        "habilitacion_permitida": False,
        "alcance_autorizado": None,
        "referencia_autorizacion": None,
        "uso_permitido": ["OBSERVACION_SECUNDARIA_CIERRE_REPORTADO"],
        "uso_prohibido": ["PPP_OFICIAL_BMV", "SILVER_PPP", "GUARDIA_SENALES", "INFERENCIA_MODELOS"],
        "requisitos_activacion": [
            "Registrar estado=APROBADO y habilitacion_permitida=true con alcance_autorizado verificable.",
            "Conservar observaciones archivadas en observaciones/yahoo/<SIMBOLO>/YYYY-MM-DD.json.",
            "Mantener separacion visual/API frente a PPP BMV y nunca alimentar modelos.",
            "Activar YahooObservacionesHabilitadas=true en API Gateway y VITE_YAHOO_OBSERVACIONES=true en Amplify.",
        ],
    }


def estado_calendario_2027(fecha_iso: str) -> dict:
    return {
        "version": 1,
        "anio": 2027,
        "actualizado_en_utc": fecha_iso,
        "estado": "PENDIENTE_FUENTE_OFICIAL",
        "url_oficial": "https://www.bmv.com.mx/es/grupo-bmv/calendario-de-dias-festivos",
        "evidencia_s3_key": None,
        "sha256_evidencia": None,
        "feriados": None,
        "habilita_operacion": False,
    }


def verificar_permiso_yahoo(payload: dict | None) -> tuple[bool, list[str]]:
    """Evalúa si la compuerta de gobernanza Yahoo permite activar el feature flag en producción."""
    errores = []
    if not isinstance(payload, dict):
        return False, ["Falta evidencias/observaciones_yahoo/estado_permiso.json en S3."]
    if payload.get("estado") != "APROBADO":
        errores.append(f"Permiso Yahoo no aprobado (estado={payload.get('estado')!r}).")
    if payload.get("habilitacion_permitida") is not True:
        errores.append("habilitacion_permitida no es true.")
    alcance = payload.get("alcance_autorizado")
    if not isinstance(alcance, str) or not alcance.strip():
        errores.append("Falta alcance_autorizado documentado.")
    ref = payload.get("referencia_autorizacion")
    if not isinstance(ref, str) or not ref.strip():
        errores.append("Falta referencia_autorizacion verificable.")
    prohibidos = set(payload.get("uso_prohibido") or [])
    requeridos = {"PPP_OFICIAL_BMV", "SILVER_PPP", "GUARDIA_SENALES", "INFERENCIA_MODELOS"}
    if not requeridos.issubset(prohibidos):
        errores.append("Debe declararse explícitamente la prohibición de uso en PPP/Silver/guardia/modelos.")
    return not errores, errores


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def validar_sha256(valor: str) -> bool:
    return isinstance(valor, str) and bool(re.fullmatch(r"[0-9a-f]{64}", valor))
