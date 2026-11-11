"""
Prisma BMV - Quantitative Terminal
Orquestador de la aplicación Streamlit.

Ejecución:  streamlit run app.py
Configuración: variables de entorno o .streamlit/secrets.toml (ver .env.example).
"""

from __future__ import annotations

import os

import streamlit as st

st.set_page_config(page_title="Prisma BMV - Quantitative Terminal", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")


def _secretos_a_entorno() -> None:
    """Copia st.secrets al entorno para que la configuración sea idéntica en local y en la nube."""
    try:
        for k, v in st.secrets.items():
            if isinstance(v, (str, int, float, bool)) and k not in os.environ:
                os.environ[k] = str(v)
    except Exception:
        pass  # sin secrets.toml: se usan solo variables de entorno


_secretos_a_entorno()

from prisma.data.analytics import seguimiento  # noqa: E402
from prisma.plans import tiene_acceso  # noqa: E402
from prisma.security.crypto import ErrorConfiguracionSeguridad  # noqa: E402
from prisma.services import prismi as motor_prismi  # noqa: E402
from prisma.ui import components as ui  # noqa: E402
from prisma.ui.contexto import datos as cargar_datos  # noqa: E402
from prisma.ui.contexto import recortar, servicios, vista_para_plan  # noqa: E402
from prisma.ui.theme import CSS  # noqa: E402
from prisma.ui.views import account, audit, landing, lakehouse, market, signals  # noqa: E402
from prisma.ui.views import prismi as widget_prismi  # noqa: E402

ui.html(CSS)


def _estado_inicial() -> None:
    for k, v in {"usuario_email": None, "vista": "terminal", "tour_abierto": False,
                 "tour_tipo": "visitante", "tour_paso": 0, "tour_visto": False}.items():
        st.session_state.setdefault(k, v)


def _contexto_prismi(d: dict, vp) -> motor_prismi.ContextoMercado:
    g1 = recortar(d["g1"], "fecha_senal", vp.fecha_corte)
    g2 = recortar(d["g2"], "fecha_senal", vp.fecha_corte) if tiene_acceso(vp.plan, "panel_g2") else d["g2"].iloc[0:0]
    precios = recortar(d["precios"], "fecha", vp.fecha_corte)
    seg = seguimiento(g1, g2, precios, vp.fecha_corte) if vp.fecha_corte else g2
    return motor_prismi.construir_contexto(precios, g1, g2, seg, vp.emisoras)


def _barra_superior(sv, usuario: dict) -> None:
    izq, der = st.columns([3, 1.2])
    with izq:
        ui.html(f'<div class="pb-barra"><div class="pb-marca">PRISMA BMV<small>Quantitative Terminal</small></div>'
                f'<div class="pb-usuario"><b>{ui.escape(usuario["nombre"])}</b>{ui.etiqueta_plan(usuario["plan"])}'
                f'<span class="tenue" style="margin-left:.8rem">fuente: {ui.escape(sv.repo.nombre_fuente)}</span>'
                f'</div></div>')
    with der:
        if st.button("Cerrar sesión", key="logout", width="stretch"):
            for k in ("usuario_email", "prismi_msgs", "checkout_plan"):
                st.session_state.pop(k, None)
            st.rerun()


def main() -> None:
    _estado_inicial()
    try:
        sv = servicios()
    except ErrorConfiguracionSeguridad as e:
        st.error(str(e))
        st.stop()

    try:
        d = cargar_datos(sv.repo, sv.settings.fuente_datos)
    except Exception as e:  # credenciales de AWS vencidas, bucket inexistente, etc.
        st.error(f"No se pudieron leer los datos de {sv.repo.nombre_fuente}: {e}")
        st.stop()

    email = st.session_state["usuario_email"]
    usuario = sv.usuarios.obtener(email) if email else None
    if email and usuario is None:
        st.session_state["usuario_email"] = None

    # Primera visita de un visitante: el recorrido se abre una vez por sesión.
    if usuario is None and not st.session_state["tour_visto"]:
        st.session_state.update(tour_visto=True, tour_abierto=True, tour_tipo="visitante", tour_paso=0)

    vp = vista_para_plan(d, usuario["plan"] if usuario else "explorer")

    if usuario is None:
        landing.render(sv, d)
    elif st.session_state["vista"] == "checkout":
        account.checkout(sv, usuario)
    else:
        _barra_superior(sv, usuario)
        if vp.fecha_corte:
            ui.cinta_cotizaciones(d["precios"][d["precios"]["fecha"] == vp.fecha_corte])
        t_mk, t_sg, t_au, t_lk, t_ac = st.tabs(
            ["Monitor de mercado", "Señales y consenso", "Auditoría t+1 a t+5", "Lakehouse", "Cuenta"])
        with t_mk:
            market.render(d, vp)
        with t_sg:
            signals.render(d, vp)
        with t_au:
            audit.render(d, vp, sv.settings)
        with t_lk:
            lakehouse.render(sv, d, vp)
        with t_ac:
            account.cuenta(sv, usuario)

    widget_prismi.render(sv, usuario, _contexto_prismi(d, vp))

    if st.session_state["tour_abierto"]:
        st.session_state["tour_abierto"] = False
        account.recorrido(sv, usuario)


main()
