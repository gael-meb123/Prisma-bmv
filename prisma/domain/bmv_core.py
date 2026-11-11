"""
Prisma BMV - Núcleo de dominio cuantitativo (sin dependencias de AWS ni de Streamlit).

Este módulo es la única fuente de verdad para:
  * Calendario de sesiones hábiles BMV.
  * Extracción del PPP oficial desde el boletín RSS de la BMV.
  * Ventanas estrictas de 21 sesiones con política de cero imputación.
  * Inferencia de los modelos de 2ª generación (panel G2) con parámetros congelados.
  * Seguimiento prospectivo t+1 ... t+5 y resolución en t+5.

Lo usan tanto la Lambda `recolector-diario-bmv` (se copia dentro del .zip de despliegue)
como la terminal Streamlit. Solo depende de la biblioteca estándar, numpy y pandas, que
están incluidas en la Lambda Layer oficial `AWSSDKPandas-Python311`.
"""

from __future__ import annotations

import html
import math
import os
import re
from datetime import date, timedelta
from typing import Any, Iterable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Contratos de datos
# ---------------------------------------------------------------------------
ESTADO_PUBLICADO = "PPP_PUBLICADO_VERIFICADO"
ESTADO_HUECO = "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA"
# Variantes históricas del mismo estado que se normalizan al leer.
ESTADOS_HUECO_LEGADO = frozenset({"NO_PUBLICADO_EN_BOLETIN_RSS_DEL_DIA", ESTADO_HUECO})

EVIDENCIA_HUECO = (
    "Emisora ausente del boletin RSS de la fecha; hueco conservado, no se imputa valor"
)

# (emisora, serie, anillo de madurez, sector económico)
EMISORAS_15: tuple[tuple[str, str, str, str], ...] = (
    ("GMEXICO", "B", "Anillo 2 (Plata: Seleccion Modelo Sectorial)", "Mineria y materiales"),
    ("GFNORTE", "O", "Anillo 2 (Plata: Seleccion Modelo Sectorial)", "Banca y servicios financieros"),
    ("FEMSA", "UBD", "Anillo 3 (Bronce: Ingesta en Vivo)", "Consumo y comercio"),
    ("AMX", "B", "Anillo 3 (Bronce: Ingesta en Vivo)", "Telecomunicaciones"),
    ("WALMEX", "*", "Anillo 1 (Oro: Inferencia Prospectiva Estricta)", "Comercio y autoservicio"),
    ("CEMEX", "CPO", "Anillo 3 (Bronce: Ingesta en Vivo)", "Cemento y construccion"),
    ("PE&OLES", "*", "Anillo 3 (Bronce: Ingesta en Vivo)", "Mineria y metales"),
    ("GAP", "B", "Anillo 3 (Bronce: Ingesta en Vivo)", "Infraestructura aeroportuaria"),
    ("AC", "*", "Anillo 3 (Bronce: Ingesta en Vivo)", "Bebidas y consumo"),
    ("ASUR", "B", "Anillo 3 (Bronce: Ingesta en Vivo)", "Infraestructura aeroportuaria"),
    ("BIMBO", "A", "Anillo 3 (Bronce: Ingesta en Vivo)", "Industria alimentaria"),
    ("GFINBUR", "O", "Anillo 3 (Bronce: Ingesta en Vivo)", "Servicios financieros"),
    ("VESTA", "*", "Anillo 3 (Bronce: Ingesta en Vivo)", "Inmuebles industriales"),
    ("LIVEPOL", "C-1", "Anillo 3 (Bronce: Ingesta en Vivo)", "Comercio departamental"),
    ("GRUMA", "B", "Anillo 3 (Bronce: Ingesta en Vivo)", "Industria alimentaria"),
)
EMISORAS_PANEL_G2: tuple[str, ...] = ("AMX", "GFNORTE", "GMEXICO", "WALMEX")
META_EMISORA = {t: {"serie": s, "anillo": a, "sector": sec} for t, s, a, sec in EMISORAS_15}

VARIABLES_G2 = ("ret_10", "ret_10_rel_panel", "volatilidad_20")

