"""Prisma BMV - Componentes visuales reutilizables (HTML escapado, sin cifras fijas)."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from prisma.data.analytics import DIVERGENCIA, NO_SUBIDA, SUBIDA
from prisma.domain import bmv_core as core
from prisma.plans import PLANES, plan_minimo


def html(bloque: str) -> None:
    st.markdown(bloque, unsafe_allow_html=True)


def seccion(titulo: str, nota: str = "") -> None:
    html(f'<div class="pb-seccion"><h3>{escape(titulo)}</h3><span>{escape(nota)}</span></div>')


def kpi(etiqueta: str, valor: str, sub: str = "", tono: str = "") -> None:
    html(
        f'<div class="pb-panel"><div class="pb-kpi-l">{escape(etiqueta)}</div>'
        f'<div class="pb-kpi-v {tono}">{escape(valor)}</div>'
        f'<div class="pb-kpi-s {tono}">{escape(sub)}</div></div>'
    )


def fmt_pct(v: float | None, dec: int = 2) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:+.{dec}f}%"


def tono(v: float | None) -> str:
    if v is None or pd.isna(v) or v == 0:
        return "tenue"
    return "sube" if v > 0 else "baja"


def cinta_cotizaciones(sesion: pd.DataFrame) -> None:
    """Cinta con el PPP de la sesión visible. Los huecos se muestran como tales."""
    if sesion.empty:
        return
    items = []
    for _, r in sesion.sort_values("emisora").iterrows():
        if r["estado_captura"] == core.ESTADO_PUBLICADO and pd.notna(r["ppp_bmv_mxn"]):
            v = r["variacion_ppp_vs_anterior_pct"]
            items.append(
                f'<span class="it"><span class="tk">{escape(r["emisora"])}</span>{r["ppp_bmv_mxn"]:,.2f} '
                f'<span class="{tono(v)}">{fmt_pct(v)}</span></span>'
            )
        else:
            items.append(f'<span class="it"><span class="tk">{escape(r["emisora"])}</span>'
                         f'<span class="alerta">sin PPP en boletín</span></span>')
    fecha = escape(str(sesion["fecha"].iloc[0]))
    pista = "".join(items)
    html(f'<div class="pb-cinta" aria-label="PPP oficial BMV del {fecha}">'
         f'<div class="pb-cinta-pista"><span class="it tenue">PPP BMV {fecha}</span>{pista}</div></div>')


def semaforo(etiqueta_canonica: str, titulo: str) -> None:
    luces = {
        SUBIDA: ("on-sube", "", ""),
        DIVERGENCIA: ("", "on-alerta", ""),
        NO_SUBIDA: ("", "", "on-baja"),
    }.get(etiqueta_canonica, ("", "", ""))
    tono_txt = {SUBIDA: "sube", NO_SUBIDA: "baja", DIVERGENCIA: "alerta"}.get(etiqueta_canonica, "tenue")
    html(
        f'<div class="pb-panel"><div class="pb-kpi-l">{escape(titulo)}</div>'
        f'<div class="pb-semaforo"><span class="pb-luz {luces[0]}"></span><span class="pb-luz {luces[1]}"></span>'
        f'<span class="pb-luz {luces[2]}"></span><span class="pb-etq {tono_txt}">{escape(etiqueta_canonica)}</span></div></div>'
    )


def chip(texto: str, clase: str) -> str:
    return f'<span class="pb-chip {clase}">{escape(texto)}</span>'


def bloqueo(derecho: str, descripcion: str, clave: str) -> None:
    """Tarjeta de función bloqueada con acceso directo al checkout del plan necesario."""
    plan = plan_minimo(derecho)
    html(
        f'<div class="pb-bloqueo"><h4>Disponible en {escape(plan.nombre)}</h4>'
        f'<p>{escape(descripcion)}</p></div>'
    )
    if st.button(f"Activar {plan.nombre} por ${plan.precio_usd_mes} USD/mes", key=f"up_{clave}", type="primary"):
        st.session_state["checkout_plan"] = plan.id
        st.session_state["vista"] = "checkout"
        st.rerun()


def etiqueta_plan(plan_id: str) -> str:
    p = PLANES.get(plan_id, PLANES["explorer"])
    return f'<span class="pb-plan" style="color:{p.color}">{escape(p.nombre)}</span>'
