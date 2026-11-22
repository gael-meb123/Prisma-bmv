"""Audita e incorpora boletines HTML BMV históricos a S3 de forma inmutable.

Concilia cada boletín contra la instantánea ``silver/serie_unificada_reciente.csv``
para garantizar compatibilidad total con API Gateway y guardia de señales,
sin sobrescribir Silver legado ni activar emisión.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import io
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infra.capturas_seguras import captura as validar_captura_segura, manifiesto as validar_manifiesto
from prisma.data.evidencias_s3 import (
    BUCKET_PRODUCTIVO,
    escribir_inmutable,
    escribir_json_inmutable,
    timestamp_slug,
)
from prisma.domain import bmv_core as core
from scripts.auditar_boletin_diario import auditar as auditar_boletin


ESTADOS_HUECO_LEGADO = frozenset({
    core.ESTADO_HUECO,
    "NO_PUBLICADO_EN_BOLETIN_RSS_DEL_DIA",
})


def _numero(valor):
    try:
        n = float(valor)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def preparar_corte(raw: bytes, fecha: str, snapshot_filas: list[dict] | None = None) -> dict:
    """Valida un boletín HTML y construye el CSV Silver y manifiesto deterministas."""
    corte = date.fromisoformat(fecha)
    if corte.isoformat() != fecha:
        raise ValueError(f"Fecha no canónica: {fecha}")
    if not core.calendario_verificado(corte.year) or not core.es_sesion_bmv(corte):
        raise ValueError(f"Fecha no corresponde a sesión BMV validada: {fecha}")
    rec = importlib.import_module("infra.lambda.recolector_seguro.handler")
    ymd = corte.strftime("%Y%m%d")
    url = core.url_boletin(ymd)
    sha = hashlib.sha256(raw).hexdigest()

    filas = rec._filas(raw, corte, url)
    conciliacion = {"en_instantanea": False, "sha_coincide_instantanea": None, "huecos_normalizados_legado": 0}

    if snapshot_filas is not None:
        snap_dia = {(r["emisora"], r["serie"]): r for r in snapshot_filas if r.get("fecha") == fecha}
        if snap_dia:
            conciliacion["en_instantanea"] = True
            shas_snap = {r.get("sha256_boletin", "") for r in snap_dia.values() if r.get("sha256_boletin")}
            if shas_snap and shas_snap != {sha}:
                raise ValueError(f"SHA-256 del boletín {fecha} difiere de la instantánea ({shas_snap} != {sha}).")
            conciliacion["sha_coincide_instantanea"] = shas_snap == {sha}
            for fila in filas:
                clave = (fila["emisora"], fila["serie"])
                anterior = snap_dia.get(clave)
                if anterior is None:
                    continue
                ppp_nuevo = _numero(fila.get("ppp_bmv_mxn"))
                ppp_ant = _numero(anterior.get("ppp_bmv_mxn"))
                if ppp_nuevo != ppp_ant:
                    raise ValueError(f"Discrepancia PPP en {fecha} {clave}: instantánea={ppp_ant} vs boletín={ppp_nuevo}")
                # Preservar la etiqueta exacta de hueco ya presente en la instantánea evita 503
                # en la validación estricta de infra/api_gateway_aislada/handler.py.
                estado_ant = anterior.get("estado_captura")
                if (fila["estado_captura"] == "NO_ENCONTRADO_EN_TABLAS_BOLETIN"
                        and estado_ant in ESTADOS_HUECO_LEGADO
                        and ppp_nuevo is None and ppp_ant is None):
                    fila["estado_captura"] = estado_ant
                    conciliacion["huecos_normalizados_legado"] += 1
                elif estado_ant != fila["estado_captura"]:
                    raise ValueError(
                        f"Estado incompatible en {fecha} {clave}: "
                        f"instantánea={anterior.get('estado_captura')} vs boletín={fila['estado_captura']}"
                    )

    auditoria = auditar_boletin(raw, filas, fecha)
    if any(r["resultado"] not in ("COINCIDE_PPP_Y_HASH", "NO_EVALUADO_NO_VERIFICADO") for r in auditoria["filas"]):
        raise ValueError(f"Auditoría de boletín fallida en {fecha}: {auditoria['resumen']}")

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(core.COLUMNAS_SILVER), lineterminator="\n")
    writer.writeheader()
    writer.writerows(filas)
    csv_bytes = buf.getvalue().encode("utf-8")
    sha_csv = hashlib.sha256(csv_bytes).hexdigest()

    bronze_key = f"bronze/{corte:%Y/%m}/boletin_{ymd}.html"
    silver_key = f"silver/recolector_seguro/precios_ppp/{corte:%Y/%m}/ppp_15_emisoras_{ymd}.csv"
    manifiesto_key = f"silver/capturas_seguras/{corte:%Y/%m}/captura_{ymd}.json"
    manifiesto_obj = {
        "version": 1,
        "fecha": fecha,
        "bronze": bronze_key,
        "sha256_bronze": sha,
        "silver": silver_key,
        "sha256_silver": sha_csv,
        "guardia": "COMPLETADA_SIN_EMISION",
    }
    return {
        "fecha": fecha,
        "bronze_key": bronze_key,
        "silver_key": silver_key,
        "manifiesto_key": manifiesto_key,
        "raw_html": raw,
        "csv_bytes": csv_bytes,
        "manifiesto": manifiesto_obj,
        "sha256_bronze": sha,
        "sha256_silver": sha_csv,
        "resumen_auditoria": auditoria["resumen"],
        "conciliacion": conciliacion,
    }


def incorporar_en_s3(s3, bucket: str, cortes: list[dict], *, aplicar: bool) -> dict:
    """Ejecuta en modo dry-run o escribe inmutablemente Bronze, Silver seguro y Manifiesto."""
    resultados = []
    for item in cortes:
        entrada = {
            "fecha": item["fecha"],
            "bronze_key": item["bronze_key"],
            "silver_key": item["silver_key"],
            "manifiesto_key": item["manifiesto_key"],
            "sha256_bronze": item["sha256_bronze"],
            "sha256_silver": item["sha256_silver"],
            "resumen_auditoria": item["resumen_auditoria"],
            "conciliacion": item["conciliacion"],
            "modo": "APLICADO" if aplicar else "DRY_RUN",
        }
        if aplicar:
            r_bronze = escribir_inmutable(s3, bucket, item["bronze_key"], item["raw_html"], "text/html; charset=utf-8")
            r_silver = escribir_inmutable(s3, bucket, item["silver_key"], item["csv_bytes"], "text/csv; charset=utf-8")
            manifiesto_bytes = json.dumps(item["manifiesto"], sort_keys=True, separators=(",", ":")).encode("utf-8")
            r_man = escribir_inmutable(s3, bucket, item["manifiesto_key"], manifiesto_bytes, "application/json")
            # Relectura inmediata con el lector oficial compartido para garantizar integridad.
            dato = validar_manifiesto(s3, bucket, item["fecha"])
            validar_captura_segura(s3, bucket, dato)
            entrada["escrituras"] = {
                "bronze": r_bronze["estado"],
                "silver": r_silver["estado"],
                "manifiesto": r_man["estado"],
            }
            entrada["verificado_lector_compartido"] = True
        resultados.append(entrada)

    reporte = {
        "version": 1,
        "generado_en_utc": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "modo": "APLICADO" if aplicar else "DRY_RUN",
        "total_cortes": len(resultados),
        "emision": "NO_HABILITADA",
        "cortes": resultados,
    }
    if aplicar:
        clave_reporte = f"evidencias/auditorias/incorporacion_boletines_{timestamp_slug()}.json"
        res_rep = escribir_json_inmutable(s3, bucket, clave_reporte, reporte)
        reporte["reporte_s3"] = res_rep
    return reporte


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--origen", type=Path, required=True, help="Carpeta origen con boletin_YYYYMMDD.html")
    p.add_argument("--fechas", nargs="+", required=True, help="Fechas ISO AAAA-MM-DD a auditar/incorporar")
    p.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--aplicar", action="store_true", help="Escribir inmutablemente en S3 (sin este flag es dry-run)")
    args = p.parse_args()

    import boto3
    s3 = boto3.client("s3", region_name=args.region)
    raw_snap = s3.get_object(Bucket=args.bucket, Key="silver/serie_unificada_reciente.csv")["Body"].read()
    snap_filas = list(csv.DictReader(io.StringIO(raw_snap.decode("utf-8-sig"), newline="")))

    cortes = []
    for fecha in sorted(args.fechas):
        ymd = fecha.replace("-", "")
        ruta = args.origen / f"boletin_{ymd}.html"
        if not ruta.is_file():
            raise FileNotFoundError(f"Boletín ausente: {ruta}")
        cortes.append(preparar_corte(ruta.read_bytes(), fecha, snap_filas))

    reporte = incorporar_en_s3(s3, args.bucket, cortes, aplicar=args.aplicar)
    print(json.dumps(reporte, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
