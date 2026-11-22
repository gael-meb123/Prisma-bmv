"""Audita la cobertura real de los 35 pares provisionales del IPC en boletines Bronze S3.

No certifica pertenencia oficial al IPC ni habilita captura/señales; mide únicamente
en qué porcentaje de boletines RSS HTML conservados aparece cada par (emisora, serie).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prisma.data.captura_ampliada import extraer
from prisma.data.evidencias_s3 import BUCKET_PRODUCTIVO, escribir_json_inmutable, timestamp_slug
from prisma.domain.bmv_core import url_boletin
from prisma.domain.catalogo_ipc import CatalogoReferencia, catalogo_naftrac_20261117


class _CatalogoAuditoriaProvisional:
    """Envoltorio explícitamente restringido a auditoría de presencia histórica en HTML."""

    def __init__(self, base: CatalogoReferencia):
        self.base = base
        self.version = f"{base.version}:auditoria-presencia"

    def en_corte(self, fecha: date):
        return self.base.componentes


def listar_bronze_boletines(s3, bucket: str, prefix: str = "bronze/") -> list[tuple[str, str]]:
    claves = []
    token = None
    while True:
        args = {"Bucket": bucket, "Prefix": prefix}
        if token:
            args["ContinuationToken"] = token
        page = s3.list_objects_v2(**args)
        for obj in page.get("Contents", []):
            key = obj["Key"]
            m = re.fullmatch(r"bronze/(\d{4})/(\d{2})/boletin_(\d{8})\.html", key)
            if m:
                ymd = m.group(3)
                fecha = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:])).isoformat()
                claves.append((fecha, key))
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")
    return sorted(claves)


def auditar_cobertura_s3(s3, bucket: str, catalogo: CatalogoReferencia | None = None) -> dict:
    catalogo = catalogo or catalogo_naftrac_20261117()
    wrapper = _CatalogoAuditoriaProvisional(catalogo)
    boletines = listar_bronze_boletines(s3, bucket)
    stats = defaultdict(lambda: {"apariciones_ppp": 0, "ausentes": 0, "conflictos": 0, "fechas_ppp": [], "fechas_ausente": []})
    sesiones_auditadas = []
    errores_boletin = []

    for fecha, key in boletines:
        raw = s3.get_object(Bucket=bucket, Key=key)["Body"].read(2_000_001)
        try:
            res = extraer(raw, date.fromisoformat(fecha), wrapper, url_boletin(fecha.replace("-", "")))
        except Exception as exc:
            errores_boletin.append({"fecha": fecha, "key": key, "error": str(exc)})
            continue
        sesiones_auditadas.append({"fecha": fecha, "key": key, "sha256": res["sha256_boletin"], "tablas": res["tablas_reconocidas"]})
        for fila in res["filas"]:
            par = (fila["emisora_propuesta"], fila["serie_propuesta"])
            st = stats[par]
            if fila["estado_captura"] == "PPP_OBSERVADO_MAPEO_PROVISIONAL":
                st["apariciones_ppp"] += 1
                st["fechas_ppp"].append(fecha)
            elif fila["estado_captura"] == "NO_ENCONTRADO_EN_TABLAS":
                st["ausentes"] += 1
                st["fechas_ausente"].append(fecha)
            else:
                st["conflictos"] += 1

    total = len(sesiones_auditadas)
    detalle = []
    for c in catalogo.componentes:
        par = (c.emisora, c.serie)
        st = stats[par]
        pct = round((st["apariciones_ppp"] / total) * 100.0, 2) if total else 0.0
        detalle.append({
            "emisora": c.emisora,
            "serie": c.serie,
            "origen": c.origen,
            "blackrock": c.blackrock,
            "yahoo_actual": c.yahoo,
            "apariciones_ppp": st["apariciones_ppp"],
            "ausentes": st["ausentes"],
            "conflictos": st["conflictos"],
            "cobertura_rss_pct": pct,
            "ultima_fecha_ppp": st["fechas_ppp"][-1] if st["fechas_ppp"] else None,
        })

    detalle.sort(key=lambda x: (-x["cobertura_rss_pct"], x["origen"], x["emisora"]))
    actual_15 = [d for d in detalle if d["origen"] == "ACTUAL_15"]
    cand_20 = [d for d in detalle if d["origen"] == "CANDIDATO_20"]
    return {
        "version": 1,
        "generado_en_utc": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "catalogo_base": catalogo.version,
        "estado_catalogo": "PROVISIONAL_NO_OFICIAL",
        "total_boletines_auditados": total,
        "rango_sesiones": [sesiones_auditadas[0]["fecha"], sesiones_auditadas[-1]["fecha"]] if sesiones_auditadas else [],
        "errores_boletin": errores_boletin,
        "resumen": {
            "actual_15_con_cobertura_100pct": sum(1 for x in actual_15 if x["cobertura_rss_pct"] == 100.0),
            "actual_15_con_cobertura_0pct": sum(1 for x in actual_15 if x["cobertura_rss_pct"] == 0.0),
            "candidato_20_con_alguna_aparicion": sum(1 for x in cand_20 if x["apariciones_ppp"] > 0),
            "candidato_20_con_cobertura_100pct": sum(1 for x in cand_20 if x["cobertura_rss_pct"] == 100.0),
            "candidato_20_con_cobertura_0pct": sum(1 for x in cand_20 if x["cobertura_rss_pct"] == 0.0),
            "total_conflictos": sum(x["conflictos"] for x in detalle),
        },
        "componentes": detalle,
        "limitacion": (
            "Presencia en tablas parciales del boletín RSS no demuestra pertenencia oficial al IPC "
            "ni garantiza fuente completa para los 35 componentes."
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--guardar-s3", action="store_true", help="Guarda el reporte inmutable bajo evidencias/auditorias/")
    args = p.parse_args()

    import boto3
    s3 = boto3.client("s3", region_name=args.region)
    reporte = auditar_cobertura_s3(s3, args.bucket)
    if args.guardar_s3:
        clave = f"evidencias/auditorias/cobertura_ipc35_{timestamp_slug()}.json"
        reporte["reporte_s3"] = escribir_json_inmutable(s3, args.bucket, clave, reporte)
    print(json.dumps(reporte, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
