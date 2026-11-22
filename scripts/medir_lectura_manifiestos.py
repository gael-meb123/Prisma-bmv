"""Presupuesto de peticiones S3; tarifas explícitas, no una factura AWS."""
import argparse
import json


def estimar(fechas, consultas, list_por_1000, get_por_1000):
    if not 0 <= fechas <= 31 or consultas < 0 or min(list_por_1000, get_por_1000) < 0:
        raise ValueError("Parámetros fuera de rango")
    lists, gets = consultas, 2 * fechas * consultas
    return {"list": lists, "get": gets, "usd_solicitudes": (lists * list_por_1000 + gets * get_por_1000) / 1000,
            "excluye": ["Lambda", "Gateway", "almacenamiento", "transferencia", "reintentos"],
            "bytes_max_por_consulta": fechas * (16_384 + 1_000_000)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fechas", type=int, default=20)
    p.add_argument("--consultas", type=int, default=1000)
    p.add_argument("--list-usd-1000", type=float, required=True)
    p.add_argument("--get-usd-1000", type=float, required=True)
    args = p.parse_args()
    print(json.dumps(estimar(args.fechas, args.consultas, args.list_usd_1000, args.get_usd_1000)))


if __name__ == "__main__":
    main()
