"""Compara Gold con un Silver diario por clave exacta, sin modificar archivos."""
import argparse
import collections
import csv
import hashlib
import io
import json
import math
from datetime import date
from pathlib import Path


def cargar(path):
    data = path.read_bytes()
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))), hashlib.sha256(data).hexdigest()


def precio(valor):
    try:
        n = float(valor)
        return n if math.isfinite(n) and n > 0 else None
    except (TypeError, ValueError):
        return None


def auditar(gold, silver, fecha):
    if date.fromisoformat(fecha).isoformat() != fecha:
        raise ValueError("Fecha debe ser ISO.")
    indice = collections.defaultdict(list)
    for fila in silver:
        if fila["fecha"] != fecha:
            raise ValueError("Silver contiene fechas ajenas al corte.")
        if not fila.get("emisora") or not fila.get("serie"):
            raise ValueError("Silver carece de clave exacta.")
        indice[(fila["emisora"], fila["serie"])].append(fila)
    contadores = collections.Counter()
    for fila in gold:
        if fila["fecha_senal"] != fecha:
            continue
        contadores["filas_gold"] += 1
        matches = indice[(fila.get("emisora"), fila.get("serie"))]
        if len(matches) != 1:
            contadores["clave_ausente" if not matches else "clave_ambigua"] += 1
            continue
        contadores["clave_exacta"] += 1
        actual = matches[0]
        contadores["estado:" + (actual.get("estado_captura") or "SIN_ESTADO")] += 1
        anterior_hash, nuevo_hash = fila.get("sha256_boletin_base"), actual.get("sha256_boletin")
        contadores["hash_igual" if anterior_hash and anterior_hash == nuevo_hash else "hash_distinto_o_ausente"] += 1
        a, b = precio(fila.get("ppp_base_t")), precio(actual.get("ppp_bmv_mxn"))
        if a is None or b is None:
            contadores["precio_faltante_o_invalido"] += 1
        else:
            contadores["precio_igual" if math.isclose(a, b, rel_tol=0, abs_tol=1e-8) else "precio_distinto"] += 1
    return {"fecha": fecha, "contadores": dict(contadores),
            "limitacion": "Coincidencias de fecha base no validan ventanas de cálculo, modelos ni resultados."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gold", type=Path, required=True)
    p.add_argument("--silver-diario", type=Path, required=True)
    p.add_argument("--fecha", required=True)
    args = p.parse_args()
    gold, hash_gold = cargar(args.gold)
    silver, hash_silver = cargar(args.silver_diario)
    resultado = auditar(gold, silver, args.fecha)
    resultado.update(sha256_gold=hash_gold, sha256_silver_diario=hash_silver)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
