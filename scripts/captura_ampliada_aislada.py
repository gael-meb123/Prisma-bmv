"""Captura un boletín del corte provisional a un directorio local nuevo."""
from __future__ import annotations

import argparse
import urllib.request
from datetime import date
from pathlib import Path

import _ruta  # noqa: F401
from prisma.data.captura_ampliada import extraer, guardar
from prisma.domain.catalogo_ipc import catalogo_naftrac_20261117


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fecha", required=True, help="Fecha ISO; solo el corte del catálogo está permitido")
    p.add_argument("--salida", required=True, help="Directorio NUEVO para HTML, CSV y manifiesto")
    origen = p.add_mutually_exclusive_group(required=True)
    origen.add_argument("--descargar", action="store_true", help="Descarga la URL pública del boletín BMV")
    origen.add_argument("--html", help="Archivo local: la URL BMV queda registrada como fuente declarada")
    a = p.parse_args()
    fecha = date.fromisoformat(a.fecha)
    catalogo = catalogo_naftrac_20261117()
    catalogo.en_corte(fecha)  # Fallar antes de descargar o crear archivos.
    destino = Path(a.salida)
    if destino.exists():
        raise FileExistsError("El directorio de salida ya existe; no se sobrescribe.")
    url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{fecha:%Y%m%d}.html"
    if a.descargar:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PrismaBMV-Captura-Aislada/1.0"})
        with urllib.request.urlopen(req, timeout=30) as respuesta:
            raw = respuesta.read()
    else:
        raw = Path(a.html).read_bytes()
    resultado = extraer(raw, fecha, catalogo, url)
    resultado["modo_origen"] = "DESCARGA_DIRECTA" if a.descargar else "ARCHIVO_LOCAL_FUENTE_DECLARADA"
    guardar(resultado, raw, destino)
    print(f"Captura aislada: {destino}")
    print(f"Fecha: {fecha}; catálogo: {catalogo.version}; filas: {len(resultado['filas'])}")
    print(f"Estados: {resultado['resumen']}")
    print(f"SHA-256: {resultado['sha256_boletin']}")
    print("Sin inferencia, S3 ni cambios en producción.")


if __name__ == "__main__":
    main()
