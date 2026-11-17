"""Prismi: asistente flotante en la esquina inferior derecha de toda la aplicación."""

from __future__ import annotations

from html import escape

import streamlit as st

from prisma.plans import EXPLORER, tiene_acceso
from prisma.services import prismi as motor
from prisma.ui import components as ui
from prisma.ui.mascota import mascota
from prisma.ui.contexto import Servicios, hoy_iso

# Prismi: el billete superhéroe, el mismo personaje del sitio web (frontend/).
AVATAR = mascota("happy", "wave")

SALUDO = ("Soy Prismi. Te explico el PPP, las señales de cada modelo, el seguimiento hasta t+5 o cómo "
          "funciona la plataforma, con los datos del día.")
RAPIDAS = {
    "¿Qué es el PPP?": "¿Qué es el PPP?",
    "Señal de GMEXICO": "¿Cuál es la señal de GMEXICO?",
    "¿Cómo van los aciertos?": "¿Cómo van los resultados?",
    "ret_10_rel_panel": "¿Qué es ret_10_rel_panel?",
}


def _enviar(sv: Servicios, pregunta: str, usuario: dict | None, contexto: motor.ContextoMercado) -> None:
    historial = st.session_state.setdefault("prismi_msgs", [])
    plan = usuario["plan"] if usuario else EXPLORER
    usar_claude, aviso = False, None
    if usuario and sv.settings.anthropic_api_key:
        if tiene_acceso(plan, "prismi_ilimitado"):
            usar_claude = True
        else:
            permitido, restantes = sv.usuarios.consumir_cuota_prismi(
                usuario["email"], sv.settings.prismi_cuota_explorer_diaria, hoy_iso())
            usar_claude = permitido
            aviso = (f"Te quedan {restantes} consultas a Claude hoy." if permitido else
                     "Agotaste tus consultas diarias a Claude; respondo con el motor local. Professional es ilimitado.")
    r = motor.responder(pregunta, historial, contexto, plan, sv.settings.anthropic_api_key,
                        sv.settings.prismi_modelo, usar_claude)
    historial.append({"role": "user", "content": pregunta})
    historial.append({"role": "assistant", "content": r.texto, "origen": r.origen, "aviso": aviso})
    st.session_state["prismi_msgs"] = historial[-20:]


def render(sv: Servicios, usuario: dict | None, contexto: motor.ContextoMercado) -> None:
    with st.container(key="prismi_flotante"):
        with st.popover("Prismi", icon=":material/candlestick_chart:"):
            ui.html(AVATAR)
            ui.html('<div class="prismi-origen" style="text-align:center;margin-bottom:.5rem">'
                    'Asistente cuantitativo de Prisma BMV</div>')
            msgs = st.session_state.get("prismi_msgs", [])
            if not msgs:
                ui.html(f'<div class="prismi-msg a">{escape(SALUDO)}</div>')
            for m in msgs[-6:]:
                if m["role"] == "user":
                    ui.html(f'<div class="prismi-msg u">{escape(m["content"])}</div>')
                else:
                    origen = {"CLAUDE": "Claude", "LOCAL": "motor local", "GUARDRAIL": "regla de alcance"}.get(m.get("origen"), "")
                    st.markdown(m["content"])
                    nota = f"respondido por {origen}" + (f". {m['aviso']}" if m.get("aviso") else "")
                    ui.html(f'<div class="prismi-origen">{escape(nota)}</div>')
            cols = st.columns(2)
            for i, (etq, preg) in enumerate(RAPIDAS.items()):
                if cols[i % 2].button(etq, key=f"pr_q{i}", width="stretch"):
                    _enviar(sv, preg, usuario, contexto)
                    st.rerun()
            with st.form("pr_form", clear_on_submit=True, border=False):
                txt = st.text_input("Pregunta", placeholder="Escribe tu pregunta", label_visibility="collapsed")
                if st.form_submit_button("Enviar", width="stretch") and txt.strip():
                    _enviar(sv, txt, usuario, contexto)
                    st.rerun()
            if not usuario:
                st.caption("Sin cuenta respondo con el motor local. Con cuenta, uso Claude.")
            st.caption(motor.AVISO)
