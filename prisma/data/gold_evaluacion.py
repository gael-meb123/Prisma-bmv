"""Lector de solo lectura del archivo histórico Gold (evaluación de modelos G2/G1 en S3).

Solo se invoca cuando la bandera ``GOLD_EVALUACION_HABILITADA=true`` está activa en
un entorno de evaluación/entrega. No escribe en S3, no imputa precios ausentes y
etiqueta explícitamente cada respuesta como archivo histórico en evaluación.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
from datetime import date, timedelta

from prisma.domain.calendario_bmv import FERIADOS_BMV

KEY_GOLD_G2 = "gold/senales_g2/registro_senales_prospectivas_panel_g2.csv"
KEY_GOLD_G1 = "gold/senales_g1/registro_senales_prospectivas_walmex.csv"
KEY_REGISTRO_MODELOS = "evidencias/modelos_evaluacion/registro_modelos_g2_oficial.json"
KEY_METRICAS_MODELOS = "evidencias/modelos_evaluacion/metricas_institucionales_v1.json"

CONSENSO_G2_MODELOS = (
    "G2_V1_POOLED_REL3_CALIBRADO",
    "G2_V2_POOLED_REL3_ZONA_NEUTRAL",
    "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO",
    "G2_V4_POOLED_DM5_REL_CORTO_PLAZO",
    "G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL",
)

NOMBRES_MODELO = {
    "G2_V1_POOLED_REL3_CALIBRADO": "G2-V1 Calibrado",
    "G2_V2_POOLED_REL3_ZONA_NEUTRAL": "G2-V2 Zona neutral",
    "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO": "G2-V3 Alta discriminación",
    "G2_V4_POOLED_DM5_REL_CORTO_PLAZO": "G2-V4 Agotamiento corto (DM5)",
    "G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL": "G2-V5 Adaptativo por régimen",
    "G2_V4_F1_GAP": "G2-V4 + Gap intradía (UH-PPP)",
    "V1_CONTROL_LOGREG": "G1-V1 Logística base",
    "V2R_RETADOR_LINEAL_AJUSTE_DIVIDENDOS": "G1-V2R Ajuste dividendos",
    "V3_RETADOR_SELECCIONADO_RF": "G1-V3 Random Forest",
    "V2_RETADOR_HIBRIDO_BOLETIN": "G1-V2 Híbrido boletín",
}

AVISO_EVALUACION = (
    "Archivo histórico Gold en evaluación (solo lectura S3); la emisión productiva "
    "continua permanece sujeta a la compuerta de ventana limpia 21/21 y conciliación final."
)


def _num(valor, nd=None):
    if valor is None or valor == "":
        return None
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return round(n, nd) if nd is not None else n


def _int(valor):
    n = _num(valor)
    return int(n) if n is not None else None


def _bool(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        return valor
    s = str(valor).strip().lower()
    if s in ("true", "1", "1.0", "si", "sí"):
        return True
    if s in ("false", "0", "0.0", "no"):
        return False
    return None


def _nombre(modelo: str) -> str:
    return NOMBRES_MODELO.get(modelo, modelo)


def _modelo_g1(id_senal: str) -> str:
    m = re.match(r"^[A-Z&]+_\d{8}_(.+)$", str(id_senal or ""))
    return m.group(1) if m else str(id_senal or "")


def _consenso_clases(clases: list[int]) -> str:
    if clases and all(c == 1 for c in clases):
        return "CONSENSO_ALTO_SUBIDA"
    if clases and all(c == 0 for c in clases):
        return "CONSENSO_ALTO_NO_SUBIDA"
    return "DIVERGENCIA_ALERTA"


def _es_sesion_bmv(dia: date) -> bool:
    if dia.weekday() >= 5:
        return False
    return dia.isoformat() not in FERIADOS_BMV.get(dia.year, frozenset())


def _sesiones_entre(desde_iso: str, hasta_iso: str) -> list[str]:
    try:
        actual = date.fromisoformat(desde_iso)
        fin = date.fromisoformat(hasta_iso)
    except (TypeError, ValueError):
        return []
    out = []
    while actual <= fin and len(out) < 20:
        if _es_sesion_bmv(actual):
            out.append(actual.isoformat())
        actual += timedelta(days=1)
    return out


def _leer_csv_s3(s3, bucket: str, key: str, max_bytes: int = 5_000_000) -> list[dict]:
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        raw = obj["Body"].read(max_bytes + 1)
        if len(raw) > max_bytes:
            return []
        return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
    except Exception:
        return []


def _leer_json_s3(s3, bucket: str, key: str, max_bytes: int = 2_000_000) -> dict:
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        raw = obj["Body"].read(max_bytes + 1)
        if len(raw) > max_bytes:
            return {}
        data = json.loads(raw.decode("utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def cargar_metricas_modelos(s3, bucket: str) -> dict | None:
    data = _leer_json_s3(s3, bucket, KEY_METRICAS_MODELOS)
    if not data:
        return None
    return {
        **data,
        "modo_evaluacion_gold": True,
        "aviso_evaluacion": AVISO_EVALUACION,
    }


def _normalizar_g2(filas: list[dict]) -> list[dict]:
    out = []
    for r in filas:
        em = (r.get("emisora") or "").strip().upper()
        f = (r.get("fecha_senal") or "").strip()
        mod = (r.get("modelo_g2") or "").strip()
        prob = _num(r.get("probabilidad_subida"))
        clase = _int(r.get("prediccion_clase"))
        if not em or not f or not mod or prob is None or clase not in (0, 1):
            continue
        out.append({
            **r,
            "emisora": em,
            "fecha_senal": f,
            "modelo_g2": mod,
            "probabilidad_subida": prob,
            "prediccion_clase": clase,
            "ppp_base_t": _num(r.get("ppp_base_t")),
            "ret_10": _num(r.get("ret_10")),
            "ret_10_rel_panel": _num(r.get("ret_10_rel_panel")),
            "volatilidad_20": _num(r.get("volatilidad_20")),
            "sesiones_transcurridas": _int(r.get("sesiones_transcurridas")) or 0,
            "retorno_parcial_pct": _num(r.get("retorno_parcial_pct")),
            "acierto_parcial_en_curso": _bool(r.get("acierto_parcial_en_curso")),
            "acierto_direccional_t5": _int(r.get("acierto_direccional_t5")),
            "brier_observado_t5": _num(r.get("brier_observado_t5")),
            "generacion": "G2",
        })
    return out


def _normalizar_g1(filas: list[dict]) -> list[dict]:
    out = []
    for r in filas:
        em = (r.get("emisora") or "").strip().upper()
        f = (r.get("fecha_senal") or "").strip()
        prob_pct = _num(r.get("prob_subida_pct"))
        clase = _int(r.get("prediccion_clase"))
        if not em or not f or prob_pct is None or clase not in (0, 1):
            continue
        valida = (r.get("estado_validez") or "VALIDA").strip().upper() == "VALIDA"
        mod = _modelo_g1(r.get("id_senal", ""))
        out.append({
            "id_senal_g2": r.get("id_senal", ""),
            "fecha_senal": f,
            "fecha_objetivo_h5": (r.get("fecha_objetivo_h5") or "").strip(),
            "emisora": em,
            "modelo_g2": mod,
            "ppp_base_t": _num(r.get("ppp_base_mxn")),
            "probabilidad_subida": round(prob_pct / 100.0, 6),
            "prediccion_clase": clase,
            "valida": valida,
            "estado_resolucion": (r.get("estado_resolucion") or "PENDIENTE_T+5").strip(),
            "generacion": "G1",
        })
    return out


def _mapa_precios_verificados(precios_filas: list[dict]) -> tuple[dict[tuple[str, str], float], set[str], str | None]:
    mapa = {}
    fechas = set()
    for r in precios_filas:
        f = (r.get("fecha") or "").strip()
        em = (r.get("emisora") or "").strip().upper()
        if not f or not em:
            continue
        fechas.add(f)
        if r.get("estado_captura") == "PPP_PUBLICADO_VERIFICADO":
            ppp = _num(r.get("ppp_bmv_mxn"))
            if ppp is not None and ppp > 0:
                mapa[(em, f)] = ppp
    corte = max(fechas) if fechas else None
    return mapa, fechas, corte


def _enriquecer_seguimiento(senales: list[dict], precios_filas: list[dict]) -> tuple[list[dict], str | None]:
    mapa, fechas_disp, fecha_corte = _mapa_precios_verificados(precios_filas)
    out = []
    for s in senales:
        em = s["emisora"]
        f_sen = s["fecha_senal"]
        f_obj = (s.get("fecha_objetivo_h5") or "").strip()
        base = s.get("ppp_base_t")
        clase = s["prediccion_clase"]
        prob = s["probabilidad_subida"]
        sesiones = _sesiones_entre(f_sen, f_obj)
        posteriores = [f for f in sesiones[1:] if (em, f) in mapa]
        estado = s.get("estado_resolucion") or "PENDIENTE_T+5"
        ret_parcial = s.get("retorno_parcial_pct")
        f_parcial = (s.get("fecha_parcial_reciente") or "").strip()
        acierto_parcial = s.get("acierto_parcial_en_curso")
        acierto_t5 = s.get("acierto_direccional_t5")
        brier_t5 = s.get("brier_observado_t5")

        if base and base > 0 and posteriores:
            ult_f = posteriores[-1]
            ult_p = mapa[(em, ult_f)]
            ret_parcial = round((ult_p / base - 1.0) * 100.0, 4)
            f_parcial = ult_f
            y_parc = 1 if ult_p > base else 0
            acierto_parcial = (y_parc == clase)
            if f_obj and (em, f_obj) in mapa:
                p_t5 = mapa[(em, f_obj)]
                y_t5 = 1 if p_t5 > base else 0
                estado = "RESUELTA_T+5"
                acierto_t5 = 1 if y_t5 == clase else 0
                brier_t5 = round((prob - y_t5) ** 2, 6)
            elif f_obj and fecha_corte and fecha_corte >= f_obj and f_obj in fechas_disp:
                estado = "NO_EVALUABLE_SIN_PPP_T+5"
            else:
                estado = "EN_SEGUIMIENTO_PARCIAL"
        out.append({
            **s,
            "estado_resolucion": estado,
            "sesiones_transcurridas": len(posteriores),
            "fecha_parcial_reciente": f_parcial,
            "retorno_parcial_pct": ret_parcial,
            "acierto_parcial_en_curso": acierto_parcial,
            "acierto_direccional_t5": acierto_t5,
            "brier_observado_t5": brier_t5,
        })
    return out, fecha_corte


def _explicar_factor_g2(modelos_reg: dict, fila: dict) -> dict:
    em = fila["emisora"]
    mod = fila["modelo_g2"]
    ret_rel = fila.get("ret_10_rel_panel")
    ret_pct = round(ret_rel * 100.0, 4) if ret_rel is not None else None
    p = modelos_reg.get(mod)
    if not p or em not in (p.get("scalers_por_emisora") or {}):
        return {
            "modelo": mod, "nombre": _nombre(mod), "ret_rel_pp": ret_pct, "z_rel": None,
            "contribuciones": {}, "log_odds_total": None, "probabilidad_reconstruida": None,
            "lectura": "Sin parámetros registrados para descomponer la señal.",
            "ppp_base": _num(fila.get("ppp_base_t"), 4),
        }
    variables = p.get("variables") or ["ret_10", "ret_10_rel_panel", "volatilidad_20"]
    if "ret_10_rel_panel" not in variables or any(fila.get(v) is None for v in variables):
        return {
            "modelo": mod, "nombre": _nombre(mod), "ret_rel_pp": ret_pct, "z_rel": None,
            "contribuciones": {}, "log_odds_total": None, "probabilidad_reconstruida": None,
            "lectura": (
                f"{_nombre(mod)} usa variables propias ({', '.join(variables)}); "
                "la descomposición exacta está disponible en G2-V1, V2 y V3."
            ),
            "ppp_base": _num(fila.get("ppp_base_t"), 4),
        }
    sc = p["scalers_por_emisora"][em]
    beta = p["beta"]
    contrib = {"intercepto": round(float(beta[0]), 6)}
    z_rel = None
    for i, var in enumerate(variables):
        val = float(fila[var])
        z = (val - float(sc["mean"][i])) / float(sc["scale"][i])
        if var == "ret_10_rel_panel":
            z_rel = round(z, 4)
        contrib[var] = round(float(beta[i + 1]) * z, 6)
    total = round(sum(contrib.values()), 6)
    prob_rec = round(1.0 / (1.0 + math.exp(-total)), 6)
    idx_rel = variables.index("ret_10_rel_panel")
    signo_beta = "negativo" if float(beta[idx_rel + 1]) < 0 else "positivo"
    if z_rel is not None and z_rel <= -1.5:
        lectura = (
            f"{em} va {abs(ret_pct):.2f} pp por debajo del promedio del panel en 10 sesiones "
            f"({z_rel:+.2f} desviaciones respecto a su historia). Con coeficiente {signo_beta}, "
            "el rezago relativo empuja la probabilidad hacia la subida (reversión a la media)."
        )
    elif z_rel is not None and z_rel >= 1.5:
        lectura = (
            f"{em} va {ret_pct:.2f} pp por encima del panel ({z_rel:+.2f} desviaciones). "
            f"Con coeficiente {signo_beta}, la sobreextensión relativa resta probabilidad de subida."
        )
    else:
        lectura = (
            f"El retorno relativo de {em} ({ret_pct:+.2f} pp, {z_rel:+.2f} desviaciones) está dentro de su "
            "rango habitual; el factor aporta de forma moderada frente al resto de variables."
        )
    return {
        "modelo": mod, "nombre": _nombre(mod), "ret_rel_pp": ret_pct, "z_rel": z_rel,
        "contribuciones": contrib, "log_odds_total": total, "probabilidad_reconstruida": prob_rec,
        "lectura": lectura, "ppp_base": _num(fila.get("ppp_base_t"), 4),
    }


def senales_panel(s3, bucket: str, permitidas: list[str], fecha: str | None = None, emisora: str | None = None) -> dict:
    g2 = _normalizar_g2(_leer_csv_s3(s3, bucket, KEY_GOLD_G2))
    g2 = [r for r in g2 if r["emisora"] in permitidas]
    if emisora:
        g2 = [r for r in g2 if r["emisora"] == emisora]
    fechas = sorted({r["fecha_senal"] for r in g2}, reverse=True)
    if fecha and fecha in fechas:
        corte = fecha
    elif fecha:
        corte = next((f for f in fechas if f <= fecha), fechas[0] if fechas else None)
    else:
        corte = fechas[0] if fechas else None
    if corte:
        g2 = [r for r in g2 if r["fecha_senal"] == corte]
    registros = [{
        "id_senal_g2": r.get("id_senal_g2", ""),
        "fecha_senal": r["fecha_senal"],
        "muestra_evaluacion": r.get("muestra_evaluacion") or "IN_SAMPLE_DISENO",
        "fecha_objetivo_h5": r.get("fecha_objetivo_h5", ""),
        "emisora": r["emisora"],
        "sector": r.get("sector_economico", ""),
        "modelo_g2": r["modelo_g2"],
        "ppp_base_t": r["ppp_base_t"] or 0.0,
        "ret_10": r["ret_10"] or 0.0,
        "ret_10_rel_panel": r["ret_10_rel_panel"] or 0.0,
        "volatilidad_20": r["volatilidad_20"] or 0.0,
        "probabilidad_subida": r["probabilidad_subida"],
        "prediccion_etiqueta": r.get("prediccion_etiqueta") or ("SUBIDA" if r["prediccion_clase"] == 1 else "NO_SUBIDA"),
        "estado_consenso_g2": r.get("estado_consenso_g2", ""),
        "estado_resolucion": r.get("estado_resolucion", ""),
        "sesiones_transcurridas": r["sesiones_transcurridas"],
        "retorno_parcial_pct": r["retorno_parcial_pct"],
        "acierto_parcial_en_curso": r["acierto_parcial_en_curso"],
        "sha256_boletin_base": r.get("sha256_boletin_base", ""),
    } for r in g2]
    return {"fecha": corte, "modo_evaluacion_gold": True, "aviso_evaluacion": AVISO_EVALUACION, "senales": registros}


def consenso_g2(s3, bucket: str, permitidas: list[str], fecha: str | None = None) -> dict:
    g2 = _normalizar_g2(_leer_csv_s3(s3, bucket, KEY_GOLD_G2))
    esperados = set(CONSENSO_G2_MODELOS)
    fechas = sorted({r["fecha_senal"] for r in g2 if r["modelo_g2"] in esperados}, reverse=True)
    if fecha and fecha in fechas:
        corte = fecha
    elif fecha:
        corte = next((f for f in fechas if f <= fecha), fechas[0] if fechas else fecha)
    else:
        corte = fechas[0] if fechas else None
    filas = []
    for em in permitidas:
        sub = [r for r in g2 if r["emisora"] == em and r["fecha_senal"] == corte and r["modelo_g2"] in esperados]
        modelos = []
        vistos = set()
        duplicados = False
        objetivos = set()
        for r in sorted(sub, key=lambda x: x["modelo_g2"]):
            if r["modelo_g2"] in vistos:
                duplicados = True
            vistos.add(r["modelo_g2"])
            if r.get("fecha_objetivo_h5"):
                objetivos.add(r["fecha_objetivo_h5"])
            if 0.0 <= r["probabilidad_subida"] <= 1.0:
                modelos.append({
                    "id": r["modelo_g2"], "nombre": _nombre(r["modelo_g2"]),
                    "clase": r["prediccion_clase"], "probabilidad": r["probabilidad_subida"],
                })
        obj_valido = False
        if len(objetivos) == 1 and corte:
            try:
                obj_valido = date.fromisoformat(next(iter(objetivos))) > date.fromisoformat(corte)
            except ValueError:
                obj_valido = False
        completos = (len(sub) == len(esperados) and not duplicados and obj_valido
                     and {m["id"] for m in modelos} == esperados and len(modelos) == len(esperados))
        clases = [m["clase"] for m in modelos]
        estado = ("sin_datos" if not sub else "incompleto" if not completos else
                  "subida" if all(c == 1 for c in clases) else
                  "no_subida" if all(c == 0 for c in clases) else "divergencia")
        filas.append({
            "emisora": em,
            "fecha_senal": corte if sub else None,
            "fecha_objetivo": next(iter(objetivos)) if obj_valido else None,
            "estado": estado,
            "modelos": modelos,
            "modelos_validos": len({m["id"] for m in modelos}),
            "modelos_esperados": len(esperados),
            "razon_incompleto": (
                "Faltan modelos o hay señales duplicadas, inválidas o con objetivos inconsistentes."
                if estado == "incompleto" else None
            ),
        })
    return {
        "fecha_sesion": corte,
        "generacion": "G2",
        "horizonte": "5 sesiones",
        "modelos_esperados": [{"id": m, "nombre": _nombre(m)} for m in CONSENSO_G2_MODELOS],
        "emisoras": filas,
        "modo_evaluacion_gold": True,
        "aviso_evaluacion": AVISO_EVALUACION,
    }


def senal_emisora(s3, bucket: str, emisora: str, fecha: str | None = None) -> dict:
    g2 = [r for r in _normalizar_g2(_leer_csv_s3(s3, bucket, KEY_GOLD_G2)) if r["emisora"] == emisora]
    g1 = [r for r in _normalizar_g1(_leer_csv_s3(s3, bucket, KEY_GOLD_G1)) if r["emisora"] == emisora] if emisora == "WALMEX" else []
    fechas = sorted({r["fecha_senal"] for r in g2} | {r["fecha_senal"] for r in g1}, reverse=True)
    if not fechas:
        return {"emisora": emisora, "fecha": None, "fechas": [], "modelos": [], "consensos": {}, "factor": None,
                "modo_evaluacion_gold": True, "aviso_evaluacion": AVISO_EVALUACION}
    f = fecha if fecha in fechas else next((x for x in fechas if not fecha or x <= fecha), fechas[0])
    modelos = []
    for r in g1:
        if r["fecha_senal"] == f:
            modelos.append({
                "generacion": "G1", "modelo": r["modelo_g2"], "nombre": _nombre(r["modelo_g2"]),
                "probabilidad": round(r["probabilidad_subida"], 6), "clase": r["prediccion_clase"], "valida": r["valida"],
            })
    filas_g2 = sorted((r for r in g2 if r["fecha_senal"] == f), key=lambda x: x["modelo_g2"])
    for r in filas_g2:
        modelos.append({
            "generacion": "G2", "modelo": r["modelo_g2"], "nombre": _nombre(r["modelo_g2"]),
            "probabilidad": round(r["probabilidad_subida"], 6), "clase": r["prediccion_clase"], "valida": True,
        })
    consensos = {}
    for gen in ("G1", "G2"):
        cl = [m["clase"] for m in modelos if m["generacion"] == gen and m["valida"]]
        if cl:
            consensos[gen] = _consenso_clases(cl)
    factor = None
    if filas_g2:
        reg = _leer_json_s3(s3, bucket, KEY_REGISTRO_MODELOS)
        explicaciones = [_explicar_factor_g2(reg, fila) for fila in filas_g2]
        factor = next((ex for ex in explicaciones if ex["contribuciones"]), explicaciones[0])
    return {
        "emisora": emisora, "fecha": f, "fechas": fechas[:30],
        "modelos": modelos, "consensos": consensos, "factor": factor,
        "modo_evaluacion_gold": True, "aviso_evaluacion": AVISO_EVALUACION,
    }


def seguimiento_emisora(s3, bucket: str, precios_filas: list[dict], emisora: str, fecha_senal: str | None = None) -> dict:
    g2 = [r for r in _normalizar_g2(_leer_csv_s3(s3, bucket, KEY_GOLD_G2)) if r["emisora"] == emisora]
    g1 = [r for r in _normalizar_g1(_leer_csv_s3(s3, bucket, KEY_GOLD_G1)) if r["emisora"] == emisora and r["valida"]] if emisora == "WALMEX" else []
    enr, _ = _enriquecer_seguimiento(g2 + g1, precios_filas)
    if not enr:
        return {"emisora": emisora, "fecha_senal": None, "fechas": [], "trayectoria": [], "modelos": [], "resumen": None,
                "modo_evaluacion_gold": True, "aviso_evaluacion": AVISO_EVALUACION}
    fechas = sorted({r["fecha_senal"] for r in enr}, reverse=True)
    if fecha_senal not in fechas:
        con_precio = {r["fecha_senal"] for r in enr if r.get("acierto_parcial_en_curso") is not None}
        fecha_senal = next((f for f in fechas if f in con_precio), fechas[0])
    corte_filas = sorted((r for r in enr if r["fecha_senal"] == fecha_senal), key=lambda x: (x["generacion"], x["modelo_g2"]))
    r0 = corte_filas[0]
    base = r0["ppp_base_t"]
    f_obj = r0.get("fecha_objetivo_h5", "")

    mapa, fechas_disp, _ = _mapa_precios_verificados(precios_filas)
    sesiones = _sesiones_entre(fecha_senal, f_obj)
    tray = []
    for i, s in enumerate(sesiones):
        p = mapa.get((emisora, s))
        if i == 0 and p is None and base is not None:
            p = base
        ret = round((p / base - 1.0) * 100.0, 4) if (p is not None and base and base > 0) else None
        est = "OBSERVADO" if p is not None else ("HUECO_DOCUMENTADO" if s in fechas_disp else "FUTURO")
        tray.append({"paso": f"t+{i}" if i else "t0", "fecha": s, "ppp": _num(p, 4), "retorno_pct": ret, "estado": est})

    modelos = []
    for r in corte_filas:
        resuelta = r["estado_resolucion"] == "RESUELTA_T+5"
        modelos.append({
            "generacion": r["generacion"], "modelo": r["modelo_g2"], "nombre": _nombre(r["modelo_g2"]),
            "probabilidad": round(r["probabilidad_subida"], 6),
            "prediccion": "SUBIDA" if r["prediccion_clase"] == 1 else "NO_SUBIDA",
            "acierto_parcial": r["acierto_parcial_en_curso"],
            "resuelta_t5": resuelta,
            "acierto_t5": (r["acierto_direccional_t5"] == 1) if (resuelta and r["acierto_direccional_t5"] is not None) else None,
        })
    parciales = [m["acierto_parcial"] for m in modelos if m["acierto_parcial"] is not None]
    return {
        "emisora": emisora, "fecha_senal": fecha_senal, "fechas": fechas[:30],
        "trayectoria": tray, "modelos": modelos,
        "resumen": {
            "estado": r0["estado_resolucion"],
            "fecha_objetivo": f_obj,
            "ppp_base": _num(base, 4),
            "retorno_parcial_pct": _num(r0["retorno_parcial_pct"], 4),
            "fecha_parcial": r0.get("fecha_parcial_reciente") or "",
            "modelos_acertando": sum(1 for x in parciales if x),
            "modelos_con_precio": len(parciales),
        },
        "modo_evaluacion_gold": True,
        "aviso_evaluacion": AVISO_EVALUACION,
    }


def marcador_modelos(s3, bucket: str, precios_filas: list[dict], permitidas: list[str]) -> dict:
    g2 = [r for r in _normalizar_g2(_leer_csv_s3(s3, bucket, KEY_GOLD_G2)) if r["emisora"] in permitidas]
    g1 = [r for r in _normalizar_g1(_leer_csv_s3(s3, bucket, KEY_GOLD_G1)) if r["emisora"] in permitidas and r["valida"]]
    enr, fecha_corte = _enriquecer_seguimiento(g2 + g1, precios_filas)
    grupos: dict[tuple[str, str], list[dict]] = {}
    for r in enr:
        grupos.setdefault((r["generacion"], r["modelo_g2"]), []).append(r)
    filas = []
    for (gen, mod), lista in sorted(grupos.items()):
        parciales = [r["acierto_parcial_en_curso"] for r in lista if r["acierto_parcial_en_curso"] is not None]
        resueltas = [r for r in lista if r["estado_resolucion"] == "RESUELTA_T+5"]
        aciertos_t5 = sum(1 for r in resueltas if r.get("acierto_direccional_t5") == 1)
        briers = [r["brier_observado_t5"] for r in resueltas if r.get("brier_observado_t5") is not None]
        filas.append({
            "generacion": gen, "id_modelo": mod, "modelo": _nombre(mod), "nombre": _nombre(mod),
            "senales": len(lista),
            "en_seguimiento": len(parciales),
            "aciertos_parciales": sum(1 for x in parciales if x),
            "tasa_parcial_pct": round(sum(1 for x in parciales if x) * 100.0 / len(parciales), 2) if parciales else None,
            "resueltas_t5": len(resueltas),
            "aciertos_t5": aciertos_t5,
            "brier_t5": round(sum(briers) / len(briers), 4) if briers else None,
        })
    return {
        "fecha_corte": fecha_corte,
        "emisoras": list(permitidas),
        "modelos": filas,
        "modo_evaluacion_gold": True,
        "aviso_evaluacion": AVISO_EVALUACION,
    }


def resumen_prismi_gold(s3, bucket: str, permitidas: list[str]) -> dict[str, str]:
    g2 = [r for r in _normalizar_g2(_leer_csv_s3(s3, bucket, KEY_GOLD_G2)) if r["emisora"] in permitidas]
    if not g2:
        return {}
    ult = max(r["fecha_senal"] for r in g2)
    out = {}
    for em in permitidas:
        sub = [r for r in g2 if r["emisora"] == em and r["fecha_senal"] == ult and r["modelo_g2"] in CONSENSO_G2_MODELOS]
        if not sub:
            continue
        cons = _consenso_clases([r["prediccion_clase"] for r in sub])
        probs = ", ".join(f"{_nombre(r['modelo_g2'])} {r['probabilidad_subida'] * 100:.1f}%" for r in sorted(sub, key=lambda x: x["modelo_g2"]))
        out[em] = (
            f"En el archivo histórico Gold (corte {ult}, objetivo {sub[0].get('fecha_objetivo_h5', '—')}), "
            f"{em} registra consenso {cons} ({probs})."
        )
    return out
