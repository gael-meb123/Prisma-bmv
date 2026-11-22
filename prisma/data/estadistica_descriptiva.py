"""Reporte descriptivo reproducible; no modifica datos ni modelos existentes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from prisma.domain.bmv_core import ESTADO_PUBLICADO

ROOT = Path(__file__).resolve().parents[2]
CLAVES = ["fecha", "emisora", "serie"]
VARIABLES_HISTORICAS = ["ppp_bmv_mxn", "variacion_ppp_vs_anterior_pct"]
VARIABLES_PANEL = ["ret_1", "ret_5", "ret_10", "ret_20", "volatilidad_5",
                   "volatilidad_20", "distancia_media_5", "distancia_media_20"]


def _numero(valor):
    return float(valor) if pd.notna(valor) and np.isfinite(valor) else None


def _filtrar(df, desde=None, hasta=None, emisora=None, sector=None):
    fechas = pd.to_datetime(df["fecha"], errors="coerce")
    mascara = fechas.notna()
    if desde:
        mascara &= fechas >= pd.Timestamp(desde)
    if hasta:
        mascara &= fechas <= pd.Timestamp(hasta)
    if emisora:
        mascara &= df["emisora"] == emisora
    if sector:
        mascara &= df["sector_economico"] == sector
    return df.loc[mascara].copy()


def _numerica(serie):
    return pd.to_numeric(serie, errors="coerce").replace([np.inf, -np.inf], np.nan)


def resumen(serie):
    """DE muestral, cuantiles lineales, asimetría y exceso de curtosis de pandas."""
    valores = _numerica(serie)
    v = valores.dropna()
    q1, q3 = (v.quantile(.25), v.quantile(.75)) if len(v) else (np.nan, np.nan)
    return {
        "n_total": len(valores), "n_valido": len(v), "faltantes": int(valores.isna().sum()),
        "faltantes_pct": _numero(valores.isna().mean() * 100) if len(valores) else None,
        "media": _numero(v.mean()), "mediana": _numero(v.median()),
        "minimo": _numero(v.min()), "maximo": _numero(v.max()),
        "desviacion_estandar_muestral": _numero(v.std(ddof=1)),
        "q1": _numero(q1), "q3": _numero(q3), "rango_intercuartilico": _numero(q3 - q1),
        "asimetria": _numero(v.skew()) if len(v) >= 3 and v.nunique() > 1 else None,
        "exceso_curtosis": _numero(v.kurt()) if len(v) >= 4 and v.nunique() > 1 else None,
    }


def _estadisticas(df, variables):
    resultado = []
    for agrupacion in (None, "emisora", "sector_economico"):
        grupos = [(None, df)] if agrupacion is None else df.groupby(agrupacion, dropna=False, sort=True)
        for nombre, grupo in grupos:
            for variable in variables:
                resultado.append({"agrupacion": agrupacion or "total",
                                  "grupo": None if pd.isna(nombre) else str(nombre),
                                  "variable": variable, **resumen(grupo[variable])})
    return resultado


def _cobertura(df, variables):
    fechas = pd.to_datetime(df["fecha"], errors="coerce").dropna()
    return {
        "registros": len(df), "fecha_inicial": fechas.min().strftime("%Y-%m-%d") if len(fechas) else None,
        "fecha_final": fechas.max().strftime("%Y-%m-%d") if len(fechas) else None,
        "emisoras": int(df["emisora"].nunique()), "sectores": int(df["sector_economico"].nunique()),
        "estados": {str(k): int(v) for k, v in df["estado_captura"].fillna("SIN_ESTADO").value_counts().items()},
        "variables": {v: {"validos": int(_numerica(df[v]).notna().sum()),
                           "faltantes": int(_numerica(df[v]).isna().sum()),
                           "faltantes_pct": _numero(_numerica(df[v]).isna().mean() * 100) if len(df) else None}
                      for v in variables},
    }


def _direcciones(df):
    valores = _numerica(df["variacion_ppp_vs_anterior_pct"])
    d = df.loc[valores.notna(), ["emisora", "sector_economico"]].copy()
    v = valores.loc[valores.notna()]
    d["direccion"] = np.where(v > 0, "alza", np.where(v < 0, "baja", "sin_cambio"))
    salida = []
    for dimension in (None, "emisora", "sector_economico"):
        grupos = [(None, d)] if dimension is None else d.groupby(dimension, dropna=False, sort=True)
        for nombre, grupo in grupos:
            for direccion in ("alza", "baja", "sin_cambio"):
                n = int((grupo["direccion"] == direccion).sum())
                salida.append({"agrupacion": dimension or "total", "grupo": None if pd.isna(nombre) else str(nombre),
                               "direccion": direccion, "n": n,
                               "porcentaje": n * 100 / len(grupo) if len(grupo) else None})
    return salida


def _correlaciones(df, variables):
    valores = df[variables].apply(_numerica)
    salida = []
    for a in variables:
        for b in variables:
            par = valores[[a, b]].dropna() if a != b else valores[[a]].dropna()
            n = len(par)
            if a == b:
                pearson = spearman = 1.0 if n >= 2 and par[a].nunique() > 1 else None
            elif n >= 2 and par[a].nunique() > 1 and par[b].nunique() > 1:
                pearson = _numero(par[a].corr(par[b], method="pearson"))
                spearman = _numero(par[a].rank().corr(par[b].rank(), method="pearson"))
            else:
                pearson = spearman = None
            salida.append({"variable_1": a, "variable_2": b, "n_pares": n,
                           "pearson": pearson, "spearman": spearman})
    return salida


def _distribuciones(df, variable):
    valores = _numerica(df[variable]).dropna()
    if valores.empty:
        return {"variable": variable, "n": 0, "histograma": [], "cajas": []}
    counts, edges = np.histogram(valores.to_numpy(), bins="auto")
    cajas = []
    for dimension in ("emisora", "sector_economico"):
        for nombre, grupo in df.groupby(dimension, dropna=False, sort=True):
            cajas.append({"agrupacion": dimension, "grupo": None if pd.isna(nombre) else str(nombre),
                          **resumen(grupo[variable])})
    return {"variable": variable, "n": len(valores),
            "histograma": [{"desde": float(edges[i]), "hasta": float(edges[i + 1]), "n": int(c)}
                           for i, c in enumerate(counts)], "cajas": cajas}


def generar_reporte(historico, panel, desde=None, hasta=None, emisora=None, sector=None, ajustado=True):
    if desde and hasta and pd.Timestamp(desde) > pd.Timestamp(hasta):
        raise ValueError("La fecha inicial debe ser anterior o igual a la final.")
    if historico.duplicated(CLAVES).any() or panel.duplicated(CLAVES).any():
        raise ValueError("Hay claves fecha/emisora/serie duplicadas; no se puede vincular la muestra.")
    variables_panel = [f"{v}_adj" if ajustado else v for v in VARIABLES_PANEL]
    h = _filtrar(historico, desde, hasta, emisora, sector)
    p = _filtrar(panel, desde, hasta, emisora, sector)
    p = p.merge(historico[CLAVES + ["estado_captura"]], on=CLAVES, how="left", validate="one_to_one")
    hv = h.loc[h["estado_captura"] == ESTADO_PUBLICADO].copy()
    pv = p.loc[p["estado_captura"] == ESTADO_PUBLICADO].copy()
    # La correlación combina variables solo en filas del panel con una clave histórica verificada.
    correlacion = pv.merge(historico[CLAVES + VARIABLES_HISTORICAS], on=CLAVES, validate="one_to_one")
    variables = VARIABLES_HISTORICAS + variables_panel
    return {
        "metodologia": {
            "filtros": {"desde": desde, "hasta": hasta, "emisora": emisora, "sector": sector},
            "panel": "ajustado" if ajustado else "no ajustado",
            "fuentes": ["serie_ppp_historica_15_emisoras_bmv.csv",
                        "dataset_panel_15_emisoras_features_ajustado_fase1.csv"],
            "seleccion": "Solo filas con estado PPP_PUBLICADO_VERIFICADO; sin imputación. "
                         "Panel vinculado por fecha, emisora y serie; estados ausentes se excluyen.",
            "advertencia": "La verificación corresponde a la fila actual, no garantiza la cobertura de toda "
                           "la ventana histórica de cada indicador. No se recalculan las variables del panel.",
            "unidades": "PPP en MXN; variacion_ppp_vs_anterior_pct en porcentaje; "
                        "rendimientos y volatilidades del panel en escala decimal.",
            "medidas": "DE muestral (ddof=1), cuantiles lineales, asimetría muestral corregida "
                       "y exceso de curtosis de Fisher corregido (pandas).",
            "correlaciones": "Exploratorias, pares completos; no implican causalidad ni independencia.",
        },
        "cobertura_historico": _cobertura(h, VARIABLES_HISTORICAS),
        "cobertura_panel": _cobertura(p, variables_panel),
        "estadisticas_historico_verificado": _estadisticas(hv, VARIABLES_HISTORICAS),
        "estadisticas_panel_verificado": _estadisticas(pv, variables_panel),
        "frecuencias_direccion": _direcciones(hv),
        "distribucion_variacion_pct": _distribuciones(hv, "variacion_ppp_vs_anterior_pct"),
        "correlaciones_panel": _correlaciones(correlacion, variables),
        "serie_historica_verificada": [
            {"fecha": str(r.fecha), "emisora": str(r.emisora), "serie": str(r.serie),
             "ppp_bmv_mxn": _numero(r.ppp_bmv_mxn),
             "variacion_ppp_vs_anterior_pct": _numero(r.variacion_ppp_vs_anterior_pct)}
            for r in hv.itertuples(index=False)
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Genera un reporte descriptivo JSON sin modificar fuentes.")
    parser.add_argument("--desde", help="Fecha inicial inclusiva AAAA-MM-DD")
    parser.add_argument("--hasta", help="Fecha final inclusiva AAAA-MM-DD")
    parser.add_argument("--emisora")
    parser.add_argument("--sector")
    parser.add_argument("--sin-ajuste", action="store_true")
    parser.add_argument("--salida", type=Path, required=True, help="Archivo JSON nuevo; no sobrescribe.")
    args = parser.parse_args()
    h = pd.read_csv(ROOT / "serie_ppp_historica_15_emisoras_bmv.csv", low_memory=False)
    p = pd.read_csv(ROOT / "dataset_panel_15_emisoras_features_ajustado_fase1.csv", low_memory=False)
    reporte = generar_reporte(h, p, args.desde, args.hasta, args.emisora, args.sector, not args.sin_ajuste)
    with args.salida.open("x", encoding="utf-8") as archivo:
        json.dump(reporte, archivo, ensure_ascii=False, indent=2, allow_nan=False)
        archivo.write("\n")


if __name__ == "__main__":
    main()
