"""
Prisma BMV - API REST Backend (FastAPI)
Conecta los insumos oficiales de Big Data e IA con la interfaz web en React.
Ejecución: uvicorn api:app --reload --port 8000

Autenticación: Supabase (JWT en 'Authorization: Bearer ...'). Ver core/supabase_auth.py.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.claude_bot import responder_con_claude
from core.data_provider import (
    cargar_monitoreo_en_vivo,
    cargar_senales_panel_g2,
    cargar_serie_walmex,
    obtener_fechas_mercado,
    obtener_kpis_mercado,
    obtener_metricas_institucionales_modelos,
)
from core.terminal_api import router as terminal_router
from core.supabase_auth import (
    Usuario,
    actualizar_usuario,
    crear_usuario,
    exigir_emisora,
    listar_usuarios,
    requiere_admin,
    usuario_actual,
)
from dotenv import load_dotenv
load_dotenv()
app = FastAPI(
    title="Prisma BMV - Quantitative API",
    description="API REST de grado institucional para la terminal cuantitativa Prisma BMV",
    version="3.0.0",
)

# Orígenes permitidos: CORS_ORIGINS="http://localhost:5173,https://tu-dominio.com"
_origenes = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origenes,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gráficas de la terminal web (sector, serie, señales, seguimiento, marcador, gobernanza).
app.include_router(terminal_router)


# ==============================================================================
# HEALTH CHECK
# ==============================================================================
@app.get("/health")
@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Endpoint de verificación de estado para monitores, Docker y proxies."""
    return {"status": "ok", "service": "prisma-bmv-api"}


# ==============================================================================
# MODELOS DE ENTRADA
# ==============================================================================
class ChatRequest(BaseModel):
    pregunta: str
    historial: list[dict[str, str]] | None = None


class NuevoUsuario(BaseModel):
    nombre: str
    email: str
    password: str
    rol: str = "user"
    plan: str = "explorer"


class CambioUsuario(BaseModel):
    rol: str | None = None
    plan: str | None = None
    nombre: str | None = None


# ==============================================================================
# SESIÓN
# ==============================================================================
@app.get("/api/me")
def me(u: Usuario = Depends(usuario_actual)) -> dict[str, Any]:
    """Perfil verificado: el frontend debe leer rol y plan de aquí."""
    return {"id": u.id, "email": u.email, "nombre": u.nombre, "rol": u.rol, "plan": u.plan, "emisoras": u.emisoras}


# ==============================================================================
# ADMINISTRACIÓN (solo rol admin)
# ==============================================================================
@app.get("/api/admin/usuarios")
def admin_listar(_: Usuario = Depends(requiere_admin)) -> list[dict[str, Any]]:
    return listar_usuarios()


@app.post("/api/admin/usuarios", status_code=201)
def admin_crear(req: NuevoUsuario, _: Usuario = Depends(requiere_admin)) -> dict[str, Any]:
    return crear_usuario(req.email.strip().lower(), req.password, req.nombre.strip(), req.rol, req.plan)


@app.patch("/api/admin/usuarios/{uid}")
def admin_actualizar(uid: str, req: CambioUsuario, admin: Usuario = Depends(requiere_admin)) -> dict[str, Any]:
    if uid == admin.id and req.rol and req.rol != "admin":
        raise HTTPException(status_code=400, detail="No puedes quitarte tu propio rol de administrador.")
    return actualizar_usuario(uid, rol=req.rol, plan=req.plan, nombre=req.nombre)


# ==============================================================================
# MÓDULO 1: MONITOR DE MERCADO (abierto: lo ve también quien aún no inicia sesión)
# ==============================================================================
@app.get("/api/mercado/fechas")
def get_fechas_mercado() -> list[str]:
    return obtener_fechas_mercado()


@app.get("/api/mercado/resumen")
def get_mercado_resumen(fecha: str | None = None) -> dict[str, Any]:
    fechas = obtener_fechas_mercado()
    if not fechas:
        raise HTTPException(status_code=404, detail="No hay datos de mercado disponibles.")

    fecha_target = fecha if fecha else fechas[0]
    kpis = obtener_kpis_mercado(fecha_target)

    df = cargar_monitoreo_en_vivo()
    sub = df[df["fecha"] == fecha_target].copy()

    registros = []
    for _, r in sub.iterrows():
        registros.append({
            "emisora": str(r.get("emisora", "")),
            "serie": str(r.get("serie", "")),
            "sector": str(r.get("sector_economico", "")),
            "ppp_bmv_mxn": float(r["ppp_bmv_mxn"]) if pd.notna(r.get("ppp_bmv_mxn")) else None,
            "anterior_bmv_mxn": float(r["anterior_bmv_mxn"]) if pd.notna(r.get("anterior_bmv_mxn")) else None,
            "variacion_pct": float(r["variacion_ppp_vs_anterior_pct"]) if pd.notna(r.get("variacion_ppp_vs_anterior_pct")) else None,
            "estado_captura": str(r.get("estado_captura", "")),
        })

    return {"fecha": fecha_target, "kpis": kpis, "cotizaciones": registros}


