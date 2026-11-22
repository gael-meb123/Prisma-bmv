"""Cruza Gold con Silver sin alterar fuentes; no certifica una señal o sus ventanas."""
import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path


def cargar(path):
    data = path.read_bytes()
    filas = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    return filas, hashlib.sha256(data).hexdigest()


def auditar(gold, silver):
    indice = collections.defaultdict(list)
    for fila in silver:
        indice[(fila["fecha"], fila["emisora"])].append(fila)
    cortes = collections.defaultdict(collections.Counter)
    detalles = collections.defaultdict(collections.Counter)
    for senal in gold:
        fecha, emisora = senal["fecha_senal"], senal["emisora"]
        coincidencias = indice[(fecha, emisora)]
        estado = ("SIN_CORRESPONDENCIA" if not coincidencias else
                  "AMBIGUO" if len(coincidencias) != 1 else
                  coincidencias[0].get("estado_captura") or "SIN_ESTADO")
        cortes[fecha][estado] += 1
        if len(coincidencias) == 1:
            base = coincidencias[0]
            misma_serie = bool(base.get("serie") and senal.get("serie") and base["serie"] == senal["serie"])
            mismo_hash = bool(base.get("sha256_boletin") and senal.get("sha256_boletin_base") and
                              base["sha256_boletin"] == senal["sha256_boletin_base"])
            detalles[fecha]["serie_coincidente" if misma_serie else "serie_distinta_o_ausente"] += 1
            detalles[fecha]["hash_coincidente" if mismo_hash else "hash_distinto_o_ausente"] += 1
    return {
        "criterio": "Cruce por fecha y emisora; no verifica identidad de serie ni ventana de cálculo.",
        "filas_gold": len(gold),
        "filas_silver": len(silver),
        "estados_por_fecha": {k: dict(v) for k, v in sorted(cortes.items())},
        "comprobaciones_por_fecha": {k: dict(v) for k, v in sorted(detalles.items())},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--silver", type=Path, required=True)
    args = parser.parse_args()
    gold, hash_gold = cargar(args.gold)
    silver, hash_silver = cargar(args.silver)
    resultado = auditar(gold, silver)
    resultado["sha256_gold"] = hash_gold
    resultado["sha256_silver"] = hash_silver
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
