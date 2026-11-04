"""
Prisma BMV - Módulo 1: Monitor de Mercado BMV en Vivo
Desarrollador asignado: Desarrollador 1
Ejecución independiente: streamlit run modulos/modulo1_mercado/vista_mercado.py
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from core.data_provider import cargar_monitoreo_en_vivo, obtener_fechas_mercado, obtener_kpis_mercado
from config_saas import FINTECH_CSS


def render_terminal_mercado() -> None:
    st.markdown("### 🏛️ Monitor de Mercado BMV en Vivo (Oficial PPP)")
    st.markdown(
        "Extracción directa y verificación criptográfica de las **15 emisoras líderes del IPC** "
        "a partir del boletín regulatorio oficial de la Bolsa Mexicana de Valores."
    )

    fechas = obtener_fechas_mercado()
    c_fecha, c_sector = st.columns([1, 2])

    with c_fecha:
        fecha_sel = st.selectbox("Fecha de Sesión BMV:", options=fechas, index=0)

    df_full = cargar_monitoreo_en_vivo()
    if df_full.empty:
        st.warning("No se encontraron registros de mercado en vivo.")
        return

    df_sesion = df_full[df_full["fecha"] == fecha_sel].copy()

    with c_sector:
        sectores = ["Todos"] + sorted(df_sesion["sector_economico"].dropna().unique().tolist())
        sector_sel = st.selectbox("Filtrar por Sector:", options=sectores, index=0)

    if sector_sel != "Todos":
        df_sesion = df_sesion[df_sesion["sector_economico"] == sector_sel]

    # KPIs Ejecutivos
    kpis = obtener_kpis_mercado(fecha_sel)
    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        st.markdown(
            f"""
            <div class="fintech-card">
                <div class="kpi-title">Emisoras en Lista</div>
                <div class="kpi-value">{kpis.get('total_emisoras', 15)}</div>
                <div style="color: #94A3B8; font-size: 0.8rem;">Universo IPC Oficial</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"""
            <div class="fintech-card">
                <div class="kpi-title">PPP Verificados</div>
                <div class="kpi-value" style="color: #10B981;">{kpis.get('total_verificadas', 10)}</div>
                <div class="kpi-delta-up">✓ En Boletín RSS</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"""
            <div class="fintech-card">
                <div class="kpi-title">Huecos Documentados</div>
                <div class="kpi-value" style="color: #F59E0B;">{kpis.get('total_ausentes', 5)}</div>
                <div style="color: #F59E0B; font-size: 0.8rem;">0% Imputación Sintética</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f"""
            <div class="fintech-card">
                <div class="kpi-title">Mayor Ganancia</div>
                <div class="kpi-value" style="color: #10B981; font-size: 1.4rem;">{kpis.get('top_alza_ticker', 'N/D')}</div>
                <div class="kpi-delta-up">+{kpis.get('top_alza_pct', 0.0):.2f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k5:
        st.markdown(
            f"""
            <div class="fintech-card">
                <div class="kpi-title">Mayor Retroceso</div>
                <div class="kpi-value" style="color: #EF4444; font-size: 1.4rem;">{kpis.get('top_baja_ticker', 'N/D')}</div>
                <div class="kpi-delta-down">{kpis.get('top_baja_pct', 0.0):.2f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Tabla Interactiva Formateada
    st.markdown("#### Cotizaciones Oficiales del Boletín")
    
    display_cols = [
        "emisora", "serie", "sector_economico", "ppp_bmv_mxn", 
        "variacion_ppp_vs_anterior_pct", "anterior_bmv_mxn", "estado_captura"
    ]
    present_cols = [c for c in display_cols if c in df_sesion.columns]
    df_view = df_sesion[present_cols].copy()

    st.dataframe(
        df_view,
        column_config={
            "emisora": st.column_config.TextColumn("Ticker", width="small"),
            "serie": st.column_config.TextColumn("Serie", width="small"),
            "sector_economico": st.column_config.TextColumn("Sector", width="medium"),
            "ppp_bmv_mxn": st.column_config.NumberColumn("PPP Oficial ($MXN)", format="$%.2f"),
            "variacion_ppp_vs_anterior_pct": st.column_config.NumberColumn("Var %", format="%.2f%%"),
            "anterior_bmv_mxn": st.column_config.NumberColumn("Anterior ($MXN)", format="$%.2f"),
            "estado_captura": st.column_config.TextColumn("Auditoría de Ingesta"),
        },
        hide_index=True,
        use_container_width=True,
    )

    # Tarjeta de Auditoria Criptografica SHA-256
    st.markdown(
        f"""
        <div class="fintech-card" style="margin-top: 20px; border-left: 4px solid #10B981;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div>
                    <span style="font-weight: 700; color: #10B981; font-size: 0.9rem;">🔐 SELLO CRIPTOGRÁFICO SHA-256 DEL BOLETÍN OFICIAL</span>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #CBD5E1; word-break: break-all; margin-top: 4px;">
                        {kpis.get('sha256_boletin', 'N/A')}
                    </div>
                </div>
                <div>
                    <a href="{kpis.get('url_fuente', '#')}" target="_blank" style="display: inline-block; background: rgba(56, 189, 248, 0.15); color: #38BDF8; padding: 6px 14px; border-radius: 6px; text-decoration: none; font-size: 0.85rem; font-weight: 600; border: 1px solid rgba(56, 189, 248, 0.3);">
                        Ver Boletín en BMV.com.mx ↗
                    </a>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Ejecución aislada para desarrollo independiente
if __name__ == "__main__":
    st.set_page_config(page_title="Prisma BMV - Monitor de Mercado", layout="wide")
    st.markdown(FINTECH_CSS, unsafe_allow_html=True)
    render_terminal_mercado()
