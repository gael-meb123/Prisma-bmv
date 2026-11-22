"""Audita 21 sesiones de Silver diario local sin generar ni modificar señales."""
import argparse
import csv
import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from prisma.domain.bmv_core import FERIADOS_BMV, es_sesion_bmv
from prisma.domain.elegibilidad_senales import evaluar_ventanas


def sesiones_hasta(corte):
    actual = date.fromisoformat(corte)
    if actual.isoformat() != corte or actual.year not in FERIADOS_BMV or not es_sesion_bmv(actual):
        raise ValueError("El corte debe ser una sesión de un año con calendario local verificado.")
    sesiones = []
    while len(sesiones) < 21:
        if actual.year not in FERIADOS_BMV:
            raise ValueError("La ventana cruza un año sin calendario local verificado.")
        if es_sesion_bmv(actual):
            sesiones.append(actual.isoformat())
        actual -= timedelta(days=1)
    return list(reversed(sesiones))


def auditar(directorio, corte, emisoras):
    sesiones = sesiones_hasta(corte)
    filas = []
    archivos = []
    requeridas = {"fecha", "emisora", "serie", "estado_captura", "ppp_bmv_mxn", "sha256_boletin", "url_fuente"}
    for fecha in sesiones:
        d = date.fromisoformat(fecha)
        ruta = directorio / f"{d:%Y}" / f"{d:%m}" / f"ppp_15_emisoras_{d:%Y%m%d}.csv"
        if not ruta.exists():
            archivos.append({"fecha": fecha, "estado": "ARCHIVO_AUSENTE"})
            continue
        raw = ruta.read_bytes()
        if len(raw) > 1_000_000:
            raise ValueError("Archivo diario demasiado grande.")
        import io
        lector = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
        if not requeridas.issubset(lector.fieldnames or []):
            raise ValueError(f"Contrato diario inválido: {fecha}.")
        diario = list(lector)
        if not diario or any(x["fecha"] != fecha for x in diario):
            raise ValueError(f"El archivo contiene otra fecha o está vacío: {fecha}.")
        filas.extend(diario)
        archivos.append({"fecha": fecha, "estado": "LEIDO", "sha256_archivo": hashlib.sha256(raw).hexdigest()})
    return {"corte": corte, "sesiones": sesiones, "archivos": archivos,
            "emisoras": evaluar_ventanas(filas, sesiones, emisoras),
            "limitacion": "Las etiquetas, hashes y URL declarados no acreditan autenticidad ni modelos; no se emitieron señales."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directorio", type=Path, required=True, help="Raíz local con YYYY/MM/*.csv")
    p.add_argument("--fecha", required=True, help="Sesión final AAAA-MM-DD")
    p.add_argument("--emisoras", nargs="+", required=True)
    args = p.parse_args()
    print(json.dumps(auditar(args.directorio, args.fecha, args.emisoras), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
