"""
Prisma BMV - Orquestador Principal de la Plataforma FinTech
"""

from __future__ import annotations

import streamlit as st

from config_saas import APP_NAME, APP_SUBTITLE, FINTECH_CSS, PLANS
from views.asistente_widget import render_onboarding_tutorial, render_prismi_assistant_widget
from views.landing import render_landing_page
from views.terminal_auditoria import render_terminal_auditoria
from views.terminal_mercado import render_terminal_mercado
from views.terminal_senales import render_terminal_senales

# Configuración básica de página
st.set_page_config(
    page_title="Prisma BMV - Quantitative Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inyectar estilos FinTech oscuros
st.markdown(FINTECH_CSS, unsafe_allow_html=True)


def inicializar_estado() -> None:
    if "usuario_actual" not in st.session_state:
        st.session_state["usuario_actual"] = None
    if "mostrar_onboarding" not in st.session_state:
        st.session_state["mostrar_onboarding"] = False
    if "onboarding_step" not in st.session_state:
        st.session_state["onboarding_step"] = 1


def main() -> None:
    inicializar_estado()

    # Widget permanente de Prismi (La Grafica Bailarina) en la barra lateral
    render_prismi_assistant_widget()

    usuario = st.session_state.get("usuario_actual")

    # Caso 1: Flujo de Onboarding Interactivo con Prismi
    if st.session_state.get("mostrar_onboarding", False):
        c_head1, c_head2 = st.columns([4, 1])
        with c_head1:
            st.markdown(
                f"<h2 style='color:#10B981; margin:0;'>✨ Configuración de Acceso Institucional - {APP_NAME}</h2>",
                unsafe_allow_html=True,
            )
        with c_head2:
            if st.button("✕ Cerrar Onboarding"):
                st.session_state["mostrar_onboarding"] = False
                st.rerun()

        render_onboarding_tutorial()
        return

    # Caso 2: Visitante No Autenticado -> Landing Page Pública
    if usuario is None:
        render_landing_page()
        return

    # Caso 3: Usuario Autenticado -> Terminal Cuantitativa Privada
    plan_id = usuario.get("plan", "explorer")
    plan_info = PLANS.get(plan_id, PLANS["explorer"])

    # Barra de Estado Superior de la Terminal
    top_col1, top_col2, top_col3 = st.columns([3, 2, 1.2])

    with top_col1:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
                <span style="font-size: 1.6rem; font-weight: 900; background: linear-gradient(135deg, #10B981, #38BDF8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                    {APP_NAME}
                </span>
                <span style="font-size: 0.75rem; background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3); padding: 3px 8px; border-radius: 4px; font-weight: 700;">
                    TERMINAL EN VIVO
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with top_col2:
        st.markdown(
            f"""
            <div style="text-align: right; margin-top: 4px;">
                <span style="font-size: 0.9rem; color: #CBD5E1; font-weight: 600;">{usuario.get('nombre', 'Analista')}</span>
                <span style="display: inline-block; margin-left: 8px; background: rgba(255,255,255,0.08); color: {plan_info['color']}; border: 1px solid {plan_info['color']}; padding: 2px 10px; border-radius: 9999px; font-size: 0.78rem; font-weight: 700;">
                    Plan {plan_info['name']}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with top_col3:
        if st.button("Cerrar Sesión", key="btn_logout", use_container_width=True):
            st.session_state["usuario_actual"] = None
            st.rerun()

    st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255,255,255,0.08); margin: 5px 0 20px 0;'>", unsafe_allow_html=True)

    # Pestañas de la Terminal
    tab_mercado, tab_senales, tab_auditoria = st.tabs(
        [
            "🏛️ Monitor BMV en Vivo",
            "🧠 Señales y Consenso Cuantitativo",
            "⏱️ Auditoría Temporal & AWS",
        ]
    )

    with tab_mercado:
        render_terminal_mercado()

    with tab_senales:
        render_terminal_senales(plan_usuario=plan_id)

    with tab_auditoria:
        render_terminal_auditoria()


if __name__ == "__main__":
    main()