# ==============================================================================
# MÓDULO 2: SEÑALES Y CONSENSO IA (requiere sesión; filtra por plan)
# ==============================================================================
@app.get("/api/senales/panel")
def get_senales_panel(
    fecha: str | None = None,
    emisora: str | None = None,
    u: Usuario = Depends(usuario_actual),
) -> dict[str, Any]:
    # Emisora pedida explícitamente y fuera del plan -> 403.
    if emisora:
        exigir_emisora(u, emisora)

    df_g2 = cargar_senales_panel_g2()
    if df_g2.empty:
        return {"fecha": fecha, "emisora": emisora, "senales": []}

    # Sin emisora: solo se devuelve lo que el plan incluye (Explorer = WALMEX).
    df_g2 = df_g2[df_g2["emisora"].isin(u.emisoras)]
    if fecha:
        df_g2 = df_g2[df_g2["fecha_senal"] == fecha]
    if emisora:
        df_g2 = df_g2[df_g2["emisora"] == emisora]

    registros = []
    for _, r in df_g2.iterrows():
        registros.append({
            "id_senal_g2": str(r.get("id_senal_g2", "")),
            "fecha_senal": str(r.get("fecha_senal", "")),
            "muestra_evaluacion": str(r.get("muestra_evaluacion", "IN_SAMPLE_DISENO")),
            "fecha_objetivo_h5": str(r.get("fecha_objetivo_h5", "")),
            "emisora": str(r.get("emisora", "")),
            "sector": str(r.get("sector_economico", "")),
            "modelo_g2": str(r.get("modelo_g2", "")),
            "ppp_base_t": float(r["ppp_base_t"]) if pd.notna(r.get("ppp_base_t")) else 0.0,
            "ret_10": float(r["ret_10"]) if pd.notna(r.get("ret_10")) else 0.0,
            "ret_10_rel_panel": float(r["ret_10_rel_panel"]) if pd.notna(r.get("ret_10_rel_panel")) else 0.0,
            "volatilidad_20": float(r["volatilidad_20"]) if pd.notna(r.get("volatilidad_20")) else 0.0,
            "probabilidad_subida": float(r["probabilidad_subida"]) if pd.notna(r.get("probabilidad_subida")) else 0.5,
            "prediccion_etiqueta": str(r.get("prediccion_etiqueta", "")),
            "estado_consenso_g2": str(r.get("estado_consenso_g2", "")),
            "estado_resolucion": str(r.get("estado_resolucion", "")),
            "sesiones_transcurridas": int(r["sesiones_transcurridas"]) if pd.notna(r.get("sesiones_transcurridas")) else 0,
            "retorno_parcial_pct": float(r["retorno_parcial_pct"]) if pd.notna(r.get("retorno_parcial_pct")) else None,
            "acierto_parcial_en_curso": bool(r["acierto_parcial_en_curso"]) if pd.notna(r.get("acierto_parcial_en_curso")) and str(r.get("acierto_parcial_en_curso")).lower() in ("true", "1", "false", "0") else None,
        })

    return {"senales": registros}


# ==============================================================================
# MÓDULO 2B: MÉTRICAS INSTITUCIONALES Y ASIGNACIÓN DE CAPITAL (abierto para dashboard)
# ==============================================================================
@app.get("/api/metricas/modelos")
def get_metricas_modelos() -> dict[str, Any]:
    """
    Expone las métricas institucionales de calidad (BSS, Rank IC, ECE, lambda_Cox,
    intervalos Wilson 95%, N_eff y diagrama de confiabilidad), la separación de
    muestra prospectiva (IN_SAMPLE_DISENO vs OUT_OF_SAMPLE_PRE_REGISTRADO) y la
    política de asignación de capital ¼-Kelly (Fase 5).
    """
    return obtener_metricas_institucionales_modelos()


# ==============================================================================
# MÓDULO 3: AUDITORÍA TEMPORAL Y SERIE (requiere sesión; WALMEX está en todos los planes)
# ==============================================================================
@app.get("/api/serie/walmex")
def get_serie_walmex(u: Usuario = Depends(usuario_actual)) -> list[dict[str, Any]]:
    exigir_emisora(u, "WALMEX")
    df = cargar_serie_walmex()
    if df.empty:
        return []
    registros = []
    for _, r in df.iterrows():
        registros.append({
            "fecha": str(r.get("fecha", "")),
            "ppp": float(r["ppp_bmv_mxn"]) if pd.notna(r.get("ppp_bmv_mxn")) else None,
            "estado": str(r.get("estado", "")),
        })
    return registros


# ==============================================================================
# ASISTENTE PRISMI (Claude API) - requiere sesión (cuota diaria: pendiente)
# ==============================================================================
@app.post("/api/chat/prismi")
def chat_prismi(req: ChatRequest, u: Usuario = Depends(usuario_actual)) -> dict[str, str]:
    respuesta = responder_con_claude(req.pregunta, historial=req.historial)
    return {"respuesta": respuesta}
