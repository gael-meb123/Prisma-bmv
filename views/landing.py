"""
Prisma BMV - Landing Page Pública Institucional
"""

from __future__ import annotations

import streamlit as st
from config_saas import APP_NAME, APP_SUBTITLE, APP_TAGLINE, PLANS
from core.auth import autenticar_usuario, registrar_usuario


def render_landing_page() -> None:
    # 1. Barra de Navegacion Superior
    nav_col1, nav_col2, nav_col3 = st.columns([3, 1, 1])
    with nav_col1:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.8rem; font-weight: 900; background: linear-gradient(135deg, #10B981, #38BDF8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                    {APP_NAME}
                </span>
                <span style="font-size: 0.75rem; background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3); padding: 2px 8px; border-radius: 4px; font-weight: 600;">
                    TERMINAL PRO
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with nav_col2:
        if st.button("Explorar Planes", key="nav_btn_planes"):
            st.session_state["scroll_a_planes"] = True
    with nav_col3:
        if st.button("Iniciar Sesión", key="nav_btn_login", type="secondary"):
            st.session_state["ver_modal_login"] = True

    st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255,255,255,0.08); margin: 15px 0 35px 0;'>", unsafe_allow_html=True)

    # 2. Hero Section
    st.markdown(
        f"""
        <div style="text-align: center; max-width: 900px; margin: 0 auto 30px auto;">
            <div style="display: inline-block; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.25); padding: 6px 16px; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; color: #38BDF8; margin-bottom: 20px;">
                ⚡ Modelos Cuantitativos de 2ª Generación para el IPC Mexicano
            </div>
            <h1 style="font-size: 2.8rem; font-weight: 800; line-height: 1.2; margin-bottom: 18px; color: #FFFFFF;">
                {APP_TAGLINE}
            </h1>
            <p style="font-size: 1.15rem; color: #94A3B8; line-height: 1.6; margin-bottom: 28px;">
                Anticipe la dirección a 5 sesiones del <b>Precio Promedio Ponderado (PPP)</b> oficial mediante 
                modelos de panel multivariado con regularización, reversión a la media y auditoría criptográfica SHA-256 en la nube.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cta_col1, cta_col2, cta_col3 = st.columns([1, 1.2, 1])
    with cta_col2:
        btn_start = st.button("🚀 Comenzar con Asistente Prismi (Tutorial Gratis)", type="primary", use_container_width=True)
        if btn_start:
            st.session_state["mostrar_onboarding"] = True
            st.session_state["onboarding_step"] = 1
            st.rerun()

    # Credenciales de Confianza
    st.markdown(
        """
        <div style="display: flex; justify-content: center; gap: 30px; margin: 35px 0 50px 0; color: #94A3B8; font-size: 0.88rem; font-weight: 500;">
            <span>🛡️ <b>Datos 100% Oficiales BMV</b></span>
            <span>🔒 <b>Cero Imputación Sintética</b></span>
            <span>⚡ <b>Validación Purgada Walk-Forward</b></span>
            <span>☁️ <b>Data Lakehouse en AWS</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Propuesta de Valor: PPP vs Ultimo Hecho
    col_pv1, col_pv2 = st.columns(2)
    with col_pv1:
        st.markdown(
            """
            <div class="fintech-card">
                <h4 style="color: #EF4444; margin-top: 0;">⚠️ El Riesgo de los Precios de Cierre Tradicionales</h4>
                <p style="color: #94A3B8; font-size: 0.95rem; line-height: 1.6;">
                    La mayoría de los sistemas financieros operan con el <b>precio de último hecho</b>. En mercados emergentes como la BMV, este valor es fácilmente distorsionado por subastas de cierre con bajo volumen, órdenes residuales o manipulación ilíquida.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_pv2:
        st.markdown(
            """
            <div class="fintech-card" style="border-color: rgba(16, 185, 129, 0.4);">
                <h4 style="color: #10B981; margin-top: 0;">💎 La Ventaja Cuantitativa del PPP Oficial</h4>
                <p style="color: #E2E8F0; font-size: 0.95rem; line-height: 1.6;">
                    <b>Prisma BMV</b> opera exclusivamente con el <b>Precio Promedio Ponderado oficial</b> publicado en los boletines regulatorios de la BMV. Representa el flujo institucional ponderado por volumen, inmune al ruido de cierre y respaldado por hashes SHA-256 inmutables.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 4. Sección de Planes Freemium (Pricing Table)
    st.markdown("<div id='planes-seccion'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="text-align: center; margin: 50px 0 30px 0;">
            <h2 style="font-size: 2rem; font-weight: 800; color: #FFFFFF; margin-bottom: 8px;">Planes de Suscripción Institucional</h2>
            <p style="color: #94A3B8; font-size: 1rem;">Diseñados con rigor cuantitativo para inversores individuales, analistas y mesas de dinero.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    p_col1, p_col2, p_col3 = st.columns(3)

    # Plan Explorer
    with p_col1:
        st.markdown(
            f"""
            <div class="fintech-card" style="height: 480px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <span style="background: rgba(148, 163, 184, 0.2); color: #94A3B8; padding: 3px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 700;">
                        {PLANS['explorer']['badge']}
                    </span>
                    <h3 style="color: #FFFFFF; margin: 12px 0 4px 0;">{PLANS['explorer']['name']}</h3>
                    <div style="font-size: 2.2rem; font-weight: 800; color: #FFFFFF; font-family: 'JetBrains Mono', monospace;">
                        {PLANS['explorer']['price']}
                    </div>
                    <div style="color: #64748B; font-size: 0.85rem; margin-bottom: 16px;">{PLANS['explorer']['period']}</div>
                    <p style="color: #94A3B8; font-size: 0.88rem; margin-bottom: 20px;">{PLANS['explorer']['description']}</p>
                    <ul style="color: #CBD5E1; font-size: 0.85rem; padding-left: 20px; line-height: 1.8;">
                        {''.join([f"<li>{f}</li>" for f in PLANS['explorer']['features']])}
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Elegir Explorer", key="plan_exp_btn", use_container_width=True):
            st.session_state["mostrar_onboarding"] = True
            st.session_state["temp_plan"] = "explorer"
            st.session_state["onboarding_step"] = 3
            st.rerun()

    # Plan Professional (Recomendado)
    with p_col2:
        st.markdown(
            f"""
            <div class="fintech-card" style="height: 480px; display: flex; flex-direction: column; justify-content: space-between; border: 2px solid #10B981; background: rgba(16, 185, 129, 0.05);">
                <div>
                    <span style="background: rgba(16, 185, 129, 0.2); color: #10B981; padding: 3px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 700;">
                        {PLANS['professional']['badge']}
                    </span>
                    <h3 style="color: #10B981; margin: 12px 0 4px 0;">{PLANS['professional']['name']}</h3>
                    <div style="font-size: 2.2rem; font-weight: 800; color: #FFFFFF; font-family: 'JetBrains Mono', monospace;">
                        {PLANS['professional']['price']}
                    </div>
                    <div style="color: #64748B; font-size: 0.85rem; margin-bottom: 16px;">{PLANS['professional']['period']}</div>
                    <p style="color: #E2E8F0; font-size: 0.88rem; margin-bottom: 20px;">{PLANS['professional']['description']}</p>
                    <ul style="color: #E2E8F0; font-size: 0.85rem; padding-left: 20px; line-height: 1.8;">
                        {''.join([f"<li>{f}</li>" for f in PLANS['professional']['features'][:5]])}
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Comenzar con Professional", key="plan_pro_btn", type="primary", use_container_width=True):
            st.session_state["mostrar_onboarding"] = True
            st.session_state["temp_plan"] = "professional"
            st.session_state["onboarding_step"] = 3
            st.rerun()

    # Plan Enterprise
    with p_col3:
        st.markdown(
            f"""
            <div class="fintech-card" style="height: 480px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <span style="background: rgba(99, 102, 241, 0.2); color: #6366F1; padding: 3px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 700;">
                        {PLANS['enterprise']['badge']}
                    </span>
                    <h3 style="color: #FFFFFF; margin: 12px 0 4px 0;">{PLANS['enterprise']['name']}</h3>
                    <div style="font-size: 2.2rem; font-weight: 800; color: #FFFFFF; font-family: 'JetBrains Mono', monospace;">
                        {PLANS['enterprise']['price']}
                    </div>
                    <div style="color: #64748B; font-size: 0.85rem; margin-bottom: 16px;">{PLANS['enterprise']['period']}</div>
                    <p style="color: #94A3B8; font-size: 0.88rem; margin-bottom: 20px;">{PLANS['enterprise']['description']}</p>
                    <ul style="color: #CBD5E1; font-size: 0.85rem; padding-left: 20px; line-height: 1.8;">
                        {''.join([f"<li>{f}</li>" for f in PLANS['enterprise']['features'][:5]])}
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Contactar Enterprise", key="plan_ent_btn", use_container_width=True):
            st.session_state["mostrar_onboarding"] = True
            st.session_state["temp_plan"] = "enterprise"
            st.session_state["onboarding_step"] = 3
            st.rerun()

    # Modal de Inicio de Sesión
    if st.session_state.get("ver_modal_login", False):
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### 🔐 Acceso a la Terminal Prisma BMV")
        log_col1, log_col2 = st.columns([1, 1])
        with log_col1:
            email_log = st.text_input("Correo Registrado", placeholder="demo@prismabmv.com", key="login_email")
            pwd_log = st.text_input("Contraseña", type="password", key="login_pwd")
            c_entrar, c_cerrar = st.columns(2)
            with c_entrar:
                if st.button("Entrar a la Terminal", type="primary"):
                    ok, info, msg = autenticar_usuario(email_log, pwd_log)
                    if ok:
                        st.session_state["usuario_actual"] = info
                        st.session_state["ver_modal_login"] = False
                        st.success("¡Bienvenido! Cargando terminal...")
                        st.rerun()
                    else:
                        st.error(msg)
            with c_cerrar:
                if st.button("Cancelar"):
                    st.session_state["ver_modal_login"] = False
                    st.rerun()
        with log_col2:
            st.info(
                "💡 **Credenciales de Demostración:**\n\n"
                "- Correo: `demo@prismabmv.com`\n"
                "- Contraseña: `Prisma2026!`\n"
                "- Plan: **Professional**"
            )

    # 5. Footer Institucional
    st.markdown(
        """
        <div style="margin-top: 80px; padding: 30px 0; border-top: 1px solid rgba(255,255,255,0.08); text-align: center; color: #64748B; font-size: 0.8rem;">
            <p style="margin-bottom: 8px;">
                © 2026 <b>Prisma BMV</b>. Todos los derechos reservados. Plataforma de Inteligencia Cuantitativa Bursátil.
            </p>
            <p style="max-width: 800px; margin: 0 auto; line-height: 1.5;">
                Aviso Regulatorio: Los modelos matemáticos y pronósticos estadísticos de Prisma BMV son herramientas analíticas de apoyo a la toma de decisiones y no constituyen una recomendación o mandato legal de compra o venta de valores. Datos extraídos directamente de los boletines oficiales de la Bolsa Mexicana de Valores.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
