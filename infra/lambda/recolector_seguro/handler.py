"""Captura BMV conservadora; no modifica instantáneas ni lee o escribe Gold.

No sustituir la Lambda activa ni conectar Scheduler sin validar el despliegue,
la visibilidad de fechas en la API y las condiciones de uso de la fuente.
"""
import csv
import hashlib
import io
import json
import os
import urllib.request
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from prisma.data.captura_ampliada import extraer
from prisma.data.ipc35_almacen import generar_resumen_avance_s3, guardar_corte_ipc35
from prisma.domain import bmv_core as core
from scripts.auditar_boletin_diario import auditar
from infra.lambda_guardia_adapter import auditar_s3

BUCKET = "prisma-bmv-datalake-tunombre-2026"
MAX_BYTES = 1_000_000


class ConflictoInmutable(RuntimeError):
    pass


class _LecturaGuardia:
    """Presenta solo el corte actual aislado a la guardia; no modifica lectores legados."""
    def __init__(self, s3, legado, aislado):
        self.s3, self.legado, self.aislado = s3, legado, aislado

    def get_object(self, **kwargs):
        if kwargs.get("Key") == self.legado:
            kwargs = {**kwargs, "Key": self.aislado}
        return self.s3.get_object(**kwargs)


def _guardar(s3, bucket, key, raw, tipo):
    """Put condicional atómico. Los errores distintos de 412 no son ausencia."""
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=raw, ContentType=tipo, IfNoneMatch="*")
        return "CREADO"
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code not in ("PreconditionFailed", "412"):
            raise
        response = s3.get_object(Bucket=bucket, Key=key)
        if response.get("ContentLength", 0) > MAX_BYTES:
            raise ConflictoInmutable(f"Objeto existente demasiado grande: {key}") from exc
        anterior = response["Body"].read(MAX_BYTES + 1)
        if anterior != raw:
            raise ConflictoInmutable(f"Contenido existente diferente: {key}") from exc
        return "IDENTICO"


