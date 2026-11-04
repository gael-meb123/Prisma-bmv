"""
Prisma BMV - Terminal Cuantitativa: Módulo 2 (Motor de Señales y Consenso IA)
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.data_provider import cargar_senales_panel_g2, cargar_senales_walmex


def render_terminal_senales(plan_usuario: str = "professional") -> None:
    st.markdown("### 🧠 Motor Cuantitativo y Matriz de Consenso Prospectivo")
    st.markdown(
        r"Pronóstico del horizonte a 5 sesiones ($Y_t = \mathbb{I}(\text{PPP}_{t+5} > \text{PPP}_t)$) "
        "contrastando modelos de 1ª Generación (Individuales) y 2ª Generación (Panel Multiemisora con Reversión Relativa)."
    )

    df_g2 = cargar_senales_panel_g2()
    df_w = cargar_senales_walmex()

    if df_g2.empty and df_w.empty:
        st.warning("No hay señales registradas.")
        return

    emisoras_disponibles = ["WALMEX", "GMEXICO", "GFNORTE", "AMX"]
    
    col_sel_emi, col_sel_fecha = st.columns([1, 1])
    with col_sel_emi:
        emi_sel = st.selectbox("Seleccionar Emisora:", options=emisoras_disponibles, index=0)

    # Control de Acceso Freemium (Gating)
    if plan_usuario == "explorer" and emi_sel != "WALMEX":
        st.markdown(
            f"""
            <div class="fintech-card" style="border: 2px dashed #F59E0B; text-align: center; padding: 40px 20px;">
                <div style="font-size: 2.5rem; margin-bottom: 12px;">🔒</div>
                <h3 style="color: #F59E0B; margin: 0 0 10px 0;">Emisora Exclusiva del Plan Professional</h3>
                <p style="color: #94A3B8; max-width: 600px; margin: 0 auto 20px auto; font-size: 0.95rem;">
                    El análisis de panel multiemisora de <b>{emi_sel}</b> con modelos de 2ª generación y reversión relativa 
                    está reservado para suscriptores <b>Professional</b> y <b>Enterprise</b>.
                </p>
                <div style="display: inline-block;">
                    <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid #10B981; padding: 8px 18px; border-radius: 6px; font-weight: 700; font-size: 0.9rem;">
                        Actualizar a Professional por $49 USD/mes
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Filtrar fechas disponibles para la emisora
    sub_g2 = df_g2[df_g2["emisora"] == emi_sel].copy() if not df_g2.empty else pd.DataFrame()
    fechas_emi = sorted(sub_g2["fecha_senal"].dropna().unique().tolist(), reverse=True) if not sub_g2.empty else ["2026-10-30"]

    with col_sel_fecha:
        fecha_sel = st.selectbox("Fecha de Emisión de Señal:", options=fechas_emi, index=0)

    senales_corte = sub_g2[sub_g2["fecha_senal"] == fecha_sel] if not sub_g2.empty else pd.DataFrame()

    if senales_corte.empty:
        st.info("No hay datos de señales para la combinación seleccionada.")
        return

    # Extraccion de métricas del corte
    consenso_raw = senales_corte["estado_consenso_g2"].iloc[0] if "estado_consenso_g2" in senales_corte.columns else "N/D"
    ppp_base = senales_corte["ppp_base_t"].iloc[0] if "ppp_base_t" in senales_corte.columns else 0.0
    ret_rel = senales_corte["ret_10_rel_panel"].iloc[0] if "ret_10_rel_panel" in senales_corte.columns else 0.0
    fecha_target = senales_corte["fecha_objetivo_h5"].iloc[0] if "fecha_objetivo_h5" in senales_corte.columns else "N/D"

    # Tarjeta de Consenso y Estado
    c_card1, c_card2, c_card3 = st.columns([1.5, 1, 1])

    with c_card1:
        st.markdown("<div class='kpi-title'>Estado de Consenso del Panel G2</div>", unsafe_allow_html=True)
        if "SUBIDA" in consenso_raw and "NO_SUBIDA" not in consenso_raw:
            st.markdown(f"<div class='badge-consenso-subida'>🟢 {consenso_raw}</div>", unsafe_allow_html=True)
            st.markdown("<p style='color: #10B981; font-size: 0.85rem; margin-top: 8px;'>Los modelos anticipan alza hacia el objetivo formal.</p>", unsafe_allow_html=True)
        elif "NO_SUBIDA" in consenso_raw:
            st.markdown(f"<div class='badge-consenso-baja'>🔴 {consenso_raw}</div>", unsafe_allow_html=True)
            st.markdown("<p style='color: #EF4444; font-size: 0.85rem; margin-top: 8px;'>Los modelos proyectan consolidación o retroceso.</p>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='badge-consenso-alerta'>🟡 {consenso_raw}</div>", unsafe_allow_html=True)
            st.markdown("<p style='color: #F59E0B; font-size: 0.85rem; margin-top: 8px;'>Divergencia entre algoritmos lineales y retadores.</p>", unsafe_allow_html=True)

    with c_card2:
        st.markdown(
            f"""
            <div class="fintech-card">
                <div class="kpi-title">Precio PPP Base (t0)</div>
                <div class="kpi-value">${ppp_base:.2f}</div>
                <div style="color: #94A3B8; font-size: 0.8rem;">Objetivo: {fecha_target}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_card3:
        color_ret = "#10B981" if ret_rel > 0 else "#EF4444"
        st.markdown(
            f"""
            <div class="fintech-card">
                <div class="kpi-title">Retorno Relativo Panel</div>
                <div class="kpi-value" style="color: {color_ret};">{ret_rel:+.2f}%</div>
                <div style="color: #94A3B8; font-size: 0.8rem;">vs Promedio del Mercado</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Gráfico de Barras Horizontales de Probabilidad
    st.markdown("#### Desglose de Probabilidades por Modelo en Competencia")

    modelos_nombres = []
    probabilidades = []
    colores = []

    for _, row in senales_corte.iterrows():
        mod_nombre = str(row["modelo_g2"]).replace("G2_", "").replace("_POOLED_REL3", "")
        p_val = float(row["probabilidad_subida"]) * 100.0
        modelos_nombres.append(mod_nombre)
        probabilidades.append(p_val)
        colores.append("#10B981" if p_val >= 50.0 else "#EF4444")

    # Si es WALMEX, agregar comparativa con 1ª Generacion si está en la fecha
    if emi_sel == "WALMEX" and not df_w.empty:
        sub_w = df_w[df_w["fecha_senal"] == fecha_sel]
        for _, r_w in sub_w.iterrows():
            m_nom = "G1_" + str(r_w["id_senal"]).split("_")[-1]
            p_w = float(r_w["prob_subida_pct"])
            modelos_nombres.append(m_nom)
            probabilidades.append(p_w)
            colores.append("#10B981" if p_w >= 50.0 else "#EF4444")

    fig = go.Figure(
        go.Bar(
            x=probabilidades,
            y=modelos_nombres,
            orientation="h",
            marker=dict(color=colores),
            text=[f"{p:.2f}%" for p in probabilidades],
            textposition="auto",
        )
    )
    fig.add_vline(x=50.0, line_dash="dash", line_color="#F59E0B", annotation_text="Umbral Neutral 50%")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F1F5F9", family="Inter"),
        xaxis=dict(title="Probabilidad de Subida a 5 Sesiones (%)", range=[0, 100], gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        margin=dict(l=20, r=20, t=20, b=20),
        height=300,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Explicación del Factor Clave
    st.markdown(
        f"""
        <div class="fintech-card" style="border-left: 4px solid #6366F1; margin-top: 15px;">
            <h5 style="color: #6366F1; margin-top: 0;">💡 Interpretación Cuantitativa del Factor Clave</h5>
            <p style="color: #CBD5E1; font-size: 0.92rem; line-height: 1.6; margin-bottom: 0;">
                La variable <b>ret_10_rel_panel ({ret_rel:+.2f}%)</b> cuantifica la dispersión transversal de <b>{emi_sel}</b> 
                frente a la media del mercado. {'Un valor fuertemente negativo activa el inductor de <b>reversión a la media por sobreventa extrema</b>, fundamentando la alta probabilidad de rebote alcista proyectada por los algoritmos regularizados.' if ret_rel < -5 else 'Un valor positivo o neutral indica que la acción no presenta sobreventa relativa, fundamentando un pronóstico de consolidación técnica o ajuste.'}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
