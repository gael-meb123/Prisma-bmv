"""
Prisma BMV - Composición de servicios para la interfaz (inyección de dependencias).

Los recursos se crean una sola vez por proceso (`st.cache_resource`) y los datos se
cachean 5 minutos (`st.cache_data`), suficiente para una fuente que cambia una vez al día.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from prisma.data import analytics as an
from prisma.data.repository import RepositorioDatos, crear_repositorio
from prisma.plans import EMISORAS_SENALES, RETRASO_BOLETIN_SESIONES
from prisma.security.crypto import AlmacenCifrado, obtener_fernet
from prisma.services.auth import ServicioUsuarios
from prisma.services.billing import PasarelaSandbox
from prisma.settings import Settings, get_settings


@dataclass
class Servicios:
    settings: Settings
    usuarios: ServicioUsuarios
    pasarela: PasarelaSandbox
    repo: RepositorioDatos


@st.cache_resource(show_spinner=False)
def servicios() -> Servicios:
    s = get_settings()
    fernet = obtener_fernet(s.llave_maestra, s.dir_estado, s.es_produccion)
    usuarios = ServicioUsuarios(AlmacenCifrado(s.dir_estado / "usuarios.enc", fernet), s.pbkdf2_iteraciones)
    if s.sembrar_demo:
        usuarios.sembrar_cuentas_demo()
    pasarela = PasarelaSandbox(AlmacenCifrado(s.dir_estado / "pagos.enc", fernet))
    return Servicios(s, usuarios, pasarela, crear_repositorio(s))


@st.cache_data(ttl=300, show_spinner="Leyendo el lakehouse…")
def datos(_repo: RepositorioDatos, fuente: str) -> dict[str, Any]:
    return {
        "precios": _repo.precios(),
        "g2": _repo.senales_g2(),
        "g1": _repo.senales_g1(),
        "modelos": _repo.modelos_g2(),
    }


@dataclass
class VistaPlan:
    """Lo que un plan puede ver de los datos: aplica el retraso del boletín y el universo de emisoras."""

    plan: str
    fechas: list[str]
    fecha_corte: str | None
    emisoras: tuple[str, ...]


def vista_para_plan(d: dict[str, Any], plan: str) -> VistaPlan:
    fechas = an.fechas_disponibles(d["precios"], RETRASO_BOLETIN_SESIONES.get(plan, 1))
    return VistaPlan(plan, fechas, fechas[0] if fechas else None, EMISORAS_SENALES.get(plan, ("WALMEX",)))


def recortar(df: pd.DataFrame, columna: str, corte: str | None) -> pd.DataFrame:
    if df.empty or corte is None:
        return df
    return df[df[columna].astype(str) <= corte]


def hoy_iso() -> str:
    return date.today().isoformat()
