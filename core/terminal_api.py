"""
Prisma BMV - Endpoints de la terminal web (/api/terminal/...).

Sirven las gráficas que antes solo existían en la terminal Streamlit: variación por sector,
serie PPP de cualquier emisora (con huecos), probabilidades por modelo, descomposición del
factor clave, trayectoria t0 → t+5, efectividad por modelo, marcador y gobernanza AWS.

Toda la lógica cuantitativa viene de `prisma.data.analytics` (la misma que usa la Lambda y
la terminal Streamlit), leída sobre los CSV vivos de la raíz del repositorio. Las reglas de
plan son las de `core.supabase_auth` (fuente de verdad del backend).
"""

from __future__ import annotations

import math
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.supabase_auth import Usuario, exigir_emisora, usuario_actual
from prisma.data import analytics as an
from prisma.data.repository import RepositorioLocal
from prisma.services import prismi as motor_prismi
from prisma.settings import get_settings

RAIZ = Path(__file__).resolve().parent.parent
router = APIRouter(prefix="/api/terminal", tags=["terminal"])

# ------------------------------------------------------------------------------
# Datos: caché corta (la ingesta diaria reescribe los CSV; 60 s es suficiente)
# ------------------------------------------------------------------------------
_TTL = 60.0
_lock = threading.Lock()
_cache: dict[str, Any] = {"t": 0.0, "datos": None}


def _datos() -> dict[str, Any]:
    with _lock:
        if _cache["datos"] is None or time.monotonic() - _cache["t"] > _TTL:
            repo = RepositorioLocal(RAIZ, archivo_modelos=RAIZ / "registro_modelos_g2_oficial.json")
            _cache["datos"] = {
                "precios": repo.precios(),
                "g2": repo.senales_g2(),
                "g1": repo.senales_g1(),
                "modelos": repo.modelos_g2(),
            }
            _cache["t"] = time.monotonic()
        return _cache["datos"]


