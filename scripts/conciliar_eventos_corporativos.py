"""Genera colas prioritarias en S3 y concilia avisos oficiales de eventos corporativos.

No sustituye automáticamente factores ni desbloquea el panel ajustado o señales.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prisma.data.evidencias_s3 import (
    BUCKET_PRODUCTIVO,
    escribir_inmutable,
    escribir_json_inmutable,
    leer_json,
    sha256_bytes,
    timestamp_slug,
    validar_sha256,
)

EMISORAS_G2 = ("AMX", "FEMSA", "GFNORTE", "GMEXICO", "WALMEX")
PREFIJO_EVENTOS = "evidencias/eventos_corporativos/v1/"


def _cargar_ppp_previo(historico_csv: Path) -> dict[str, tuple[list[str], list[float]]]:
    por_emisora: dict[str, list[tuple[str, float]]] = {}
    with historico_csv.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            em = row.get("emisora", "").strip().upper()
            if em not in EMISORAS_G2 or row.get("estado_captura") != "PPP_PUBLICADO_VERIFICADO":
                continue
            try:
                ppp = float(row["ppp_bmv_mxn"])
            except (TypeError, ValueError):
                continue
            if math.isfinite(ppp) and ppp > 0:
                por_emisora.setdefault(em, []).append((row["fecha"], ppp))
    indice = {}
    for em, pares in por_emisora.items():
        pares.sort(key=lambda x: x[0])
        indice[em] = ([p[0] for p in pares], [p[1] for p in pares])
    return indice


def _ppp_anterior(indice: dict, emisora: str, fecha_ex: str) -> tuple[str | None, float | None]:
    fechas, precios = indice.get(emisora, ([], []))
    pos = bisect_left(fechas, fecha_ex) - 1
    if pos < 0:
        return None, None
    return fechas[pos], precios[pos]


def construir_colas_g2(eventos_csv: Path, historico_csv: Path, corte_ola1: str = "2024-01-01") -> dict:
    indice = _cargar_ppp_previo(historico_csv)
    raw_ev = eventos_csv.read_bytes()
    sha_ev = sha256_bytes(raw_ev)
    filas = list(csv.DictReader(io.StringIO(raw_ev.decode("utf-8-sig"), newline="")))

    ola1, ola2 = [], []
    for row in filas:
        em = row["emisora"].strip().upper()
        if em not in EMISORAS_G2:
            continue
        fecha_ex = row["fecha_ex"].strip()
        tipo = row["tipo"].strip().upper()
        monto = float(row["monto_mxn"])
        factor_yahoo = float(row["factor"])
        fecha_prev, ppp_prev = _ppp_anterior(indice, em, fecha_ex)
        evento_id = f"{em}_{fecha_ex}_{tipo}"
        factor_ref_bmv = (
            round((ppp_prev - monto) / ppp_prev, 8)
            if tipo == "DIVIDENDO" and ppp_prev and monto < ppp_prev
            else None
        )
        item = {
            "evento_id": evento_id,
            "emisora": em,
            "fecha_ex_yahoo": fecha_ex,
            "tipo": tipo,
            "monto_mxn_yahoo": monto,
            "factor_yahoo": factor_yahoo,
            "fuente_actual": row["fuente"].strip(),
            "fecha_ppp_bmv_previo": fecha_prev,
            "ppp_bmv_previo": ppp_prev,
            "factor_referencia_bmv_sobre_monto_yahoo": factor_ref_bmv,
            "estado_verificacion": "PENDIENTE",
            "evidencia_s3_key": None,
            "sha256_evidencia": None,
            "fecha_ex_oficial": None,
            "monto_oficial_mxn": None,
            "ratio_split_oficial": None,
            "fuente_oficial_descripcion": None,
        }
        (ola1 if fecha_ex >= corte_ola1 else ola2).append(item)

    ola1.sort(key=lambda x: (x["emisora"], x["fecha_ex_yahoo"]))
    ola2.sort(key=lambda x: (x["emisora"], x["fecha_ex_yahoo"]))
    ahora = datetime.now(timezone.utc).isoformat()
    meta_comun = {
        "version": 1,
        "generado_en_utc": ahora,
        "sha256_eventos_corporativos_csv": sha_ev,
        "emisoras_g2": list(EMISORAS_G2),
        "panel_ajustado_habilitado": False,
    }
    return {
        "ola1": {**meta_comun, "ola": "OLA_1_PRIORITARIA_2024_2026", "corte_desde": corte_ola1, "total": len(ola1), "eventos": ola1},
        "ola2": {**meta_comun, "ola": "OLA_2_HISTORICA_PRE_2024", "corte_hasta_exclusivo": corte_ola1, "total": len(ola2), "eventos": ola2},
    }


def serializar_csv_cola(eventos: list[dict]) -> bytes:
    if not eventos:
        raise ValueError("Cola de eventos vacía.")
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(eventos[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(eventos)
    return buf.getvalue().encode("utf-8")


def conciliar_eventos(s3, bucket: str, manifiesto_cola: dict, tolerancia_factor: float = 1e-4) -> dict:
    """Contrasta avisos oficiales cargados en S3 contra los factores Yahoo y recalcula sobre PPP BMV."""
    eventos = manifiesto_cola.get("eventos") or []
    evaluados = []
    verificados = 0
    divergentes = 0
    pendientes = 0
    invalidos = 0

    for ev in eventos:
        estado = ev.get("estado_verificacion", "PENDIENTE")
        if estado == "PENDIENTE":
            pendientes += 1
            evaluados.append({"evento_id": ev["evento_id"], "resultado": "PENDIENTE"})
            continue
        key = ev.get("evidencia_s3_key")
        sha = ev.get("sha256_evidencia")
        if not isinstance(key, str) or not key.startswith(PREFIJO_EVENTOS + "documentos/") or not validar_sha256(sha):
            invalidos += 1
            evaluados.append({"evento_id": ev["evento_id"], "resultado": "EVIDENCIA_INVALIDA"})
            continue
        try:
            raw_doc = s3.get_object(Bucket=bucket, Key=key)["Body"].read(5_000_001)
        except Exception:
            invalidos += 1
            evaluados.append({"evento_id": ev["evento_id"], "resultado": "DOCUMENTO_AUSENTE_S3"})
            continue
        if sha256_bytes(raw_doc) != sha:
            invalidos += 1
            evaluados.append({"evento_id": ev["evento_id"], "resultado": "SHA256_NO_COINCIDE"})
            continue

        ppp_prev = ev.get("ppp_bmv_previo")
        tipo = ev.get("tipo")
        if tipo == "DIVIDENDO":
            monto_of = ev.get("monto_oficial_mxn")
            if not isinstance(monto_of, (int, float)) or not isinstance(ppp_prev, (int, float)) or ppp_prev <= 0 or monto_of <= 0 or monto_of >= ppp_prev:
                invalidos += 1
                evaluados.append({"evento_id": ev["evento_id"], "resultado": "DATOS_DIVIDENDO_INVALIDOS"})
                continue
            factor_oficial = round((ppp_prev - float(monto_of)) / float(ppp_prev), 8)
        elif tipo == "SPLIT":
            ratio = ev.get("ratio_split_oficial")
            if not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or ratio <= 0:
                invalidos += 1
                evaluados.append({"evento_id": ev["evento_id"], "resultado": "RATIO_SPLIT_INVALIDO"})
                continue
            factor_oficial = round(float(ratio), 8)
        else:
            invalidos += 1
            evaluados.append({"evento_id": ev["evento_id"], "resultado": "TIPO_NO_SOPORTADO"})
            continue

        delta = round(abs(factor_oficial - float(ev["factor_yahoo"])), 8)
        fecha_igual = ev.get("fecha_ex_oficial") == ev.get("fecha_ex_yahoo")
        if delta > tolerancia_factor or not fecha_igual:
            divergentes += 1
            resultado = "DIVERGENTE_REQUIERE_REVISION"
        else:
            verificados += 1
            resultado = "VERIFICADO_OFICIAL"
        evaluados.append({
            "evento_id": ev["evento_id"],
            "resultado": resultado,
            "factor_yahoo": ev["factor_yahoo"],
            "factor_recalculado_bmv": factor_oficial,
            "delta_factor": delta,
            "fecha_ex_coincide": fecha_igual,
            "evidencia_s3_key": key,
            "sha256_evidencia": sha,
        })

    aprobada = bool(eventos) and verificados == len(eventos) and pendientes == 0 and divergentes == 0 and invalidos == 0
    return {
        "version": 1,
        "generado_en_utc": datetime.now(timezone.utc).isoformat(),
        "ola": manifiesto_cola.get("ola"),
        "total_eventos": len(eventos),
        "verificados_oficiales": verificados,
        "pendientes": pendientes,
        "divergentes": divergentes,
        "invalidos": invalidos,
        "muestra_aprobada": aprobada,
        "panel_ajustado_habilitado": False,
        "detalle": evaluados,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="comando", required=True)

    g = sub.add_parser("generar-colas", help="Publica colas prioritarias G2 en S3 evidencias/")
    g.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    g.add_argument("--region", default="us-east-1")
    g.add_argument("--corte-ola1", default="2024-01-01")

    c = sub.add_parser("conciliar", help="Audita una cola con avisos oficiales ya cargados en S3")
    c.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    c.add_argument("--region", default="us-east-1")
    c.add_argument("--cola-key", default=PREFIJO_EVENTOS + "muestra_prioritaria_g2_2024_2026.json")
    c.add_argument("--guardar-s3", action="store_true")

    args = p.parse_args()
    import boto3
    s3 = boto3.client("s3", region_name=args.region)

    if args.comando == "generar-colas":
        colas = construir_colas_g2(
            ROOT / "eventos_corporativos_15_emisoras.csv",
            ROOT / "serie_ppp_historica_15_emisoras_bmv.csv",
            corte_ola1=args.corte_ola1,
        )
        res = {
            "ola1_json": escribir_json_inmutable(s3, args.bucket, PREFIJO_EVENTOS + "muestra_prioritaria_g2_2024_2026.json", colas["ola1"]),
            "ola1_csv": escribir_inmutable(s3, args.bucket, PREFIJO_EVENTOS + "muestra_prioritaria_g2_2024_2026.csv", serializar_csv_cola(colas["ola1"]["eventos"]), "text/csv; charset=utf-8"),
            "ola2_json": escribir_json_inmutable(s3, args.bucket, PREFIJO_EVENTOS + "cola_historica_g2_2016_2023.json", colas["ola2"]),
            "totales": {"ola1": colas["ola1"]["total"], "ola2": colas["ola2"]["total"]},
        }
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        cola = leer_json(s3, args.bucket, args.cola_key)
        reporte = conciliar_eventos(s3, args.bucket, cola)
        if args.guardar_s3:
            clave = f"evidencias/auditorias/conciliacion_eventos_{timestamp_slug()}.json"
            reporte["reporte_s3"] = escribir_json_inmutable(s3, args.bucket, clave, reporte)
        print(json.dumps(reporte, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
