"""Lambda de laboratorio: captura provisional, sin señales ni escrituras productivas."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import urllib.request
from datetime import date

from prisma.data.captura_ampliada import extraer
from prisma.domain.catalogo_ipc import catalogo_naftrac_20261117

PREFIJO = "experimental/v1"


def _descargar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PrismaBMV-Captura-Aislada/1.0"})
    with urllib.request.urlopen(req, timeout=30) as respuesta:
        return respuesta.read()


def _guardar_inmutable(s3, bucket, key, contenido, tipo):
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=contenido, ContentType=tipo, IfNoneMatch="*")
    except Exception as exc:
        codigo = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if codigo not in ("PreconditionFailed", "412"):
            raise
        existente = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        if existente != contenido:
            raise ValueError(f"Contenido diferente en objeto inmutable: {key}") from exc


def _cuarentena(s3, bucket, fecha, sha, raw, resultado, existentes):
    """Conserva bytes divergentes y compara filas; nunca promueve a Silver."""
    base = f"{PREFIJO}/cuarentena/{fecha.isoformat()}/{sha}"
    _guardar_inmutable(s3, bucket, base + ".html", raw, "text/html; charset=utf-8")
    informe = {"sha256_nuevo": sha, "silver_existente": existentes,
               "comparacion": "NO_DISPONIBLE", "diferencias": []}
    if len(existentes) == 1:
        anterior = s3.get_object(Bucket=bucket, Key=existentes[0])["Body"].read()
        filas = list(csv.DictReader(io.StringIO(anterior.decode("utf-8"))))
        nuevas = resultado["filas"]
        claves = ("emisora_propuesta", "serie_propuesta")
        def indice(registros):
            return {tuple(str(f[k]) for k in claves): {
                k: "" if v is None else str(v) for k, v in f.items()
                if k != "sha256_boletin"
            } for f in registros}
        vieja, nueva = indice(filas), indice(nuevas)
        informe["diferencias"] = [
            {"par": list(par), "campos": sorted(
                k for k in set(vieja.get(par, {})) | set(nueva.get(par, {}))
                if vieja.get(par, {}).get(k) != nueva.get(par, {}).get(k))}
            for par in sorted(set(vieja) | set(nueva)) if vieja.get(par) != nueva.get(par)
        ]
        informe["comparacion"] = "FILAS_DISTINTAS" if informe["diferencias"] else "FILAS_IGUALES"
    _guardar_inmutable(s3, bucket, base + ".json",
                       json.dumps(informe, ensure_ascii=False, sort_keys=True).encode("utf-8"),
                       "application/json")


def ejecutar(event, s3, descargar, bucket):
    if not re.fullmatch(r"prisma-bmv-captura-aislada-[a-z0-9-]+", bucket):
        raise ValueError("Bucket no corresponde al laboratorio de captura.")
    if not isinstance(event, dict) or set(event) != {"fecha"}:
        raise ValueError("Evento debe contener únicamente fecha ISO.")
    fecha = date.fromisoformat(event["fecha"])
    catalogo = catalogo_naftrac_20261117()
    catalogo.en_corte(fecha)  # Rechaza otras sesiones antes de solicitar el boletín.
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{fecha:%Y%m%d}.html"
    raw = descargar(url)
    resultado = extraer(raw, fecha, catalogo, url)
    sha = resultado["sha256_boletin"]
    base = f"{fecha.isoformat()}/{sha}"
    key_bronze = f"{PREFIJO}/bronze/{base}.html"
    key_silver = f"{PREFIJO}/silver/{base}.csv"
    key_manifiesto = f"{PREFIJO}/manifiestos/{base}.json"
    # Compatibilidad con ejecuciones previas sin bloqueo. Una nueva firma no
    # puede introducir otro Silver de la misma fecha silenciosamente.
    existentes = s3.list_objects_v2(Bucket=bucket, Prefix=f"{PREFIJO}/silver/{fecha.isoformat()}/",
                                    MaxKeys=2)
    if existentes.get("IsTruncated") or any(x["Key"] != key_silver for x in existentes.get("Contents", [])):
        _cuarentena(s3, bucket, fecha, sha, raw, resultado,
                    [x["Key"] for x in existentes.get("Contents", [])])
        raise ValueError("HASH_DIVERGENTE_REQUIERE_REVISION: Silver ya existe con otra firma.")
    key_bloqueo = f"{PREFIJO}/bloqueos/{fecha.isoformat()}.json"
    bloqueo = json.dumps({"sha256": sha, "version_catalogo": catalogo.version},
                          sort_keys=True).encode("utf-8")
    try:
        _guardar_inmutable(s3, bucket, key_bloqueo, bloqueo, "application/json")
    except ValueError as exc:
        _cuarentena(s3, bucket, fecha, sha, raw, resultado, [])
        raise ValueError("HASH_DIVERGENTE_REQUIERE_REVISION: bloqueo previo incompatible.") from exc
    buffer = io.StringIO(newline="")
    escritor = csv.DictWriter(buffer, fieldnames=list(resultado["filas"][0]), lineterminator="\n")
    escritor.writeheader()
    escritor.writerows(resultado["filas"])
    manifiesto = {k: v for k, v in resultado.items() if k != "filas"}
    manifiesto.update({"bronze": key_bronze, "silver": key_silver, "procesador": PREFIJO})
    _guardar_inmutable(s3, bucket, key_bronze, raw, "text/html; charset=utf-8")
    _guardar_inmutable(s3, bucket, key_silver, buffer.getvalue().encode("utf-8"), "text/csv; charset=utf-8")
    # Solo un manifiesto completo certifica que las dos escrituras previas terminaron.
    _guardar_inmutable(s3, bucket, key_manifiesto,
                       json.dumps(manifiesto, ensure_ascii=False, sort_keys=True).encode("utf-8"),
                       "application/json; charset=utf-8")
    return {**manifiesto, "manifiesto": key_manifiesto}


def lambda_handler(event, context):
    import boto3
    return ejecutar(event, boto3.client("s3"), _descargar, os.environ["BUCKET_NAME"])