# Orden canónico de columnas. Athena (OpenCSVSerde) lee por posición: la Lambda, la carga
# inicial y el DDL de infra/athena deben usar exactamente estas listas.
COLUMNAS_SILVER: tuple[str, ...] = (
    "fecha", "emisora", "serie", "anillo_madurez", "sector_economico", "estado_captura",
    "ppp_bmv_mxn", "ultimo_bmv_mxn", "anterior_bmv_mxn", "variacion_ppp_vs_anterior_pct",
    "evidencia_exacta", "url_fuente", "sha256_boletin",
)
COLUMNAS_GOLD_G2: tuple[str, ...] = ('id_senal_g2', 'generacion_modelo', 'fecha_senal', 'fecha_objetivo_h5', 'calendario_objetivo', 'emisora', 'serie', 'sector_economico', 'modelo_g2', 'modo_entrenamiento', 'n_train_panel', 'fin_etiquetas_train_panel', 'c_regularizacion', 'tau_zona_neutral', 'ppp_base_t', 'ret_10', 'media_ret_10_panel_corte', 'ret_10_rel_panel', 'volatilidad_20', 'probabilidad_subida', 'prediccion_clase', 'prediccion_etiqueta', 'estado_consenso_g2', 'estado_resolucion', 'sesiones_transcurridas', 'fecha_parcial_reciente', 'ppp_parcial_reciente', 'retorno_parcial_pct', 'acierto_parcial_en_curso', 'ppp_t5_observado', 'target_y_observado', 'acierto_direccional_t5', 'brier_observado_t5', 'inicio_ventana_21', 'fin_ventana_21', 'sha256_boletin_base', 'url_fuente_base', 'version_features', 'version_metodologia', 'version_monitor_g2', 'timestamp_emision_utc', 'origen_inferencia')

MODELOS_G2_ORDEN = (
    "G2_V1_POOLED_REL3_CALIBRADO",
    "G2_V2_POOLED_REL3_ZONA_NEUTRAL",
    "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO",
)
VENTANA_SESIONES = 21
HORIZONTE_SESIONES = 5

# ---------------------------------------------------------------------------
# Calendario BMV
# ---------------------------------------------------------------------------
# Fuente: https://www.bmv.com.mx/es/grupo-bmv/calendario-de-dias-festivos
FERIADOS_BMV: dict[int, frozenset[str]] = {
    2026: frozenset(
        {
            "2026-01-01", "2026-02-02", "2026-03-16", "2026-04-02", "2026-04-03",
            "2026-05-01", "2026-09-16", "2026-11-02", "2026-11-16", "2026-12-12",
            "2026-12-25",
        }
    ),
}


def _feriados_extra() -> dict[int, set[str]]:
    """Permite cargar calendarios oficiales de años posteriores sin redeploy.

    Variable de entorno FERIADOS_BMV_EXTRA="2027-01-01,2027-02-01,..."; un año solo se
    considera verificado si aparece en FERIADOS_BMV o en esta variable.
    """
    extra: dict[int, set[str]] = {}
    raw = os.environ.get("FERIADOS_BMV_EXTRA", "").strip()
    for item in filter(None, (x.strip() for x in raw.split(","))):
        d = date.fromisoformat(item)
        extra.setdefault(d.year, set()).add(d.isoformat())
    return extra


def calendario_verificado(anio: int) -> bool:
    return anio in FERIADOS_BMV or anio in _feriados_extra()


def es_sesion_bmv(d: date) -> bool:
    """Día hábil BMV: lunes a viernes que no sea feriado oficial publicado."""
    if d.weekday() >= 5:
        return False
    feriados = set(FERIADOS_BMV.get(d.year, frozenset())) | _feriados_extra().get(d.year, set())
    return d.isoformat() not in feriados


