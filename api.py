"""
Prisma BMV - API REST Backend (FastAPI)
Conecta los insumos oficiales de Big Data e IA con la interfaz web en React.
Ejecución: uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import json
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.auth import autenticar_usuario, registrar_usuario
from core.claude_bot import responder_con_claude
from core.data_provider import (
    cargar_monitoreo_en_vivo,
    cargar_senales_panel_g2,
    cargar_senales_walmex,
    cargar_serie_walmex,
    obtener_fechas_mercado,
    obtener_kpis_mercado,
)

app = FastAPI(
    title="Prisma BMV - Quantitative API",
    description="API REST de grado institucional para la terminal cuantitativa Prisma BMV",
    version="2.0.0",
)

# Permitir CORS para desarrollo con Vite / React (localhost:5173 y producción)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# MODELOS DE ENTRADA
# ==============================================================================
class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    nombre: str
    email: str
    password: str
    plan: str = "professional"


class ChatRequest(BaseModel):
    pregunta: str
    historial: list[dict[str, str]] | None = None


# ==============================================================================
# ENDPOINTS DE AUTENTICACIÓN
# ==============================================================================
@app.post("/api/auth/login")
def login(req: LoginRequest) -> dict[str, Any]:
    ok, user_info, msg = autenticar_usuario(req.email, req.password)
    if not ok:
        raise HTTPException(status_code=401, detail=msg)
    return {"status": "success", "user": user_info, "message": msg}


@app.post("/api/auth/register")
def register(req: RegisterRequest) -> dict[str, Any]:
    ok, msg = registrar_usuario(req.nombre, req.email, req.password, req.plan)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}


# ==============================================================================
# ENDPOINTS MÓDULO 1: MONITOR DE MERCADO (DEV 1)
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
        
    return {
        "fecha": fecha_target,
        "kpis": kpis,
        "cotizaciones": registros
    }


# ==============================================================================
# ENDPOINTS MÓDULO 2: SEÑALES Y CONSENSO IA (DEV 2)
# ==============================================================================
@app.get("/api/senales/panel")
def get_senales_panel(fecha: str | None = None, emisora: str | None = None) -> dict[str, Any]:
    df_g2 = cargar_senales_panel_g2()
    if df_g2.empty:
        return {"fecha": fecha, "emisora": emisora, "senales": []}
        
    if fecha:
        df_g2 = df_g2[df_g2["fecha_senal"] == fecha]
    if emisora:
        df_g2 = df_g2[df_g2["emisora"] == emisora]
        
    registros = []
    for _, r in df_g2.iterrows():
        registros.append({
            "id_senal_g2": str(r.get("id_senal_g2", "")),
            "fecha_senal": str(r.get("fecha_senal", "")),
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
        })
        
    return {"senales": registros}


# ==============================================================================
# ENDPOINTS MÓDULO 3: AUDITORÍA TEMPORAL Y SERIE (DEV 3)
# ==============================================================================
@app.get("/api/serie/walmex")
def get_serie_walmex() -> list[dict[str, Any]]:
    df = cargar_serie_walmex()
    if df.empty:
        return []
    registros = []
    for _, r in df.iterrows():
        registros.append({
            "fecha": str(r.get("fecha", "")),
            "ppp": float(r["ppp_oficial_bmv"]) if pd.notna(r.get("ppp_oficial_bmv")) else None,
            "estado": str(r.get("estado", ""))
        })
    return registros


# ==============================================================================
# ENDPOINT MASCOTA / ASISTENTE PRISMI (CLAUDE API)
# ==============================================================================
@app.post("/api/chat/prismi")
def chat_prismi(req: ChatRequest) -> dict[str, str]:
    respuesta = responder_con_claude(req.pregunta, historial=req.historial)
    return {"respuesta": respuesta}
