"""
Prisma BMV - AWS Lambda `recolector-diario-bmv`

Runtime: Python 3.11 | Memoria: 512 MB | Timeout: 60 s | Sin VPC
Layer:   AWSSDKPandas-Python311 (pandas, numpy, pyarrow, boto3)
Disparo: EventBridge Scheduler `DisparadorDiarioBMV`
         cron(45 16 ? * MON-FRI *) en America/Mexico_City

Flujo (arquitectura Medallion en S3):
  1. Descarga el boletín RSS oficial de la BMV del día.
  2. Bronze: guarda el HTML crudo y su firma SHA-256 (inmutables; nunca se sobrescriben).
  3. Silver: 15 emisoras con PPP verificado o hueco documentado (cero imputación),
     particionado en silver/precios_ppp/YYYY/MM/.
  4. Gold: inferencia del panel G2 con ventana estricta de 21 sesiones y parámetros
     congelados del registro oficial; seguimiento t+1..t+5 de señales abiertas.

Evento opcional para reprocesar una fecha concreta (backfill): {"fecha": "20261103"}

Variables de entorno:
  BUCKET_NAME   (obligatoria) bucket privado del data lake
  MODELOS_KEY   gold/modelos/registro_modelos_g2_oficial.json
  SERIE_KEY     silver/serie_unificada_reciente.csv
  GOLD_G2_KEY   gold/senales_g2/registro_senales_prospectivas_panel_g2.csv
  FERIADOS_BMV_EXTRA  fechas inhábiles adicionales (años futuros), separadas por coma
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

try:  # En la Lambda bmv_core.py viaja junto a este archivo dentro del .zip
    import bmv_core as core
except ImportError:  # En el repositorio (pruebas locales) vive en prisma/domain
    from prisma.domain import bmv_core as core

MODELOS_KEY = os.environ.get("MODELOS_KEY", "gold/modelos/registro_modelos_g2_oficial.json")
SERIE_KEY = os.environ.get("SERIE_KEY", "silver/serie_unificada_reciente.csv")
GOLD_G2_KEY = os.environ.get(
    "GOLD_G2_KEY", "gold/senales_g2/registro_senales_prospectivas_panel_g2.csv"
)
USER_AGENT = "Mozilla/5.0 (compatible; PrismaBMV-Recolector/2.0; +https://prismabmv.com)"
TIMEOUT_DESCARGA_S = 20
VENTANA_SERIE_SESIONES = 60  # suficiente para 21 sesiones + seguimiento t+5


def _ahora_cdmx() -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Mexico_City"))
    except Exception:  # México no aplica horario de verano desde 2022: UTC-6 fijo
        return datetime.now(timezone(timedelta(hours=-6)))


def _log(evento: str, **campos: Any) -> None:
    """Log estructurado en una línea JSON (consultable con CloudWatch Logs Insights)."""
    print(json.dumps({"evento": evento, **campos}, ensure_ascii=False, default=str))


def _existe(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def _leer_texto(s3, bucket: str, key: str) -> str | None:
    try:
        return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8-sig")
    except Exception:
        return None


def _leer_csv(s3, bucket: str, key: str) -> pd.DataFrame:
    txt = _leer_texto(s3, bucket, key)
    return pd.read_csv(io.StringIO(txt)) if txt else pd.DataFrame()


def _escribir_csv(s3, bucket: str, key: str, df: pd.DataFrame) -> None:
    # UTF-8 sin BOM: Athena (OpenCSVSerde) leería el BOM como parte del primer encabezado.
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=df.to_csv(index=False).encode("utf-8"),
        ContentType="text/csv; charset=utf-8",
    )


def tipar_gold(gold: pd.DataFrame) -> pd.DataFrame:
    """Orden canónico y enteros sin '.0' (Athena convertiría '2.0' en NULL en una columna INT)."""
    out = gold.reindex(columns=list(core.COLUMNAS_GOLD_G2))
    for col in ("prediccion_clase", "sesiones_transcurridas", "n_train_panel"):
        out[col] = pd.to_numeric(out[col], errors="coerce").round().astype("Int64")
    return out


def descargar_boletin(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_DESCARGA_S) as resp:
        return resp.read()


def guardar_bronze(s3, bucket: str, fecha_str: str, html_bytes: bytes, sha256: str) -> dict[str, Any]:
    """Escritura inmutable: si ya existe el boletín se compara la firma y nunca se sobrescribe."""
    prefijo = f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/boletin_{fecha_str}"
    key_html, key_sha = f"{prefijo}.html", f"{prefijo}.sha256"

    if _existe(s3, bucket, key_sha):
        sha_previo = (_leer_texto(s3, bucket, key_sha) or "").strip()
        if sha_previo == sha256:
            return {"estado": "YA_INGERIDO_FIRMA_IDENTICA", "key_html": key_html}
        # La BMV republicó contenido distinto en la misma URL: se preserva como evidencia.
        key_div = f"{prefijo}__{sha256[:12]}"
        s3.put_object(Bucket=bucket, Key=f"{key_div}.html", Body=html_bytes, ContentType="text/html")
        s3.put_object(Bucket=bucket, Key=f"{key_div}.sha256", Body=sha256.encode(), ContentType="text/plain")
        return {"estado": "HASH_DIVERGENTE", "key_html": key_html, "sha_previo": sha_previo,
                "key_divergente": f"{key_div}.html"}

    s3.put_object(Bucket=bucket, Key=key_html, Body=html_bytes, ContentType="text/html")
    s3.put_object(Bucket=bucket, Key=key_sha, Body=sha256.encode(), ContentType="text/plain")
    return {"estado": "NUEVO", "key_html": key_html}


def actualizar_serie(serie: pd.DataFrame, nuevas: pd.DataFrame, fecha_iso: str) -> pd.DataFrame:
    comb = pd.concat([serie, nuevas], ignore_index=True) if not serie.empty else nuevas.copy()
    comb["estado_captura"] = core.normalizar_estado_captura(comb["estado_captura"])
    comb = comb.drop_duplicates(["fecha", "emisora"], keep="last")
    fechas = sorted(comb["fecha"].astype(str).unique())
    conservar = set(fechas[-VENTANA_SERIE_SESIONES:])
    comb = comb[comb["fecha"].astype(str).isin(conservar)]
    return comb.sort_values(["fecha", "emisora"]).reset_index(drop=True).reindex(columns=list(core.COLUMNAS_SILVER))


def lambda_handler(event, context, s3_client=None, descargador=None):
    import boto3  # importación diferida: permite probar el módulo sin AWS

    bucket = os.environ["BUCKET_NAME"]
    s3 = s3_client or boto3.client("s3")
    descargar = descargador or descargar_boletin

    fecha_str = str(event["fecha"]) if isinstance(event, dict) and event.get("fecha") else _ahora_cdmx().strftime("%Y%m%d")
    fecha_iso = f"{fecha_str[:4]}-{fecha_str[4:6]}-{fecha_str[6:]}"
    url = core.url_boletin(fecha_str)
    resultado: dict[str, Any] = {"fecha": fecha_iso, "url_fuente": url}

    if not core.es_sesion_bmv(datetime.strptime(fecha_iso, "%Y-%m-%d").date()):
        resultado["estado"] = "DIA_INHABIL_BMV"
        _log("fin", **resultado)
        return {"statusCode": 200, "body": json.dumps(resultado)}

    # 1. Descarga del boletín oficial
    try:
        html_bytes = descargar(url)
    except urllib.error.HTTPError as e:
        resultado.update(estado="BOLETIN_NO_PUBLICADO", detalle=f"HTTP {e.code}")
        _log("fin", **resultado)
        return {"statusCode": 404, "body": json.dumps(resultado)}
    except Exception as e:  # timeout, DNS, etc.
        resultado.update(estado="ERROR_DESCARGA", detalle=str(e))
        _log("fin", **resultado)
        return {"statusCode": 502, "body": json.dumps(resultado)}

    sha256 = hashlib.sha256(html_bytes).hexdigest()
    resultado.update(sha256=sha256, bytes=len(html_bytes))

    # 2. Bronze (inmutable)
    bronze = guardar_bronze(s3, bucket, fecha_str, html_bytes, sha256)
    resultado["bronze"] = bronze
    if bronze["estado"] == "HASH_DIVERGENTE":
        resultado["estado"] = "HASH_DIVERGENTE_REQUIERE_REVISION"
        _log("alerta_integridad", **resultado)
        return {"statusCode": 409, "body": json.dumps(resultado)}

    # 3. Silver (15 emisoras, cero imputación)
    filas = core.registros_silver(fecha_iso, core.parse_bulletin_quotes(html_bytes), url, sha256)
    df_dia = pd.DataFrame(filas)[list(core.COLUMNAS_SILVER)]
    key_silver = f"silver/precios_ppp/{fecha_str[:4]}/{fecha_str[4:6]}/ppp_15_emisoras_{fecha_str}.csv"
    _escribir_csv(s3, bucket, key_silver, df_dia)
    verificadas = int((df_dia["estado_captura"] == core.ESTADO_PUBLICADO).sum())
    resultado.update(silver=key_silver, emisoras_verificadas=verificadas,
                     emisoras_con_hueco=len(df_dia) - verificadas)

    serie = actualizar_serie(_leer_csv(s3, bucket, SERIE_KEY), df_dia, fecha_iso)
    _escribir_csv(s3, bucket, SERIE_KEY, serie)

    # 4. Gold: inferencia G2 + seguimiento prospectivo
    try:
        modelos_txt = _leer_texto(s3, bucket, MODELOS_KEY)
        nuevas: list[dict[str, Any]] = []
        if not modelos_txt:
            resultado["inferencia_g2"] = "OMITIDA_SIN_REGISTRO_DE_MODELOS"
        elif not core.calendario_verificado(int(fecha_iso[:4])):
            resultado["inferencia_g2"] = "OMITIDA_CALENDARIO_BMV_NO_VERIFICADO"
        else:
            est, eleg = core.extraer_ventanas_panel(serie, fecha_iso)
            _escribir_csv(s3, bucket, f"gold/auditoria_ventanas_g2/estado_ventanas_{fecha_str}.csv", est)
            ts = datetime.now(timezone.utc).isoformat()
            nuevas = core.inferir_panel_g2(eleg, json.loads(modelos_txt), fecha_iso, sha256, url, ts)
            resultado["emisoras_bloqueadas_por_huecos"] = est.loc[
                ~est["ventana_21_completa_apta_inferencia"], "emisora"].tolist()

        gold = _leer_csv(s3, bucket, GOLD_G2_KEY)
        if nuevas:
            df_nuevas = pd.DataFrame(nuevas)
            # keep="first": una señal emitida nunca se reescribe (registro prospectivo inmutable)
            gold = (pd.concat([gold, df_nuevas], ignore_index=True) if not gold.empty else df_nuevas)
            gold = gold.drop_duplicates("id_senal_g2", keep="first")
        if not gold.empty:
            gold = core.actualizar_seguimiento(gold, serie, fecha_iso)
            _escribir_csv(s3, bucket, GOLD_G2_KEY, tipar_gold(gold))
        resultado["senales_g2_nuevas"] = len(nuevas)
        resultado["consensos"] = {
            r["emisora"]: r["estado_consenso_g2"] for r in nuevas
        }
    except Exception as e:  # la ingesta Bronze/Silver ya quedó persistida
        resultado["inferencia_g2"] = f"ERROR: {type(e).__name__}: {e}"
        _log("aviso_gold", detalle=resultado["inferencia_g2"])

    resultado["estado"] = "EXITO"
    _log("fin", **resultado)
    return {"statusCode": 200, "body": json.dumps(resultado, default=str)}