def sesiones_entre(inicio: str | date, fin: str | date) -> list[str]:
    """Sesiones hábiles en el intervalo cerrado [inicio, fin], en ISO."""
    cur = date.fromisoformat(str(inicio)) if not isinstance(inicio, date) else inicio
    end = date.fromisoformat(str(fin)) if not isinstance(fin, date) else fin
    out: list[str] = []
    while cur <= end:
        if es_sesion_bmv(cur):
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def sumar_sesiones(fecha: str, n: int) -> str:
    """Fecha ISO que está `n` sesiones hábiles BMV después de `fecha`."""
    d = date.fromisoformat(str(fecha))
    agregadas = 0
    while agregadas < n:
        d += timedelta(days=1)
        if es_sesion_bmv(d):
            agregadas += 1
    return d.isoformat()


def ultimas_sesiones(fecha_corte: str, n: int) -> list[str]:
    """Las `n` sesiones hábiles que terminan exactamente en `fecha_corte` (inclusive)."""
    d = date.fromisoformat(fecha_corte)
    out: list[str] = []
    while len(out) < n:
        if es_sesion_bmv(d):
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(out))


def calendario_objetivo(fecha_senal: str, fecha_objetivo: str) -> str:
    anios = {date.fromisoformat(fecha_senal).year, date.fromisoformat(fecha_objetivo).year}
    if all(calendario_verificado(a) for a in anios):
        return f"OFICIAL_{max(anios)}"
    return "PROVISIONAL_SIN_FERIADOS_VERIFICADOS"


# ---------------------------------------------------------------------------
# Boletín BMV
# ---------------------------------------------------------------------------
def url_boletin(fecha_yyyymmdd: str) -> str:
    return f"https://www.bmv.com.mx/docs-pub/rss/boletin{fecha_yyyymmdd}.html"


def _celdas(fila_html: str, etiqueta: str = "td") -> list[str]:
    patron = rf"<{etiqueta}[^>]*>(.*?)</{etiqueta}>"
    crudas = re.findall(patron, fila_html, flags=re.DOTALL | re.IGNORECASE)
    limpias = []
    for c in crudas:
        txt = html.unescape(re.sub(r"<[^>]+>", "", c))
        txt = re.sub(r"\s+", " ", txt).strip()
        if txt:
            limpias.append(txt)
    return limpias


def _numero(txt: str) -> float:
    return float(txt.replace(",", "").replace("$", "").strip())


def parse_bulletin_quotes(raw_html: bytes | str) -> dict[tuple[str, str], dict[str, float]]:
    """Extrae {(emisora, serie): {ultimo, anterior, ppp, variacion_ppp_vs_anterior_pct}}.

    Reglas de seguridad de la extracción:
      * Solo tablas de cotizaciones (más negociadas / mayor variación); se excluye "Paquetes".
      * La columna PPP es la 5ª celda (Emisora, Serie, Último, Anterior, PPP, ...).
      * Se descarta una fila si la "PPP" coincide con la variación porcentual teórica, lo que
        indica una tabla con columnas desplazadas (defensa contra leer % como precio).
      * Si una emisora aparece en varias tablas se conserva la primera aparición.
      * Nunca se rellena: lo que no se encuentra simplemente no se devuelve.
    """
    if not raw_html:
        return {}
    texto = raw_html.decode("utf-8", errors="ignore") if isinstance(raw_html, bytes) else raw_html
    tablas = re.findall(r"<table[^>]*>(.*?)</table>", texto, flags=re.DOTALL | re.IGNORECASE)
    cotizaciones: dict[tuple[str, str], dict[str, float]] = {}

    for tabla in tablas:
        encabezado = html.unescape(re.sub(r"<[^>]+>", " ", tabla[:400]))
        es_tabla_precios = (
            any(k in encabezado for k in ("Negociadas", "Variac", "Alza", "Baja"))
            and "Paquetes" not in encabezado
        )
        if not es_tabla_precios:
            continue

        filas = re.findall(r"<tr[^>]*>(.*?)</tr>", tabla, flags=re.DOTALL | re.IGNORECASE)
        columnas_esperadas = 0
        for fila in filas:
            cab = _celdas(fila, "th") or _celdas(fila, "td")
            if any("Emisora" in c for c in cab):
                columnas_esperadas = len(cab)
                break

        for fila in filas:
            celdas = _celdas(fila, "td")
            if len(celdas) < 5 or celdas[0] in ("Emisora",) or "Variaci" in celdas[0]:
                continue
            if columnas_esperadas and len(celdas) < columnas_esperadas:
                continue
            try:
                ticker, serie = celdas[0].upper(), celdas[1]
                ultimo, anterior, ppp = _numero(celdas[2]), _numero(celdas[3]), _numero(celdas[4])
            except (ValueError, IndexError):
                continue
            if ppp <= 0 or anterior <= 0:
                continue
            var_teorica = round((ultimo / anterior - 1.0) * 100.0, 2)
            if abs(ppp - var_teorica) < 0.05 and abs(ppp - ultimo) > 5.0:
                continue  # columna desplazada: el "PPP" es en realidad la variación
            clave = (ticker, serie)
            if clave not in cotizaciones:
                cotizaciones[clave] = {
                    "ultimo": ultimo,
                    "anterior": anterior,
                    "ppp": ppp,
                    "variacion_ppp_vs_anterior_pct": round((ppp / anterior - 1.0) * 100.0, 2),
                }
    return cotizaciones


