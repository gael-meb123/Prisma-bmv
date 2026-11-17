"""
Prisma BMV - Carga inicial del lakehouse en S3 a partir de la instantánea local (datos/).

Sube, con el mismo formato que produce la Lambda:
  silver/precios_ppp/YYYY/MM/ppp_15_emisoras_YYYYMMDD.csv   (una partición por sesión)
  silver/serie_unificada_reciente.csv                        (últimas 60 sesiones para la ventana de 21)
  gold/senales_g2/registro_senales_prospectivas_panel_g2.csv
  gold/senales_g1/registro_senales_prospectivas_walmex.csv
  gold/modelos/registro_modelos_g2_oficial.json

Bronze no se puede reconstruir desde aquí: los HTML originales no forman parte de la
instantánea. Bronze empieza con la primera ejecución de la Lambda; las filas históricas de
Silver conservan la firma SHA-256 del boletín del que salieron.

Uso:
  python scripts/bootstrap_lakehouse.py --bucket MI_BUCKET [--region us-east-1]
         [--historica ruta/serie_ppp_historica_15_emisoras_bmv.csv --desde 2025-01-01] [--simular]
"""

from __future__ import annotations

import argparse
import json

import _ruta  # noqa: F401
import pandas as pd

from lambda_function import VENTANA_SERIE_SESIONES, tipar_gold
from prisma.data.repository import RepositorioLocal, normalizar_precios
from prisma.domain import bmv_core as core


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--datos", default=str(_ruta.RAIZ / "datos"))
    ap.add_argument("--historica", help="CSV histórico de 15 emisoras (opcional)")
    ap.add_argument("--desde", default="2026-01-01", help="primera sesión histórica a subir")
    ap.add_argument("--simular", action="store_true", help="solo lista lo que se subiría")
    a = ap.parse_args()

    repo = RepositorioLocal(a.datos)
    precios = repo.precios()
    if a.historica:
        hist = normalizar_precios(pd.read_csv(a.historica))
        hist = hist[hist["fecha"] >= a.desde]
        precios = normalizar_precios(pd.concat([hist, precios], ignore_index=True))
    precios = precios.reindex(columns=list(core.COLUMNAS_SILVER))

    objetos: dict[str, bytes] = {}
    for fecha, g in precios.groupby("fecha"):
        ymd = fecha.replace("-", "")
        objetos[f"silver/precios_ppp/{ymd[:4]}/{ymd[4:6]}/ppp_15_emisoras_{ymd}.csv"] = g.to_csv(index=False).encode()
    fechas = sorted(precios["fecha"].unique())[-VENTANA_SERIE_SESIONES:]
    objetos["silver/serie_unificada_reciente.csv"] = precios[precios["fecha"].isin(fechas)].to_csv(index=False).encode()
    objetos["gold/senales_g2/registro_senales_prospectivas_panel_g2.csv"] = tipar_gold(repo._g2_crudo()).to_csv(index=False).encode()
    objetos["gold/senales_g1/registro_senales_prospectivas_walmex.csv"] = repo._g1_crudo().to_csv(index=False).encode()
    objetos["gold/modelos/registro_modelos_g2_oficial.json"] = json.dumps(repo.modelos_g2(), indent=1).encode()

    print(f"{len(objetos)} objetos ({sum(map(len, objetos.values())) / 1024:,.0f} KB) para s3://{a.bucket}/")
    if a.simular:
        for k in list(objetos)[:5] + ["…"] + list(objetos)[-5:]:
            print("  ", k)
        return

    import boto3

    s3 = boto3.client("s3", region_name=a.region)
    for i, (key, cuerpo) in enumerate(objetos.items(), 1):
        tipo = "application/json" if key.endswith(".json") else "text/csv; charset=utf-8"
        s3.put_object(Bucket=a.bucket, Key=key, Body=cuerpo, ContentType=tipo)
        if i % 50 == 0:
            print(f"  {i}/{len(objetos)}")
    print("Carga inicial completa.")


if __name__ == "__main__":
    main()
