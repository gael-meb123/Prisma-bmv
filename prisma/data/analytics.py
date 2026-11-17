"""
Prisma BMV - Cálculos que alimentan los dashboards.

Ninguna cifra que se muestra en la terminal está escrita a mano: todo sale de aquí y de
los datos del lakehouse, incluido el marcador de aciertos y la narrativa de Prismi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from prisma.domain import bmv_core as core

# ---------------------------------------------------------------------------
# Monitor de mercado
# ---------------------------------------------------------------------------


def fechas_disponibles(precios: pd.DataFrame, retraso_sesiones: int = 0) -> list[str]:
    """Sesiones visibles para el plan, de la más reciente a la más antigua."""
    fechas = sorted(precios["fecha"].unique(), reverse=True) if not precios.empty else []
    return list(fechas[retraso_sesiones:])


def kpis_sesion(sesion: pd.DataFrame) -> dict[str, Any]:
    verif = sesion[sesion["estado_captura"] == core.ESTADO_PUBLICADO].dropna(subset=["variacion_ppp_vs_anterior_pct"])
    if verif.empty:
        return {"total": len(sesion), "verificadas": 0, "huecos": len(sesion), "alzas": 0, "bajas": 0,
                "sin_cambio": 0, "mayor_alza": None, "mayor_baja": None, "variacion_media": None}
    orden = verif.sort_values("variacion_ppp_vs_anterior_pct")
    return {
        "total": len(sesion),
        "verificadas": len(verif),
        "huecos": int((sesion["estado_captura"] == core.ESTADO_HUECO).sum()),
        "alzas": int((verif["variacion_ppp_vs_anterior_pct"] > 0).sum()),
        "bajas": int((verif["variacion_ppp_vs_anterior_pct"] < 0).sum()),
        "sin_cambio": int((verif["variacion_ppp_vs_anterior_pct"] == 0).sum()),
        "mayor_alza": orden.iloc[-1][["emisora", "variacion_ppp_vs_anterior_pct"]].to_dict(),
        "mayor_baja": orden.iloc[0][["emisora", "variacion_ppp_vs_anterior_pct"]].to_dict(),
        "variacion_media": float(verif["variacion_ppp_vs_anterior_pct"].mean()),
    }


def kpis_por_sector(sesion: pd.DataFrame) -> pd.DataFrame:
    def _agg(g: pd.DataFrame) -> pd.Series:
        v = g[g["estado_captura"] == core.ESTADO_PUBLICADO]["variacion_ppp_vs_anterior_pct"].dropna()
        return pd.Series({
            "emisoras": len(g),
            "con_ppp": len(v),
            "huecos": int((g["estado_captura"] == core.ESTADO_HUECO).sum()),
            "variacion_media_pct": float(v.mean()) if len(v) else np.nan,
        })

    return sesion.groupby("sector_economico").apply(_agg, include_groups=False).reset_index().sort_values(
        "variacion_media_pct", ascending=False, na_position="last")


def firmas_sesion(sesion: pd.DataFrame) -> dict[str, Any]:
    """SHA-256 registrados para la sesión. Más de uno indica dos descargas distintas."""
    hashes = sorted(sesion["sha256_boletin"].dropna().astype(str).unique()) if "sha256_boletin" in sesion else []
    urls = sorted(sesion["url_fuente"].dropna().astype(str).unique()) if "url_fuente" in sesion else []
    return {"hashes": hashes, "url": urls[0] if urls else None,
            "estado": "FIRMA_UNICA" if len(hashes) == 1 else ("SIN_FIRMA" if not hashes else "FIRMAS_MULTIPLES")}


# ---------------------------------------------------------------------------
# Consenso (semáforo)
# ---------------------------------------------------------------------------
SUBIDA, NO_SUBIDA, DIVERGENCIA = "CONSENSO_ALTO_SUBIDA", "CONSENSO_ALTO_NO_SUBIDA", "DIVERGENCIA_ALERTA"


def consenso_desde_clases(clases: list[int]) -> str:
    if clases and all(c == 1 for c in clases):
        return SUBIDA
    if clases and all(c == 0 for c in clases):
        return NO_SUBIDA
    return DIVERGENCIA


def canonizar_consenso(etiqueta: str) -> str:
    """Traduce las etiquetas G1/G2 históricas al vocabulario del semáforo."""
    e = str(etiqueta).upper()
    if e.startswith("DIVERGENCIA") or e.startswith("MAYORIA"):
        return DIVERGENCIA
    if "NO_SUBIDA" in e:
        return NO_SUBIDA
    if "SUBIDA" in e:
        return SUBIDA
    return DIVERGENCIA


NOMBRES_MODELO = {
    "G2_V1_POOLED_REL3_CALIBRADO": "G2-V1 Calibrado",
    "G2_V2_POOLED_REL3_ZONA_NEUTRAL": "G2-V2 Zona neutral",
    "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO": "G2-V3 Alta discriminación",
    "G2_V4_POOLED_DM5_REL_CORTO_PLAZO": "G2-V4 Agotamiento corto (DM5)",
    "G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL": "G2-V5 Adaptativo por régimen",
    "V1_CONTROL_LOGREG": "G1-V1 Logística base",
    "V2R_RETADOR_LINEAL_AJUSTE_DIVIDENDOS": "G1-V2R Ajuste dividendos",
    "V3_RETADOR_SELECCIONADO_RF": "G1-V3 Random Forest",
    "V2_RETADOR_HIBRIDO_BOLETIN": "G1-V2 Híbrido boletín",
}
MODELO_BASE_G1 = "V1_CONTROL_LOGREG"


def modelo_g1(id_senal: str) -> str:
    m = re.match(r"^[A-Z&]+_\d{8}_(.+)$", str(id_senal))
    return m.group(1) if m else str(id_senal)


def tabla_probabilidades(g1: pd.DataFrame, g2: pd.DataFrame, emisora: str, fecha: str,
                         incluir_g2: bool, solo_base_g1: bool) -> pd.DataFrame:
    filas = []
    if not g1.empty:
        sub = g1[(g1["emisora"] == emisora) & (g1["fecha_senal"] == fecha)]
        for _, r in sub.iterrows():
            mod = modelo_g1(r["id_senal"])
            if solo_base_g1 and mod != MODELO_BASE_G1:
                continue
            filas.append({"generacion": "G1", "modelo": mod, "nombre": NOMBRES_MODELO.get(mod, mod),
                          "probabilidad": float(r["prob_subida_pct"]) / 100.0,
                          "clase": int(r["prediccion_clase"]), "valida": bool(r["valida"])})
    if incluir_g2 and not g2.empty:
        sub = g2[(g2["emisora"] == emisora) & (g2["fecha_senal"] == fecha)]
        for _, r in sub.iterrows():
            filas.append({"generacion": "G2", "modelo": r["modelo_g2"],
                          "nombre": NOMBRES_MODELO.get(r["modelo_g2"], r["modelo_g2"]),
                          "probabilidad": float(r["probabilidad_subida"]),
                          "clase": int(r["prediccion_clase"]), "valida": True})
    return pd.DataFrame(filas)


def consenso_por_generacion(tabla: pd.DataFrame) -> dict[str, str]:
    out = {}
    for gen, g in tabla[tabla["valida"]].groupby("generacion") if not tabla.empty else []:
        out[gen] = consenso_desde_clases(g["clase"].tolist())
    return out


def inconsistencias_consenso(g2: pd.DataFrame) -> pd.DataFrame:
    """Compara la etiqueta registrada con la que se deriva de las clases (control de calidad)."""
    filas = []
    for (f, e), g in g2.groupby(["fecha_senal", "emisora"]):
        derivado = consenso_desde_clases(g["prediccion_clase"].astype(int).tolist())
        registrado = canonizar_consenso(g["estado_consenso_g2"].iloc[0])
        if derivado != registrado:
            filas.append({"fecha_senal": f, "emisora": e, "registrado": registrado, "derivado": derivado})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# Factor clave: ret_10_rel_panel
# ---------------------------------------------------------------------------
@dataclass
class ExplicacionFactor:
    ret_rel_pct: float
    z_rel: float | None
    contribuciones: dict[str, float]
    lectura: str


def explicar_factor(modelos: dict[str, Any], fila_g2: pd.Series) -> ExplicacionFactor:
    em, mod = str(fila_g2["emisora"]), str(fila_g2["modelo_g2"])
    ret_pct = float(fila_g2["ret_10_rel_panel"]) * 100.0
    if mod not in modelos or em not in modelos[mod].get("scalers_por_emisora", {}):
        return ExplicacionFactor(ret_pct, None, {}, "Sin parámetros registrados para descomponer la señal.")
    p = modelos[mod]
    variables = p.get("variables", list(core.VARIABLES_G2))
    faltantes = [v for v in variables if v not in fila_g2.index or pd.isna(fila_g2[v])]
    if "ret_10_rel_panel" not in variables or faltantes:
        # V4/V5 usan variables que el registro de señales no publica (p. ej. distancia_media_5).
        return ExplicacionFactor(ret_pct, None, {}, (
            f"{NOMBRES_MODELO.get(mod, mod)} usa variables propias ({', '.join(variables)}) que el registro de "
            "señales no publica fila por fila, así que su probabilidad no se puede descomponer aquí. "
            "La descomposición está disponible para G2-V1, V2 y V3."))
    x = {v: float(fila_g2[v]) for v in variables}
    sc = p["scalers_por_emisora"][em]
    idx = variables.index("ret_10_rel_panel")
    z = (x["ret_10_rel_panel"] - sc["mean"][idx]) / sc["scale"][idx]
    contrib = core.contribuciones_log_odds(p, em, x)
    signo_beta = "negativo" if p["beta"][idx + 1] < 0 else "positivo"

    if z <= -1.5:
        lectura = (f"{em} va {abs(ret_pct):.2f} pp por debajo del promedio del panel en 10 sesiones "
                   f"({z:+.2f} desviaciones respecto a su propia historia). Con coeficiente {signo_beta}, "
                   "el rezago relativo empuja la probabilidad hacia la subida: es la lectura de reversión a la media.")
    elif z >= 1.5:
        lectura = (f"{em} va {ret_pct:.2f} pp por encima del panel ({z:+.2f} desviaciones). Con coeficiente "
                   f"{signo_beta}, la sobreextensión relativa resta probabilidad de subida.")
    else:
        lectura = (f"El retorno relativo de {em} ({ret_pct:+.2f} pp, {z:+.2f} desviaciones) está dentro de su "
                   "rango habitual; el factor aporta poco a la señal y pesan más las otras variables.")
    return ExplicacionFactor(ret_pct, z, contrib, lectura)


# ---------------------------------------------------------------------------
# Auditoría temporal t+1 ... t+5
# ---------------------------------------------------------------------------


def g1_a_formato_seguimiento(g1: pd.DataFrame) -> pd.DataFrame:
    if g1.empty:
        return g1
    v = g1[g1["valida"]].copy()
    return pd.DataFrame({
        "id_senal_g2": v["id_senal"],
        "fecha_senal": v["fecha_senal"],
        "fecha_objetivo_h5": v["fecha_objetivo_h5"],
        "emisora": v["emisora"],
        "modelo_g2": v["id_senal"].map(modelo_g1),
        "ppp_base_t": v["ppp_base_mxn"],
        "probabilidad_subida": v["prob_subida_pct"] / 100.0,
        "prediccion_clase": v["prediccion_clase"].astype(int),
        "estado_resolucion": "PENDIENTE_T+5",
        "generacion": "G1",
    })


def seguimiento(g1: pd.DataFrame, g2: pd.DataFrame, precios: pd.DataFrame, fecha_corte: str) -> pd.DataFrame:
    """Recalcula el mark-to-market de G1 y G2 con la serie verificada hasta `fecha_corte`."""
    partes = []
    if not g2.empty:
        partes.append(g2.assign(generacion="G2"))
    if not g1.empty:
        partes.append(g1_a_formato_seguimiento(g1))
    if not partes:
        return pd.DataFrame()
    base = pd.concat(partes, ignore_index=True)
    out = core.actualizar_seguimiento(base, precios, fecha_corte)
    out["acierto_parcial_en_curso"] = out["acierto_parcial_en_curso"].map(core._a_bool)
    return out


def marcador_modelos(seg: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for (gen, mod), g in seg.groupby(["generacion", "modelo_g2"]):
        parcial = g["acierto_parcial_en_curso"].dropna()
        resueltas = g[g["estado_resolucion"] == "RESUELTA_T+5"]
        filas.append({
            "generacion": gen,
            "modelo": NOMBRES_MODELO.get(mod, mod),
            "senales": len(g),
            "en_seguimiento": len(parcial),
            "aciertos_parciales": int(parcial.sum()),
            "tasa_parcial_pct": float(parcial.mean() * 100) if len(parcial) else np.nan,
            "resueltas_t5": len(resueltas),
            "aciertos_t5": int(pd.to_numeric(resueltas.get("acierto_direccional_t5"), errors="coerce").sum()) if len(resueltas) else 0,
            "brier_t5": float(pd.to_numeric(resueltas.get("brier_observado_t5"), errors="coerce").mean()) if len(resueltas) else np.nan,
        })
    return pd.DataFrame(filas)


def trayectoria(precios: pd.DataFrame, emisora: str, fecha_senal: str, fecha_objetivo: str, base: float) -> pd.DataFrame:
    """t0..t+5 en sesiones BMV; las sesiones sin PPP verificado quedan en NaN (sin interpolar)."""
    sesiones = core.sesiones_entre(fecha_senal, fecha_objetivo)
    verif = precios[(precios["emisora"] == emisora) & (precios["estado_captura"] == core.ESTADO_PUBLICADO)]
    mapa = dict(zip(verif["fecha"], verif["ppp_bmv_mxn"]))
    hay_boletin = set(precios["fecha"])
    filas = []
    for i, s in enumerate(sesiones):
        p = mapa.get(s)
        filas.append({
            "paso": f"t+{i}" if i else "t0",
            "fecha": s,
            "ppp": p,
            "retorno_pct": (p / base - 1) * 100 if p is not None else np.nan,
            "estado": "OBSERVADO" if p is not None else ("HUECO_DOCUMENTADO" if s in hay_boletin else "FUTURO"),
        })
    return pd.DataFrame(filas)