def _num(v: Any, nd: int | None = None) -> float | None:
    """NaN / None → None (JSON válido, sin imputar); redondeo opcional."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, nd) if nd is not None else f


def _bool(v: Any) -> bool | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, str):
        return {"true": True, "1": True, "false": False, "0": False}.get(v.strip().lower())
    return bool(v)


def _fecha_corte(precios: pd.DataFrame, fecha: str | None) -> str:
    fechas = an.fechas_disponibles(precios)
    if not fechas:
        raise HTTPException(status_code=404, detail="No hay sesiones disponibles.")
    if fecha and fecha in fechas:
        return fecha
    return fechas[0]


def _nombre(modelo: str) -> str:
    return an.NOMBRES_MODELO.get(modelo, modelo)


# ------------------------------------------------------------------------------
# Mercado (público, como /api/mercado/*)
# ------------------------------------------------------------------------------
@router.get("/sectores")
def sectores(fecha: str | None = None) -> dict[str, Any]:
    """Variación media del PPP por sector en la sesión (solo emisoras con PPP verificado)."""
    d = _datos()
    corte = _fecha_corte(d["precios"], fecha)
    sesion = d["precios"][d["precios"]["fecha"] == corte]
    tabla = an.kpis_por_sector(sesion)
    filas = [{
        "sector": str(r["sector_economico"]),
        "emisoras": int(r["emisoras"]),
        "con_ppp": int(r["con_ppp"]),
        "huecos": int(r["huecos"]),
        "variacion_media_pct": _num(r["variacion_media_pct"], 2),
    } for _, r in tabla.iterrows()]
    return {"fecha": corte, "kpis": an.kpis_sesion(sesion), "sectores": filas}


@router.get("/gobernanza")
def gobernanza() -> dict[str, Any]:
    """Flujo del lakehouse en AWS (nodos y enlaces para el diagrama Sankey)."""
    nodos = [
        ("EventBridge Scheduler", "DisparadorDiarioBMV · cron(45 16 ? * MON-FRI *) · America/Mexico_City"),
        ("Lambda recolector-diario-bmv", "Python 3.11, 512 MB, 60 s · fuera de VPC · Layer AWSSDKPandas"),
        ("Boletín BMV (RSS)", "HTML oficial del día"),
        ("S3 Bronze", "bronze/boletin_YYYYMMDD.html + .sha256 · inmutable"),
        ("S3 Silver", "silver/precios_ppp/YYYY/MM/ · 15 emisoras, cero imputación"),
        ("S3 Gold", "gold/senales_g1/ y senales_g2/ · probabilidades y consensos"),
        ("Amazon Athena", "bmv_silver_ppp, bmv_gold_senales_g2"),
        ("Terminal Prisma BMV", "Esta aplicación web"),
        ("CloudWatch Logs", "/aws/lambda/recolector-diario-bmv · retención 7 días"),
        ("IAM LabRole", "Lectura/escritura en el bucket y consulta en Athena"),
    ]
    enlaces = [(0, 1, 3), (2, 1, 3), (1, 3, 3), (3, 4, 3), (4, 5, 2), (4, 6, 2), (5, 6, 2),
               (6, 7, 2), (4, 7, 1), (1, 8, 1), (9, 1, 1)]
    return {
        "nodos": [{"nombre": n, "detalle": det} for n, det in nodos],
        "enlaces": [{"origen": a, "destino": b, "valor": v} for a, b, v in enlaces],
    }


# ------------------------------------------------------------------------------
# Serie, señales y seguimiento (requieren sesión y respetan el plan)
# ------------------------------------------------------------------------------
@router.get("/serie")
def serie(emisora: str, u: Usuario = Depends(usuario_actual)) -> dict[str, Any]:
    """PPP oficial sesión por sesión. Las sesiones sin PPP verificado van con ppp=null (no se rellenan)."""
    exigir_emisora(u, emisora)
    p = _datos()["precios"]
    sub = p[p["emisora"] == emisora].sort_values("fecha")
    if sub.empty:
        raise HTTPException(status_code=404, detail=f"Sin serie para {emisora}.")
    puntos = []
    for _, r in sub.iterrows():
        verificado = r.get("estado_captura") == "PPP_PUBLICADO_VERIFICADO"
        puntos.append({
            "fecha": str(r["fecha"]),
            "ppp": _num(r.get("ppp_bmv_mxn"), 4) if verificado else None,
            "estado": str(r.get("estado_captura", "")),
        })
    ultima = sub.iloc[-1]
    return {"emisora": emisora, "sector": str(ultima.get("sector_economico", "")), "serie": str(ultima.get("serie", "")),
            "puntos": puntos}


@router.get("/senal")
def senal(emisora: str, fecha: str | None = None, u: Usuario = Depends(usuario_actual)) -> dict[str, Any]:
    """Probabilidad por modelo, consenso por generación y descomposición del factor clave."""
    exigir_emisora(u, emisora)
    d = _datos()
    g2 = d["g2"][d["g2"]["emisora"] == emisora]
    g1 = d["g1"] if emisora == "WALMEX" else d["g1"].iloc[0:0]
    fechas = sorted(set(g2["fecha_senal"]) | (set(g1["fecha_senal"]) if not g1.empty else set()), reverse=True)
    if not fechas:
        return {"emisora": emisora, "fecha": None, "fechas": [], "modelos": [], "consensos": {}, "factor": None}
    f = fecha if fecha in fechas else next((x for x in fechas if not fecha or x <= fecha), fechas[0])

    tabla = an.tabla_probabilidades(g1, g2, emisora, f, True, False)
    modelos = [{
        "generacion": str(r["generacion"]),
        "modelo": str(r["modelo"]),
        "nombre": _nombre(str(r["modelo"])),
        "probabilidad": _num(r["probabilidad"], 6),
        "clase": int(r["clase"]),
        "valida": bool(r["valida"]),
    } for _, r in tabla.iterrows()]

    factor = None
    filas = g2[g2["fecha_senal"] == f]
    if not filas.empty:
        # Se descompone el primer modelo con parámetros publicables (V1 → V2 → V3).
        explicaciones = []
        for _, fila in filas.sort_values("modelo_g2").iterrows():
            e = an.explicar_factor(d["modelos"], fila)
            explicaciones.append((fila, e))
        fila, e = next(((fi, ex) for fi, ex in explicaciones if ex.contribuciones), explicaciones[0])
        contrib = {k: _num(v, 6) for k, v in e.contribuciones.items()}
        total = sum(v for v in contrib.values() if v is not None) if contrib else None
        factor = {
            "modelo": str(fila["modelo_g2"]),
            "nombre": _nombre(str(fila["modelo_g2"])),
            "ret_rel_pp": _num(e.ret_rel_pct, 4),
            "z_rel": _num(e.z_rel, 4),
            "contribuciones": contrib,
            "log_odds_total": _num(total, 6),
            "probabilidad_reconstruida": _num(1 / (1 + math.exp(-total)), 6) if total is not None else None,
            "lectura": e.lectura,
            "ppp_base": _num(fila.get("ppp_base_t"), 4),
        }
    return {
        "emisora": emisora,
        "fecha": f,
        "fechas": fechas[:30],
        "modelos": modelos,
        "consensos": an.consenso_por_generacion(tabla),
        "factor": factor,
    }


@router.get("/seguimiento")
def seguimiento(emisora: str, fecha_senal: str | None = None, u: Usuario = Depends(usuario_actual)) -> dict[str, Any]:
    """Trayectoria t0 → t+5 de una señal y cómo va cada modelo (sin interpolar huecos)."""
    exigir_emisora(u, emisora)
    d = _datos()
    corte = _fecha_corte(d["precios"], None)
    seg = an.seguimiento(d["g1"], d["g2"], d["precios"], corte)
    sub = seg[seg["emisora"] == emisora] if not seg.empty else seg
    if sub.empty:
        return {"emisora": emisora, "fecha_senal": None, "fechas": [], "trayectoria": [], "modelos": [], "resumen": None}

    fechas = sorted(sub["fecha_senal"].unique(), reverse=True)
    if fecha_senal not in fechas:
        con_precio = set(sub.loc[sub["acierto_parcial_en_curso"].notna(), "fecha_senal"])
        fecha_senal = next((f for f in fechas if f in con_precio), fechas[0])
    corte_df = sub[sub["fecha_senal"] == fecha_senal]
    r0 = corte_df.iloc[0]
    base = float(r0["ppp_base_t"])
    tray = an.trayectoria(d["precios"], emisora, fecha_senal, str(r0["fecha_objetivo_h5"]), base)

    modelos = []
    for _, r in corte_df.sort_values(["generacion", "modelo_g2"]).iterrows():
        resuelta = r["estado_resolucion"] == "RESUELTA_T+5"
        modelos.append({
            "generacion": str(r["generacion"]),
            "modelo": str(r["modelo_g2"]),
            "nombre": _nombre(str(r["modelo_g2"])),
            "probabilidad": _num(r["probabilidad_subida"], 6),
            "prediccion": "SUBIDA" if int(r["prediccion_clase"]) == 1 else "NO_SUBIDA",
            "acierto_parcial": _bool(r.get("acierto_parcial_en_curso")),
            "resuelta_t5": bool(resuelta),
            "acierto_t5": (int(r["acierto_direccional_t5"]) == 1) if resuelta and pd.notna(r.get("acierto_direccional_t5")) else None,
        })
    parciales = [m["acierto_parcial"] for m in modelos if m["acierto_parcial"] is not None]
    return {
        "emisora": emisora,
        "fecha_senal": fecha_senal,
        "fechas": fechas[:30],
        "trayectoria": [{
            "paso": str(t["paso"]), "fecha": str(t["fecha"]), "ppp": _num(t["ppp"], 4),
            "retorno_pct": _num(t["retorno_pct"], 4), "estado": str(t["estado"]),
        } for _, t in tray.iterrows()],
        "modelos": modelos,
        "resumen": {
            "estado": str(r0["estado_resolucion"]),
            "fecha_objetivo": str(r0["fecha_objetivo_h5"]),
            "ppp_base": _num(base, 4),
            "retorno_parcial_pct": _num(r0.get("retorno_parcial_pct"), 4),
            "fecha_parcial": str(r0.get("fecha_parcial_reciente") or ""),
            "modelos_acertando": sum(1 for x in parciales if x),
            "modelos_con_precio": len(parciales),
        },
    }


@router.get("/marcador")
def marcador(u: Usuario = Depends(usuario_actual)) -> dict[str, Any]:
    """Aciertos parciales y en t+5 por modelo, sobre las emisoras que incluye el plan."""
    d = _datos()
    corte = _fecha_corte(d["precios"], None)
    seg = an.seguimiento(d["g1"], d["g2"], d["precios"], corte)
    if not seg.empty:
        seg = seg[seg["emisora"].isin(u.emisoras)]
    tabla = an.marcador_modelos(seg) if not seg.empty else pd.DataFrame()
    filas = [{
        "generacion": str(r["generacion"]),
        "modelo": str(r["modelo"]),
        "nombre": _nombre(str(r["modelo"])),
        "senales": int(r["senales"]),
        "en_seguimiento": int(r["en_seguimiento"]),
        "aciertos_parciales": int(r["aciertos_parciales"]),
        "tasa_parcial_pct": _num(r["tasa_parcial_pct"], 2),
        "resueltas_t5": int(r["resueltas_t5"]),
        "aciertos_t5": int(r["aciertos_t5"]),
        "brier_t5": _num(r["brier_t5"], 4),
    } for _, r in tabla.iterrows()]
    return {"fecha_corte": corte, "emisoras": u.emisoras, "modelos": filas}


# ------------------------------------------------------------------------------
# Prismi: el mismo motor de la terminal Streamlit (guardrails + contexto real),
# con la gráfica que el usuario está viendo como contexto adicional.
# ------------------------------------------------------------------------------

_CUOTA_EXPLORER = 5
_cuotas: dict[tuple[str, str], int] = {}


class PreguntaPrismi(BaseModel):
    pregunta: str = Field(max_length=1500)
    historial: list[dict[str, str]] = Field(default_factory=list)
    contexto_grafica: str | None = Field(default=None, max_length=4000)


def _consumir_cuota(u: Usuario) -> bool:
    """Explorer: 5 consultas a Claude al día (memoria del proceso; una réplica). Planes de pago: sin límite."""
    if u.plan != "explorer":
        return True
    clave = (u.id, date.today().isoformat())
    usadas = _cuotas.get(clave, 0)
    if usadas >= _CUOTA_EXPLORER:
        return False
    _cuotas[clave] = usadas + 1
    return True


@router.post("/prismi")
def prismi(req: PreguntaPrismi, u: Usuario = Depends(usuario_actual)) -> dict[str, Any]:
    d = _datos()
    corte = _fecha_corte(d["precios"], None)
    g2 = d["g2"][d["g2"]["emisora"].isin(u.emisoras)]
    seg = an.seguimiento(d["g1"], g2, d["precios"], corte)
    contexto = motor_prismi.construir_contexto(d["precios"], d["g1"], g2, seg, tuple(u.emisoras))
    if req.contexto_grafica:
        contexto = motor_prismi.ContextoMercado(
            texto=f"{contexto.texto}\n\nGRÁFICA QUE EL USUARIO ESTÁ VIENDO EN LA TERMINAL:\n{req.contexto_grafica}",
            por_emisora=contexto.por_emisora,
        )
    s = get_settings()
    usar_claude = bool(s.anthropic_api_key) and _consumir_cuota(u)
    r = motor_prismi.responder(req.pregunta, req.historial, contexto, u.plan, s.anthropic_api_key,
                               s.prismi_modelo, usar_claude)
    return {"respuesta": r.texto, "origen": r.origen}