def registros_silver(
    fecha_iso: str, cotizaciones: dict[tuple[str, str], dict[str, float]], url: str, sha256: str
) -> list[dict[str, Any]]:
    """15 filas por sesión: verificadas o huecos documentados. Cero imputación."""
    filas = []
    for ticker, serie, anillo, sector in EMISORAS_15:
        q = cotizaciones.get((ticker, serie))
        base = {
            "fecha": fecha_iso,
            "emisora": ticker,
            "serie": serie,
            "anillo_madurez": anillo,
            "sector_economico": sector,
            "url_fuente": url,
            "sha256_boletin": sha256,
        }
        if q is not None:
            base.update(
                estado_captura=ESTADO_PUBLICADO,
                ppp_bmv_mxn=q["ppp"],
                ultimo_bmv_mxn=q["ultimo"],
                anterior_bmv_mxn=q["anterior"],
                variacion_ppp_vs_anterior_pct=q["variacion_ppp_vs_anterior_pct"],
                evidencia_exacta=f"{ticker} / {serie} / PPP / {q['ppp']:.2f}",
            )
        else:
            base.update(
                estado_captura=ESTADO_HUECO,
                ppp_bmv_mxn=None,
                ultimo_bmv_mxn=None,
                anterior_bmv_mxn=None,
                variacion_ppp_vs_anterior_pct=None,
                evidencia_exacta=EVIDENCIA_HUECO,
            )
        filas.append(base)
    return filas


def normalizar_estado_captura(serie: pd.Series) -> pd.Series:
    return serie.where(~serie.isin(ESTADOS_HUECO_LEGADO), ESTADO_HUECO)


# ---------------------------------------------------------------------------
# Features con ventana estricta de 21 sesiones
# ---------------------------------------------------------------------------
def calcular_features_ppp(ventana: Iterable[float]) -> dict[str, float]:
    """Las 8 variables canónicas PPP_V2_MEDIA20. Exige 21 PPP finitos y positivos."""
    p = np.asarray(list(ventana), dtype=float)
    if p.shape != (VENTANA_SESIONES,) or not np.all(np.isfinite(p) & (p > 0)):
        raise ValueError("Se requieren 21 PPP finitos y positivos, sin imputación")
    rets = p[1:] / p[:-1] - 1.0
    return {
        "ret_1": p[-1] / p[-2] - 1.0,
        "ret_5": p[-1] / p[-6] - 1.0,
        "ret_10": p[-1] / p[-11] - 1.0,
        "ret_20": p[-1] / p[0] - 1.0,
        "volatilidad_5": float(np.std(rets[-5:], ddof=1)),
        "volatilidad_20": float(np.std(rets, ddof=1)),
        "distancia_media_5": p[-1] / np.mean(p[-5:]) - 1.0,
        "distancia_media_20": p[-1] / np.mean(p[-20:]) - 1.0,
    }


