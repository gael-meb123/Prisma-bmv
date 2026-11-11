"""Checkout sandbox, gestión de cuenta y recorrido guiado de primera visita."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from prisma.plans import EXPLORER, ORDEN_PLANES, PLANES, nivel
from prisma.ui import components as ui
from prisma.ui.contexto import Servicios


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------
def checkout(sv: Servicios, usuario: dict) -> None:
    plan_id = st.session_state.get("checkout_plan")
    if plan_id not in PLANES or PLANES[plan_id].precio_usd_mes == 0:
        st.session_state["vista"] = "terminal"
        st.rerun()
    p = PLANES[plan_id]
    ui.html('<div class="pb-barra"><div class="pb-marca">PRISMA BMV<small>Pago seguro, entorno sandbox</small></div></div>')

    izq, der = st.columns([1, 1.2], gap="large")
    with izq:
        ui.seccion(f"Plan {p.nombre}")
        ui.html(f'<div class="pb-precio">${p.precio_usd_mes} <span class="tenue" style="font-size:.9rem">USD por mes</span></div>')
        for i in p.incluye:
            st.write(f"- {i}")
        st.info("Entorno de pruebas: no se realizan cargos. Tarjeta aprobada: 4242 4242 4242 4242. "
                "Tarjeta rechazada: 4000 0000 0000 0002. Cualquier vencimiento futuro y CVC de 3 dígitos.")
    with der:
        ui.seccion("Datos de pago", "no almacenamos el número completo ni el CVC")
        with st.form("f_pago"):
            titular = st.text_input("Titular", value=usuario.get("nombre", ""))
            numero = st.text_input("Número de tarjeta", placeholder="4242 4242 4242 4242")
            c1, c2 = st.columns(2)
            venc = c1.text_input("Vencimiento (MM/AA)", placeholder="12/28")
            cvc = c2.text_input("CVC", type="password", max_chars=4)
            pagar = st.form_submit_button(f"Pagar ${p.precio_usd_mes} USD y activar {p.nombre}", type="primary")
        if pagar:
            tx, msg = sv.pasarela.cobrar(usuario["email"], plan_id, numero, venc, cvc, titular)
            if tx and tx.estado == "APROBADA":
                sv.usuarios.cambiar_plan(usuario["email"], plan_id, tx.id)
                st.session_state["vista"] = "terminal"
                st.session_state.pop("checkout_plan", None)
                st.toast(f"Plan {p.nombre} activo. Referencia {tx.id}.")
                st.rerun()
            st.error(msg)
        if st.button("Volver sin pagar", key="co_volver"):
            st.session_state["vista"] = "terminal"
            st.session_state.pop("checkout_plan", None)
            st.rerun()


# ---------------------------------------------------------------------------
# Cuenta
# ---------------------------------------------------------------------------
def cuenta(sv: Servicios, usuario: dict) -> None:
    actual = usuario["plan"]
    ui.seccion("Su plan", f"actual: {PLANES[actual].nombre}")
    cols = st.columns(3)
    for col, pid in zip(cols, ORDEN_PLANES):
        p = PLANES[pid]
        with col:
            ui.kpi(p.nombre, f"${p.precio_usd_mes}/mes", "plan actual" if pid == actual else p.resumen,
                   "sube" if pid == actual else "")
            if pid == actual:
                continue
            if nivel(pid) > nivel(actual):
                if st.button(f"Mejorar a {p.nombre}", key=f"ac_up_{pid}", type="primary", width="stretch"):
                    st.session_state.update(checkout_plan=pid, vista="checkout")
                    st.rerun()
            elif pid == EXPLORER:
                if st.button("Cambiar a Explorer", key="ac_down", width="stretch"):
                    sv.usuarios.cambiar_plan(usuario["email"], EXPLORER, "cambio_voluntario")
                    st.toast("Su cuenta ahora es Explorer.")
                    st.rerun()

    ui.seccion("Pagos", "registro del entorno sandbox")
    hist = sv.pasarela.historial(usuario["email"])
    if hist:
        st.dataframe(pd.DataFrame(hist)[["fecha_utc", "id", "plan", "monto_usd", "marca", "ultimos4", "estado", "motivo"]],
                     hide_index=True)
    else:
        st.caption("Sin pagos registrados.")
    if st.button("Repetir el recorrido guiado", key="ac_tour"):
        st.session_state.update(tour_abierto=True, tour_tipo="terminal", tour_paso=0)
        st.rerun()


# ---------------------------------------------------------------------------
# Recorrido guiado (Prismi)
# ---------------------------------------------------------------------------
PASOS = {
    "visitante": [
        ("Hola, soy Prismi", "Le acompaño en su primera visita. Prisma BMV estima la probabilidad de que el Precio "
         "Promedio Ponderado oficial de una emisora sea mayor dentro de cinco sesiones hábiles que hoy: "
         "Y = 1 si PPP(t+5) > PPP(t)."),
        ("Datos que se pueden rastrear", "Cada precio sale del boletín oficial de la BMV y conserva la firma SHA-256 "
         "del archivo. Si una emisora no aparece en el boletín, el hueco queda registrado y nunca se rellena."),
        ("Cree su cuenta", "Con la cuenta Explorer, gratuita, ve el boletín con una sesión de retraso y el modelo base "
         "de WALMEX. El formulario está a la derecha de la portada."),
        ("Elija su plan", "Professional abre el panel G2 de cuatro emisoras al cierre del día. Enterprise añade SQL "
         "sobre el lakehouse en AWS, exportación masiva y auditoría forense."),
    ],
    "terminal": [
        ("Monitor", "La primera pestaña muestra el PPP de las 15 emisoras, la variación por sector y la firma del "
         "boletín de la sesión."),
        ("Señales", "El semáforo resume si los modelos coinciden: verde para subida, rojo para no subida y amarillo "
         "cuando discrepan. Debajo verá la probabilidad de cada modelo y qué variables la explican."),
        ("Auditoría", "Siga cada señal sesión por sesión hasta t+5 y vea qué modelos van acertando. Las sesiones sin "
         "PPP aparecen marcadas, no interpoladas."),
        ("Pregúnteme", "Estoy en la esquina inferior derecha. Respondo sobre la plataforma y los modelos con los datos "
         "del día; no doy recomendaciones de compra o venta."),
    ],
}


@st.dialog("Recorrido de Prisma BMV", width="large")
def recorrido(sv: Servicios, usuario: dict | None) -> None:
    from prisma.ui.views.prismi import AVATAR

    tipo = st.session_state.get("tour_tipo", "visitante")
    pasos = PASOS[tipo]
    i = min(st.session_state.get("tour_paso", 0), len(pasos) - 1)
    a, b = st.columns([1, 3])
    with a:
        ui.html(AVATAR)
    with b:
        st.caption(f"Paso {i + 1} de {len(pasos)}")
        st.subheader(pasos[i][0])
        st.write(pasos[i][1])
    c1, c2, c3 = st.columns(3)
    if i > 0 and c1.button("Anterior", key="tr_prev"):
        st.session_state["tour_paso"] = i - 1
        st.rerun(scope="fragment")
    if i < len(pasos) - 1:
        if c2.button("Siguiente", type="primary", key="tr_next"):
            st.session_state["tour_paso"] = i + 1
            st.rerun(scope="fragment")
        if c3.button("Saltar", key="tr_skip"):
            _cerrar(sv, usuario)
    elif c2.button("Empezar", type="primary", key="tr_fin"):
        _cerrar(sv, usuario)


def _cerrar(sv: Servicios, usuario: dict | None) -> None:
    st.session_state["tour_paso"] = 0
    if usuario:
        sv.usuarios.marcar_tour_completado(usuario["email"])
    st.rerun()
