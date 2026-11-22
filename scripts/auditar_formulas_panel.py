"""Comprueba coherencia aritmética del panel ajustado, sin certificar su fuente."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def auditar(df, tolerancia=1e-8):
    claves = ["fecha", "emisora", "serie"]
    columnas = claves + ["posicion_sesion", "ppp_ajustado"]
    variables = ([f"ret_{n}_adj" for n in (1, 5, 10, 20)] +
                 [f"distancia_media_{n}_adj" for n in (5, 20)] +
                 [f"volatilidad_{n}_adj" for n in (5, 20)])
    if not set(columnas + variables).issubset(df.columns):
        raise ValueError("Faltan columnas del panel.")
    if df.duplicated(claves).any() or df.duplicated(["emisora", "serie", "posicion_sesion"]).any():
        raise ValueError("El panel contiene claves o posiciones ambiguas.")
    p = df[columnas + variables].copy()
    for col in ["posicion_sesion", "ppp_ajustado", *variables]:
        p[col] = pd.to_numeric(p[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    if (p["posicion_sesion"].isna().any() or
            (p["posicion_sesion"] % 1 != 0).any() or
            p[claves].isna().any().any()):
        raise ValueError("Posición de sesión inválida.")
    p = p.sort_values(["emisora", "serie", "posicion_sesion"])
    p.loc[p["ppp_ajustado"] <= 0, "ppp_ajustado"] = np.nan
    grupo = p.groupby(["emisora", "serie"], sort=False)
    resultados = {}

    def comparar(columna, esperado, longitud):
        anterior = grupo["posicion_sesion"].shift(longitud)
        consecutivas = (p["posicion_sesion"] - anterior) == longitud
        mascara = consecutivas & esperado.notna() & p[columna].notna()
        diferencias = (p.loc[mascara, columna] - esperado.loc[mascara]).abs()
        resultados[columna] = {"comparables": int(mascara.sum()),
                               "difieren": int((diferencias > tolerancia).sum()),
                               "diferencia_maxima": float(diferencias.max()) if len(diferencias) else None}

    for n in (1, 5, 10, 20):
        prev = grupo["ppp_ajustado"].shift(n)
        comparar(f"ret_{n}_adj", p["ppp_ajustado"] / prev - 1, n)
    for n in (5, 20):
        media = grupo["ppp_ajustado"].transform(lambda x: x.rolling(n, min_periods=n).mean())
        comparar(f"distancia_media_{n}_adj", p["ppp_ajustado"] / media - 1, n - 1)
    p["_ret1"] = p["ppp_ajustado"] / grupo["ppp_ajustado"].shift(1) - 1
    grupo = p.groupby(["emisora", "serie"], sort=False)
    for n in (5, 20):
        desviacion = grupo["_ret1"].transform(lambda x: x.rolling(n, min_periods=n).std(ddof=1))
        comparar(f"volatilidad_{n}_adj", desviacion, n)
    return {"filas_panel": len(p), "tolerancia_absoluta": tolerancia, "resultados": resultados,
            "limitacion": "Comprueba aritmética solo en subventanas consecutivas del propio panel; "
                          "no valida evidencia BMV, ajustes, filas excluidas ni derechos de uso."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panel", required=True, type=Path)
    args = p.parse_args()
    raw = args.panel.read_bytes()
    import io
    resultado = auditar(pd.read_csv(io.BytesIO(raw), low_memory=False))
    resultado["sha256_panel"] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