def extraer_ventanas_panel(
    serie: pd.DataFrame, fecha_corte: str, emisoras: Iterable[str] = EMISORAS_PANEL_G2
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Audita la ventana de 21 sesiones de cada emisora y calcula features solo si está completa.

    Una sesión del calendario sin PPP verificado para la emisora es un hueco real: la ventana
    queda bloqueada y la emisora no recibe inferencia ese día. Nunca se comprime la serie ni
    se rellenan valores. `ret_10_rel_panel` se calcula solo entre emisoras elegibles.
    """
    fechas_21 = ultimas_sesiones(fecha_corte, VENTANA_SESIONES)
    if fechas_21[-1] != fecha_corte:
        raise ValueError(f"{fecha_corte} no es sesión hábil BMV")
    verificadas = serie[serie["estado_captura"] == ESTADO_PUBLICADO]

    estados, elegibles = [], []
    for em in emisoras:
        sub = (
            verificadas[verificadas["emisora"] == em]
            .drop_duplicates("fecha", keep="last")
            .set_index("fecha")
            .reindex(fechas_21)
        )
        precios = pd.to_numeric(sub["ppp_bmv_mxn"], errors="coerce").to_numpy(dtype=float)
        ok = np.isfinite(precios) & (precios > 0)
        faltantes = [f for f, v in zip(fechas_21, ok) if not v]
        completa = not faltantes
        estados.append(
            {
                "fecha_corte": fecha_corte,
                "emisora": em,
                "sesiones_con_ppp_en_ventana_21": int(ok.sum()),
                "huecos_en_ventana_21": len(faltantes),
                "ventana_21_completa_apta_inferencia": completa,
                "inicio_ventana_21": fechas_21[0],
                "fin_ventana_21": fechas_21[-1],
                "fechas_huecos_ventana_21": ";".join(faltantes) if faltantes else "NINGUNO",
                "estado_inferencia_g2": (
                    "ELEGIBLE_VENTANA_21_COMPLETA"
                    if completa
                    else f"BLOQUEADA_HUECOS_REALES_{int(ok.sum())}_DE_21"
                ),
            }
        )
        if completa:
            fila = {"fecha": fecha_corte, "emisora": em, "ppp_t": float(precios[-1])}
            fila.update(calcular_features_ppp(precios))
            fila["inicio_ventana_21"], fila["fin_ventana_21"] = fechas_21[0], fechas_21[-1]
            elegibles.append(fila)

    df_estado = pd.DataFrame(estados)
    df_eleg = pd.DataFrame(elegibles)
    if not df_eleg.empty:
        media = float(df_eleg["ret_10"].mean())
        df_eleg["media_ret_10_panel_corte"] = media
        df_eleg["ret_10_rel_panel"] = df_eleg["ret_10"] - media if len(df_eleg) >= 2 else 0.0
    return df_estado, df_eleg


# ---------------------------------------------------------------------------
# Inferencia G2 con parámetros congelados
# ---------------------------------------------------------------------------
def _sigmoide(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def probabilidad_g2(params_modelo: dict[str, Any], emisora: str, x: dict[str, float]) -> float:
    """P(PPP_{t+5} > PPP_t) con el escalador específico de la emisora del registro oficial."""
    escaladores = params_modelo["scalers_por_emisora"]
    if emisora not in escaladores:
        raise KeyError(f"Sin escalador oficial para {emisora}; no se infiere (cero imputación)")
    sc = escaladores[emisora]
    beta = params_modelo["beta"]
    variables = params_modelo.get("variables", list(VARIABLES_G2))
    z = beta[0]
    for i, var in enumerate(variables):
        z += beta[i + 1] * (float(x[var]) - sc["mean"][i]) / sc["scale"][i]
    return _sigmoide(z)


def contribuciones_log_odds(
    params_modelo: dict[str, Any], emisora: str, x: dict[str, float]
) -> dict[str, float]:
    """Descomposición aditiva del log-odds: intercepto + beta_i * z_i por variable."""
    sc = params_modelo["scalers_por_emisora"][emisora]
    beta = params_modelo["beta"]
    variables = params_modelo.get("variables", list(VARIABLES_G2))
    out = {"intercepto": float(beta[0])}
    for i, var in enumerate(variables):
        out[var] = float(beta[i + 1] * (float(x[var]) - sc["mean"][i]) / sc["scale"][i])
    return out


def etiqueta_consenso_g2(clases: list[int]) -> str:
    if all(c == 1 for c in clases):
        return "CONSENSO_PANEL_G2_SUBIDA"
    if all(c == 0 for c in clases):
        return "CONSENSO_PANEL_G2_NO_SUBIDA"
    nom = lambda c: "SUBIDA" if c == 1 else "NO_SUBIDA"  # noqa: E731
    v1, v2, v3 = (nom(c) for c in clases)
    return f"DIVERGENCIA_G2 (V1={v1}, V2={v2}, V3={v3})"


def inferir_panel_g2(
    elegibles: pd.DataFrame,
    modelos: dict[str, dict[str, Any]],
    fecha_senal: str,
    sha256_boletin: str,
    url_fuente: str,
    timestamp_utc: str,
) -> list[dict[str, Any]]:
    """Genera las filas Gold G2 (una por emisora y modelo) para la fecha de señal."""
    if elegibles.empty:
        return []
    fecha_obj = sumar_sesiones(fecha_senal, HORIZONTE_SESIONES)
    cal = calendario_objetivo(fecha_senal, fecha_obj)
    filas: list[dict[str, Any]] = []
    for _, r in elegibles.iterrows():
        em = str(r["emisora"])
        x = {v: float(r[v]) for v in VARIABLES_G2}
        try:
            probs = {m: probabilidad_g2(modelos[m], em, x) for m in MODELOS_G2_ORDEN}
        except KeyError:
            continue
        clases = [int(probs[m] >= 0.5) for m in MODELOS_G2_ORDEN]
        consenso = etiqueta_consenso_g2(clases)
        meta = META_EMISORA.get(em, {"serie": "", "sector": ""})
        for m, clase in zip(MODELOS_G2_ORDEN, clases):
            filas.append(
                {
                    "id_senal_g2": f"G2_{fecha_senal.replace('-', '')}_{em}_{m}",
                    "generacion_modelo": "SEGUNDA_GENERACION_POOLED_PANEL_REL3",
                    "fecha_senal": fecha_senal,
                    "fecha_objetivo_h5": fecha_obj,
                    "calendario_objetivo": cal,
                    "emisora": em,
                    "serie": meta["serie"],
                    "sector_economico": meta["sector"],
                    "modelo_g2": m,
                    "modo_entrenamiento": "PARAMETROS_CONGELADOS_REGISTRO_OFICIAL",
                    "c_regularizacion": modelos[m].get("c_val"),
                    "tau_zona_neutral": modelos[m].get("tau_val"),
                    "ppp_base_t": float(r["ppp_t"]),
                    "ret_10": x["ret_10"],
                    "media_ret_10_panel_corte": float(r["media_ret_10_panel_corte"]),
                    "ret_10_rel_panel": x["ret_10_rel_panel"],
                    "volatilidad_20": x["volatilidad_20"],
                    "probabilidad_subida": round(probs[m], 6),
                    "prediccion_clase": clase,
                    "prediccion_etiqueta": "SUBIDA" if clase == 1 else "NO_SUBIDA",
                    "estado_consenso_g2": consenso,
                    "estado_resolucion": "PENDIENTE_T+5",
                    "sesiones_transcurridas": 0,
                    "fecha_parcial_reciente": None,
                    "ppp_parcial_reciente": None,
                    "retorno_parcial_pct": None,
                    "acierto_parcial_en_curso": None,
                    "ppp_t5_observado": None,
                    "target_y_observado": None,
                    "acierto_direccional_t5": None,
                    "brier_observado_t5": None,
                    "inicio_ventana_21": r["inicio_ventana_21"],
                    "fin_ventana_21": r["fin_ventana_21"],
                    "sha256_boletin_base": sha256_boletin,
                    "url_fuente_base": url_fuente,
                    "origen_inferencia": "LAMBDA_RECOLECTOR_DIARIO_BMV",
                    "timestamp_emision_utc": timestamp_utc,
                }
            )
    return filas


# ---------------------------------------------------------------------------
# Seguimiento prospectivo t+1 ... t+5
# ---------------------------------------------------------------------------
ESTADOS_FINALES = ("RESUELTA_T+5", "NO_EVALUABLE_HUECO_EN_T+5")


def _a_bool(v: Any) -> bool | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("true", "1", "1.0"):
        return True
    if s in ("false", "0", "0.0"):
        return False
    return None


def acierto_direccional(clase: int, retorno: float) -> bool:
    """Y = 1 si PPP_t+k > PPP_t. SUBIDA acierta con retorno > 0; NO_SUBIDA con retorno <= 0."""
    return (retorno > 0) == (int(clase) == 1)


def actualizar_seguimiento(gold: pd.DataFrame, serie: pd.DataFrame, fecha_hoy: str) -> pd.DataFrame:
    """Actualiza mark-to-market de señales abiertas usando únicamente PPP verificados.

    Idempotente: el resultado depende solo de la serie disponible hasta `fecha_hoy`.
    * sesiones_transcurridas = sesiones hábiles BMV en (fecha_senal, min(hoy, objetivo)].
    * El PPP parcial es el último verificado dentro de esa ventana (nunca interpolado).
    * En t+5 se resuelve solo si existe PPP verificado exactamente en la fecha objetivo;
      si el boletín de esa fecha existe pero la emisora no aparece, la señal queda
      NO_EVALUABLE_HUECO_EN_T+5 (no se sustituye por el día anterior ni posterior).
    """
    if gold.empty:
        return gold
    gold = gold.copy()
    serie = serie.copy()
    serie["estado_captura"] = normalizar_estado_captura(serie["estado_captura"])
    fechas_con_boletin = set(serie["fecha"].astype(str))
    verif = serie[serie["estado_captura"] == ESTADO_PUBLICADO]
    precio = {
        (str(r.fecha), str(r.emisora)): float(r.ppp_bmv_mxn)
        for r in verif.itertuples()
        if pd.notna(r.ppp_bmv_mxn)
    }

    for col in ("fecha_parcial_reciente", "acierto_parcial_en_curso", "estado_resolucion"):
        if col in gold.columns:
            gold[col] = gold[col].astype(object)

    for idx, r in gold.iterrows():
        if str(r.get("estado_resolucion", "")) in ESTADOS_FINALES:
            continue
        f0, fobj, em = str(r["fecha_senal"]), str(r["fecha_objetivo_h5"]), str(r["emisora"])
        base = float(r["ppp_base_t"])
        limite = min(fecha_hoy, fobj)
        posteriores = [s for s in sesiones_entre(f0, limite) if s > f0]
        n = len(posteriores)
        gold.at[idx, "sesiones_transcurridas"] = min(n, HORIZONTE_SESIONES)

        observadas = [(s, precio[(s, em)]) for s in posteriores if (s, em) in precio]
        if observadas:
            s_ult, p_ult = observadas[-1]
            ret = (p_ult / base - 1.0) * 100.0
            gold.at[idx, "fecha_parcial_reciente"] = s_ult
            gold.at[idx, "ppp_parcial_reciente"] = p_ult
            gold.at[idx, "retorno_parcial_pct"] = round(ret, 4)
            gold.at[idx, "acierto_parcial_en_curso"] = acierto_direccional(r["prediccion_clase"], ret)

        if fecha_hoy >= fobj and fobj in fechas_con_boletin:
            if (fobj, em) in precio:
                p5 = precio[(fobj, em)]
                y = int(p5 > base)
                prob = float(r["probabilidad_subida"])
                gold.at[idx, "ppp_t5_observado"] = p5
                gold.at[idx, "target_y_observado"] = y
                gold.at[idx, "acierto_direccional_t5"] = int(y == int(r["prediccion_clase"]))
                gold.at[idx, "brier_observado_t5"] = round((prob - y) ** 2, 6)
                gold.at[idx, "estado_resolucion"] = "RESUELTA_T+5"
            else:
                gold.at[idx, "estado_resolucion"] = "NO_EVALUABLE_HUECO_EN_T+5"
        elif n > 0:
            gold.at[idx, "estado_resolucion"] = f"EN_CURSO_T+{min(n, HORIZONTE_SESIONES)}"
        else:
            gold.at[idx, "estado_resolucion"] = "PENDIENTE_T+5"
    return gold
