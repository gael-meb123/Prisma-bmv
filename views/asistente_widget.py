"""
Prisma BMV - Mascota y Asistente Interactivo: Prismi (La Gráfica Bailarina)
"""

from __future__ import annotations

import streamlit as st
from core.auth import marcar_onboarding_completado, registrar_usuario
from core.claude_bot import responder_con_claude

# SVG animado de Prismi: La Grafica Bursatil Bailarina
PRISMI_DANCING_SVG = """
<div style="text-align: center; margin-bottom: 12px;">
    <svg width="120" height="120" viewBox="0 0 120 120" class="prismi-avatar-dance" xmlns="http://www.w3.org/2000/svg">
        <!-- Sombra en el suelo -->
        <ellipse cx="60" cy="112" rx="35" ry="6" fill="rgba(0,0,0,0.3)" />
        
        <!-- Piernitas bailarinas -->
        <path d="M 45 92 Q 40 106 32 108" stroke="#10B981" stroke-width="4" stroke-linecap="round" fill="none" />
        <ellipse cx="30" cy="108" rx="6" ry="3" fill="#10B981" />
        
        <path d="M 75 92 Q 80 104 88 107" stroke="#10B981" stroke-width="4" stroke-linecap="round" fill="none" />
        <ellipse cx="90" cy="107" rx="6" ry="3" fill="#10B981" />

        <!-- Cuerpo: Vela Bursatil Verde Brillante (Cuerpo Principal) -->
        <!-- Mecha superior -->
        <line x1="60" y1="12" x2="60" y2="28" stroke="#34D399" stroke-width="3" stroke-linecap="round" />
        <!-- Mecha inferior -->
        <line x1="60" y1="88" x2="60" y2="98" stroke="#34D399" stroke-width="3" stroke-linecap="round" />
        
        <!-- Cuerpo de la vela -->
        <rect x="36" y="28" width="48" height="60" rx="8" fill="url(#candleGradient)" stroke="#10B981" stroke-width="2.5" class="prismi-glow" />
        
        <!-- Vela roja secundaria (Acompañante de baile) -->
        <rect x="88" y="45" width="16" height="30" rx="4" fill="#EF4444" opacity="0.85" />
        <line x1="96" y1="36" x2="96" y2="45" stroke="#EF4444" stroke-width="2" />
        <line x1="96" y1="75" x2="96" y2="82" stroke="#EF4444" stroke-width="2" />
        
        <!-- Vela verde terciaria pequeña -->
        <rect x="16" y="52" width="14" height="24" rx="4" fill="#10B981" opacity="0.85" />
        <line x1="23" y1="44" x2="23" y2="52" stroke="#10B981" stroke-width="2" />
        <line x1="23" y1="76" x2="23" y2="82" stroke="#10B981" stroke-width="2" />

        <!-- Cara de Prismi (Ojos grandes y expresivos) -->
        <ellipse cx="48" cy="48" rx="5" ry="7" fill="#064E3B" />
        <ellipse cx="72" cy="48" rx="5" ry="7" fill="#064E3B" />
        <circle cx="49" cy="46" r="2.2" fill="#FFFFFF" />
        <circle cx="73" cy="46" r="2.2" fill="#FFFFFF" />
        
        <!-- Mejillas sonrosadas -->
        <ellipse cx="42" cy="58" rx="4" ry="2.5" fill="#34D399" opacity="0.6" />
        <ellipse cx="78" cy="58" rx="4" ry="2.5" fill="#34D399" opacity="0.6" />

        <!-- Sonrisa animada -->
        <path d="M 52 56 Q 60 66 68 56" stroke="#064E3B" stroke-width="3" stroke-linecap="round" fill="none" />

        <!-- Bracitos saludando al ritmo del mercado -->
        <path d="M 36 50 Q 20 40 18 28" stroke="#10B981" stroke-width="4" stroke-linecap="round" fill="none" />
        <circle cx="18" cy="28" r="4" fill="#10B981" />
        
        <path d="M 84 50 Q 102 44 105 32" stroke="#10B981" stroke-width="4" stroke-linecap="round" fill="none" />
        <circle cx="105" cy="32" r="4" fill="#10B981" />

        <!-- Degradado para la vela principal -->
        <defs>
            <linearGradient id="candleGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#34D399" />
                <stop offset="100%" stop-color="#059669" />
            </linearGradient>
        </defs>
    </svg>
</div>
"""


