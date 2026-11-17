"""Portada pública: propuesta de valor con datos reales, planes, acceso y registro."""

from __future__ import annotations

from html import escape

import streamlit as st

from prisma.data import analytics as an
from prisma.plans import ORDEN_PLANES, PLANES, PROFESSIONAL
from prisma.services.auth import CUENTAS_DEMO, PASSWORD_DEMO
from prisma.ui import components as ui
from prisma.ui.contexto import Servicios


def _iniciar_sesion(sv: Servicios, usuario: dict) -> None:
    st.session_state["usuario_email"] = usuario["email"]
    st.session_state["vista"] = "terminal"
    if not usuario.get("tour_completado"):
        st.session_state["tour_abierto"] = True
        st.session_state["tour_tipo"] = "terminal"
        st.session_state["tour_paso"] = 0


def formulario_acceso(sv: Servicios) -> None:
    acceso, registro = st.tabs(["Iniciar sesión", "Crear cuenta"])
    with acceso:
        with st.form("f_login"):
            email = st.text_input("Correo")
            pwd = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar a la terminal", type="primary"):
                ok, u, msg = sv.usuarios.autenticar(email, pwd)
                if ok:
                    _iniciar_sesion(sv, u)
                    st.rerun()
                st.error(msg)
        if sv.settings.sembrar_demo:
            st.caption("Cuentas de demostración (contraseña " + PASSWORD_DEMO + "): " +
                       ", ".join(CUENTAS_DEMO))
    with registro:
        with st.form("f_registro"):
            nombre = st.text_input("Nombre o institución")
            email = st.text_input("Correo profesional")
            pwd = st.text_input("Contraseña", type="password", help="Mínimo 10 caracteres, con letras y números.")
            plan = st.radio("Plan", ORDEN_PLANES, horizontal=True,
                            index=ORDEN_PLANES.index(st.session_state.get("plan_elegido", "explorer")),
                            format_func=lambda p: f"{PLANES[p].nombre} (${PLANES[p].precio_usd_mes})")
            acepto = st.checkbox("Entiendo que las señales son probabilidades estadísticas y no asesoría de inversión.")
            if st.form_submit_button("Crear cuenta", type="primary"):
                if not acepto:
                    st.error("Confirme el aviso para continuar.")
                else:
                    ok, msg = sv.usuarios.registrar(nombre, email, pwd)
                    if not ok:
                        st.error(msg)
                    else:
                        _, u, _ = sv.usuarios.autenticar(email, pwd)
                        _iniciar_sesion(sv, u)
                        if PLANES[plan].precio_usd_mes > 0:
                            st.session_state["checkout_plan"] = plan
                            st.session_state["vista"] = "checkout"
                        st.rerun()


def render(sv: Servicios, datos: dict) -> None:
    precios = datos["precios"]
    fechas = an.fechas_disponibles(precios, 1)  # la portada pública también va diferida
    izq, der = st.columns([3, 1])
    with izq:
        ui.html('<div class="pb-barra"><div class="pb-marca">PRISMA BMV<small>Quantitative Terminal</small></div></div>')
    with der:
        if st.button("Ver el recorrido", key="ld_tour", width="stretch"):
            st.session_state.update(tour_abierto=True, tour_tipo="visitante", tour_paso=0)
            st.rerun()
    if fechas:
        ui.cinta_cotizaciones(precios[precios["fecha"] == fechas[0]])

    hero, acceso = st.columns([1.55, 1], gap="large")
    with hero:
        ui.html(
            '<div class="pb-hero"><h1>La dirección del PPP oficial de la BMV, cinco sesiones antes.</h1>'
            '<p>Modelos de panel sobre el Precio Promedio Ponderado que publica la Bolsa Mexicana de Valores. '
            'Cada precio conserva la firma SHA-256 del boletín del que salió, y cuando una emisora no aparece '
            'en el boletín, el hueco se registra tal cual: no rellenamos datos.</p></div>'
        )
        if fechas:
            k = an.kpis_sesion(precios[precios["fecha"] == fechas[0]])
            c = st.columns(3)
            with c[0]:
                ui.kpi("Emisoras monitoreadas", str(k["total"]), f"sesión {fechas[0]}")
            with c[1]:
                ui.kpi("PPP verificados", str(k["verificadas"]), "con firma SHA-256")
            with c[2]:
                ui.kpi("Huecos conservados", str(k["huecos"]), "sin imputación", "alerta" if k["huecos"] else "")
        ui.seccion("Por qué el PPP y no el último hecho")
        st.write("El último hecho puede moverse con una sola orden pequeña en la subasta de cierre. El PPP pondera "
                 "por volumen todas las operaciones de la sesión, así que refleja dónde se negoció el día. "
                 "Los modelos se validan con esquemas walk-forward purgados y se califican con Brier score.")
    with acceso:
        formulario_acceso(sv)

    ui.seccion("Planes", "precios en USD; cambie o cancele cuando quiera")
    cols = st.columns(3, gap="large")
    for col, pid in zip(cols, ORDEN_PLANES):
        p = PLANES[pid]
        with col:
            items = "".join(f"<li>{escape(i)}</li>" for i in p.incluye)
            ui.html(
                f'<div class="pb-plan-col {"destacado" if pid == PROFESSIONAL else ""}">'
                f'<div style="color:{p.color};font-weight:600">{escape(p.nombre)}</div>'
                f'<div class="pb-precio">${p.precio_usd_mes}<span class="tenue" style="font-size:.9rem"> /mes</span></div>'
                f'<div class="tenue" style="font-size:.88rem;margin:.3rem 0 .4rem 0">{escape(p.resumen)}</div>'
                f'<ul>{items}</ul></div>'
            )
            if st.button(f"Elegir {p.nombre}", key=f"ld_plan_{pid}", width="stretch",
                         type="primary" if pid == PROFESSIONAL else "secondary"):
                st.session_state["plan_elegido"] = pid
                st.toast(f"Plan {p.nombre} seleccionado. Complete el formulario de \"Crear cuenta\".")

    ui.html(
        '<div class="pb-legal"><b>Aviso.</b> Prisma BMV ofrece herramientas cuantitativas basadas en probabilidades '
        'estadísticas. No constituyen recomendación, asesoría ni mandato de compra o venta de valores. Rendimientos '
        'pasados no garantizan resultados futuros. Datos tomados de los boletines públicos de la Bolsa Mexicana de '
        'Valores. © 2026 Prisma BMV.</div>'
    )