def descargar(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PrismaBMV-CapturaSegura/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Boletín vacío o demasiado grande.")
    return raw


class _Catalogo:
    # Son los 15 pares preexistentes, no una certificación de composición IPC.
    version = "panel-15-existente-v1"

    def en_corte(self, fecha):
        return [SimpleNamespace(emisora=e, serie=s, origen="panel_15_existente",
                                blackrock="", estado_composicion="NO_VALIDADO_IPC",
                                estado_mapeo="PANEL_EXISTENTE")
                for e, s, _, _ in core.EMISORAS_15]


def _filas(raw, corte, url):
    extraido = extraer(raw, corte, _Catalogo(), url)
    cotizaciones = {}
    for fila in extraido["filas"]:
        estado = fila["estado_captura"]
        if estado in ("CONFLICTO_ENTRE_FILAS", "FILA_INVALIDA_REQUIERE_REVISION"):
            raise ValueError("Cotización ambigua o inválida; requiere revisión.")
        if estado == "PPP_OBSERVADO_MAPEO_PROVISIONAL":
            ppp, anterior = fila["ppp_bmv_mxn"], fila["anterior_bmv_mxn"]
            cotizaciones[(fila["emisora_propuesta"], fila["serie_propuesta"])] = {
                "ppp": ppp, "ultimo": fila["ultimo_bmv_mxn"], "anterior": anterior,
                "variacion_ppp_vs_anterior_pct": round((ppp / anterior - 1) * 100, 2),
            }
    if not cotizaciones:
        raise ValueError("No se encontraron cotizaciones para el panel.")
    filas = core.registros_silver(corte.isoformat(), cotizaciones, url, extraido["sha256_boletin"])
    for fila in filas:
        if fila["estado_captura"] == core.ESTADO_HUECO:
            fila["estado_captura"] = "NO_ENCONTRADO_EN_TABLAS_BOLETIN"
            fila["evidencia_exacta"] = "No aparece en las tablas de cotizaciones reconocidas; no acredita ausencia en otras fuentes."
    evidencia = auditar(raw, filas, corte.isoformat())
    if any(f["resultado"] not in ("COINCIDE_PPP_Y_HASH", "NO_EVALUADO_NO_VERIFICADO")
           for f in evidencia["filas"]):
        raise ValueError("La verificación del boletín no coincide.")
    return filas


def ejecutar(evento, s3, descargar_boletin, bucket, guardia=auditar_s3, hoy=None, registrar_extras=False):
    if bucket != BUCKET:
        raise ValueError("Bucket de producción no admitido.")
    if not isinstance(evento, dict) or set(evento) - {"fecha", "instante_programado"}:
        raise ValueError("Evento inválido.")
    if "instante_programado" in evento:
        if "fecha" in evento:
            raise ValueError("No combinar fecha e instante programado")
        instante = evento["instante_programado"]
        if not isinstance(instante, str):
            raise ValueError("Instante programado inválido")
        instante = datetime.fromisoformat(instante.replace("Z", "+00:00"))
        if instante.tzinfo is None:
            raise ValueError("Instante sin zona horaria")
        evento = {"fecha": instante.astimezone(ZoneInfo("America/Mexico_City")).date().isoformat()}
    valor = evento.get("fecha")
    if valor is not None and not isinstance(valor, str):
        raise ValueError("Fecha debe ser ISO.")
    corte = date.fromisoformat(valor) if valor is not None else (hoy or datetime.now(ZoneInfo("America/Mexico_City")).date())
    if valor is not None and corte.isoformat() != valor:
        raise ValueError("Fecha debe ser ISO.")
    # Los años no verificados se bloquean, incluso para ingesta.
    if not core.calendario_verificado(corte.year) or corte.year != 2026:
        raise ValueError("Calendario no validado.")
    if not core.es_sesion_bmv(corte):
        return {"fecha": corte.isoformat(), "estado": "DIA_INHABIL", "emision": "NO_HABILITADA"}
    url = core.url_boletin(corte.strftime("%Y%m%d"))
    raw = descargar_boletin(url)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError("Boletín inválido.")
    filas = _filas(raw, corte, url)
    sha = hashlib.sha256(raw).hexdigest()
    ymd = corte.strftime("%Y%m%d")
    bronze = f"bronze/{corte:%Y/%m}/boletin_{ymd}.html"
    silver_legado = f"silver/precios_ppp/{corte:%Y/%m}/ppp_15_emisoras_{ymd}.csv"
    silver = f"silver/recolector_seguro/precios_ppp/{corte:%Y/%m}/ppp_15_emisoras_{ymd}.csv"
    # La API reconoce una captura iniciada incluso si falla antes del manifiesto.
    # Se conserva para evitar confundir una captura parcial con un diario legado.
    inicio = f"silver/capturas_en_curso/{corte:%Y/%m}/captura_{ymd}.json"
    _guardar(s3, bucket, inicio,
             json.dumps({"version": 1, "fecha": corte.isoformat()}, sort_keys=True,
                        separators=(",", ":")).encode(), "application/json")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(core.COLUMNAS_SILVER), lineterminator="\n")
    writer.writeheader()
    writer.writerows(filas)
    try:
        estado_bronze = _guardar(s3, bucket, bronze, raw, "text/html; charset=utf-8")
    except ConflictoInmutable:
        # Conserva la nueva versión sin sustituir la anterior ni promover Silver.
        key = f"cuarentena/recolector-seguro/{ymd}/{sha}.html"
        _guardar(s3, bucket, key, raw, "text/html; charset=utf-8")
        raise
    csv_bytes = buffer.getvalue().encode("utf-8")
    estado_silver = _guardar(s3, bucket, silver, csv_bytes, "text/csv; charset=utf-8")
    # Guardia obligatoria, pero aun si es apta la emisión y seguimiento siguen bloqueados.
    resultado = guardia({"fecha": corte.isoformat(), "modo": "auditoria_s3"},
                        _LecturaGuardia(s3, silver_legado, silver), bucket)
    if (not isinstance(resultado, dict) or resultado.get("fecha") != corte.isoformat()
            or resultado.get("origen") != "SILVER_DIARIO_Y_BRONZE_S3"
            or resultado.get("emision") != "NO_HABILITADA" or not isinstance(resultado.get("evaluacion"), dict)
            or set(resultado["evaluacion"]) != {"AMX", "FEMSA", "GFNORTE", "GMEXICO", "WALMEX"}):
        raise ValueError("Respuesta de guardia inválida.")
    # El manifiesto es el commit: sin él, el lector no debe descubrir una
    # captura parcial. Es determinista y se crea solo después de la guardia.
    manifiesto_key = f"silver/capturas_seguras/{corte:%Y/%m}/captura_{ymd}.json"
    manifiesto = {"version": 1, "fecha": corte.isoformat(), "bronze": bronze,
                  "sha256_bronze": sha, "silver": silver,
                  "sha256_silver": hashlib.sha256(csv_bytes).hexdigest(),
                  "guardia": "COMPLETADA_SIN_EMISION"}
    estado_manifiesto = _guardar(s3, bucket, manifiesto_key,
                                  json.dumps(manifiesto, sort_keys=True, separators=(",", ":")).encode(),
                                  "application/json")
    # Almacenamiento versionado provisional IPC-35 y resumen automático de avance en S3
    # (prefijos completamente separados; activados en lambda_handler sin alterar pruebas base).
    estado_ipc35 = None
    avance_ventana = None
    if registrar_extras:
        try:
            estado_ipc35 = guardar_corte_ipc35(s3, bucket, raw, corte.isoformat(), url)
        except Exception:
            estado_ipc35 = {"estado": "NO_ESCRITO_REVISAR"}
        try:
            avance_ventana = generar_resumen_avance_s3(
                s3, bucket, corte.isoformat(), sha, hashlib.sha256(csv_bytes).hexdigest(),
                resultado.get("resumen_evidencia", {}),
            ).get("ventana_limpia")
        except Exception:
            avance_ventana = None
    salida = {"fecha": corte.isoformat(), "estado": "CAPTURADO_SIN_SENALES", "sha256": sha,
              "bronze": estado_bronze, "silver": estado_silver, "manifiesto": estado_manifiesto,
              "guardia": resultado, "emision": "NO_HABILITADA"}
    if estado_ipc35 is not None:
        salida["ipc35_provisional"] = estado_ipc35
    if avance_ventana is not None:
        salida["avance_ventana"] = avance_ventana
    return salida


def lambda_handler(event, context):
    import boto3
    resultado = ejecutar(event, boto3.client("s3"), descargar, os.environ["BUCKET_NAME"], registrar_extras=True)
    print(json.dumps(resultado, ensure_ascii=False))
    return resultado
