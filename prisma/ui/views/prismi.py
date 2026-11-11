"""Prismi: asistente flotante en la esquina inferior derecha de toda la aplicación."""

from __future__ import annotations

from html import escape

import streamlit as st

from prisma.plans import EXPLORER, tiene_acceso
from prisma.services import prismi as motor
from prisma.ui import components as ui
from prisma.ui.contexto import Servicios, hoy_iso

# Prismi: una vela verde con brazos y piernas, acompañada de una vela roja y otra verde.
AVATAR = """
<div style="text-align:center"><svg class="prismi-baile" width="96" height="96" viewBox="0 0 120 120"
 role="img" aria-label="Prismi, la gráfica bailarina" xmlns="http://www.w3.org/2000/svg">
 <ellipse cx="60" cy="112" rx="32" ry="5" fill="rgba(0,0,0,.35)"/>
 <path d="M47 92 Q41 105 33 108" stroke="#2EBD85" stroke-width="4" stroke-linecap="round" fill="none"/>
 <path d="M73 92 Q79 104 88 107" stroke="#2EBD85" stroke-width="4" stroke-linecap="round" fill="none"/>
 <line x1="60" y1="12" x2="60" y2="28" stroke="#2EBD85" stroke-width="3" stroke-linecap="round"/>
 <line x1="60" y1="88" x2="60" y2="97" stroke="#2EBD85" stroke-width="3" stroke-linecap="round"/>
 <rect x="38" y="28" width="44" height="60" rx="5" fill="#2EBD85"/>
 <rect x="90" y="46" width="14" height="28" rx="3" fill="#F0616D"/>
 <line x1="97" y1="38" x2="97" y2="82" stroke="#F0616D" stroke-width="2"/>
 <rect x="16" y="54" width="12" height="22" rx="3" fill="#2EBD85" opacity=".75"/>
 <line x1="22" y1="46" x2="22" y2="82" stroke="#2EBD85" stroke-width="2" opacity=".75"/>
 <ellipse cx="50" cy="49" rx="4.5" ry="6.5" fill="#0D1117"/><ellipse cx="70" cy="49" rx="4.5" ry="6.5" fill="#0D1117"/>
 <circle cx="51" cy="47" r="1.8" fill="#fff"/><circle cx="71" cy="47" r="1.8" fill="#fff"/>
 <path d="M52 60 Q60 68 68 60" stroke="#0D1117" stroke-width="3" stroke-linecap="round" fill="none"/>
 <path d="M38 52 Q24 42 21 30" stroke="#2EBD85" stroke-width="4" stroke-linecap="round" fill="none"/>
 <path d="M82 52 Q98 44 102 30" stroke="#2EBD85" stroke-width="4" stroke-linecap="round" fill="none"/>
</svg></div>
"""

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