def render_onboarding_tutorial() -> None:
    """Modal guiado de Onboarding conducido por Prismi la Grafica Bailarina."""
    st.markdown(
        """
        <div class="fintech-card" style="border: 2px solid #10B981; background: rgba(16, 185, 129, 0.08);">
            <div style="display: flex; align-items: center; gap: 15px;">
                <div style="font-size: 2.2rem;">💃📈</div>
                <div>
                    <h3 style="margin: 0; color: #10B981;">¡Hola! Soy Prismi, tu asistente bursátil</h3>
                    <p style="margin: 4px 0 0 0; color: #E2E8F0; font-size: 0.95rem;">
                        Permíteme darte un recorrido rápido para activar tu acceso institucional a Prisma BMV.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_img, col_form = st.columns([1, 2])

    with col_img:
        st.markdown(PRISMI_DANCING_SVG, unsafe_allow_html=True)
        st.markdown(
            """
            <div style="text-align: center; color: #94A3B8; font-size: 0.85rem; padding: 0 10px;">
                <i>"¡Bailando con los precios ponderados de la BMV! Aquí aprenderás cómo anticipar movimientos de 5 días con IA."</i>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_form:
        paso = st.session_state.get("onboarding_step", 1)

        if paso == 1:
            st.markdown("#### Paso 1 de 3: ¿Qué es Prisma BMV?")
            st.markdown(
                """
                - **Pronóstico a 5 días:** Modelamos si el **Precio Promedio Ponderado oficial** ($PPP_{t+5}$) superará al de hoy ($PPP_t$).
                - **Gobernanza Criptográfica:** Cada boletín diario de la BMV se verifica con su firma SHA-256 inmutable.
                - **Cero Imputación:** Si una emisora no cotiza en el boletín, no inventamos precios.
                """
            )
            if st.button("Siguiente: Elegir Plan de Acceso ➡️", key="btn_next_step1"):
                st.session_state["onboarding_step"] = 2
                st.rerun()

        elif paso == 2:
            st.markdown("#### Paso 2 de 3: Selecciona tu Plan Institucional")
            plan_seleccionado = st.radio(
                "Elige la modalidad que mejor se adapte a tu operativa:",
                options=["professional", "explorer", "enterprise"],
                format_func=lambda x: {
                    "explorer": "Plan Explorer ($0 USD) • Inferencia básica WALMEX",
                    "professional": "Plan Professional ($49 USD/mes) • Panel Multiemisora G2 + Prismi Claude (Recomendado)",
                    "enterprise": "Plan Enterprise ($249 USD/mes) • Acceso AWS Athena / S3 + Soporte Cuantitativo",
                }[x],
                index=0,
            )
            st.session_state["temp_plan"] = plan_seleccionado

            c_back, c_next = st.columns(2)
            with c_back:
                if st.button("⬅️ Anterior", key="btn_back_step2"):
                    st.session_state["onboarding_step"] = 1
                    st.rerun()
            with c_next:
                if st.button("Siguiente: Crear Cuenta ➡️", key="btn_next_step2"):
                    st.session_state["onboarding_step"] = 3
                    st.rerun()

        elif paso == 3:
            st.markdown("#### Paso 3 de 3: Registro Rápido")
            nombre = st.text_input("Nombre Completo o Razón Social", placeholder="Ej. Ana Morales - Fondo Alfa")
            email = st.text_input("Correo Institucional / Profesional", placeholder="ana@fondooalfa.mx")
            password = st.text_input("Contraseña", type="password")

            c_back, c_finish = st.columns(2)
            with c_back:
                if st.button("⬅️ Anterior", key="btn_back_step3"):
                    st.session_state["onboarding_step"] = 2
                    st.rerun()
            with c_finish:
                if st.button("🚀 Comenzar a Operar en Prisma BMV", type="primary"):
                    plan_final = st.session_state.get("temp_plan", "professional")
                    ok, msg = registrar_usuario(nombre, email, password, plan_final)
                    if ok:
                        st.session_state["usuario_actual"] = {
                            "nombre": nombre,
                            "email": email,
                            "plan": plan_final,
                            "onboarding_completado": True,
                        }
                        st.session_state["onboarding_step"] = 1
                        st.session_state["mostrar_onboarding"] = False
                        st.success("¡Cuenta configurada con éxito! Bienvenido a la Terminal.")
                        st.rerun()
                    else:
                        st.error(msg)


def render_prismi_assistant_widget() -> None:
    """Renderiza a Prismi la Grafica Bailarina en el panel lateral o expander permanente."""
    with st.sidebar:
        st.markdown(PRISMI_DANCING_SVG, unsafe_allow_html=True)
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 8px;">
                <h4 style="margin: 0; color: #10B981;">Prismi</h4>
                <span style="font-size: 0.78rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em;">
                    Asistente Cuantitativo • Claude AI
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("💬 Consultar a Prismi (Chat Cuantitativo)", expanded=False):
            if "prismi_messages" not in st.session_state:
                st.session_state["prismi_messages"] = [
                    {
                        "role": "assistant",
                        "content": (
                            "¡Hola! Soy Prismi, tu gráfica bailarina. Puedo resolver cualquier duda sobre "
                            "las 15 emisoras de la BMV, los modelos de 1ª y 2ª generación o cómo interpretar "
                            "nuestras probabilidades cuantitativas. ¿En qué puedo orientarte hoy?"
                        ),
                    }
                ]

            # Mostrar historial reciente
            for m in st.session_state["prismi_messages"][-4:]:
                if m["role"] == "user":
                    st.markdown(f"**Tú:** {m['content']}")
                else:
                    st.markdown(f"**Prismi 💃:** {m['content']}")

            # Botones de preguntas rapidas
            col_b1, col_b2 = st.columns(2)
            pregunta_rapida = None
            with col_b1:
                if st.button("📈 ¿Resultados?", key="q_res"):
                    pregunta_rapida = "como van los resultados"
                if st.button("🎯 ¿Qué es PPP?", key="q_ppp"):
                    pregunta_rapida = "que es el ppp"
            with col_b2:
                if st.button("💡 ¿Reversión?", key="q_rev"):
                    pregunta_rapida = "que es ret_10_rel_panel"
                if st.button("💳 Ver Planes", key="q_plan"):
                    pregunta_rapida = "cuales son los planes"

            user_query = st.text_input(
                "Pregúntale a Prismi:", placeholder="Ej. ¿Qué señal tiene GMEXICO hoy?", key="input_prismi_chat"
            )

            pregunta_a_enviar = pregunta_rapida if pregunta_rapida else user_query

            if st.button("Enviar Consulta", key="btn_send_prismi") and pregunta_a_enviar:
                st.session_state["prismi_messages"].append({"role": "user", "content": pregunta_a_enviar})
                respuesta = responder_con_claude(
                    pregunta_a_enviar, historial=st.session_state["prismi_messages"]
                )
                st.session_state["prismi_messages"].append({"role": "assistant", "content": respuesta})
                st.rerun()
