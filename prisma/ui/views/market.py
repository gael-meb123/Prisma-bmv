"""Módulo 2.1 - Monitor de mercado: PPP oficial, KPIs por sector y firma SHA-256."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from prisma.data import analytics as an
from prisma.domain import bmv_core as core
from prisma.plans import tiene_acceso
from prisma.ui import components as ui
from prisma.ui.contexto import VistaPlan
from prisma.ui.theme import COLORES as C
from prisma.ui.theme import PLANTILLA


def _estilo_tabla(df: pd.DataFrame):
    def color_var(v):
        if pd.isna(v):
            return f"color:{C['tenue']}"
        return f"color:{C['sube']}" if v > 0 else (f"color:{C['baja']}" if v < 0 else f"color:{C['tenue']}")

    def color_estado(v):
        return f"color:{C['alerta']}" if v == core.ESTADO_HUECO else f"color:{C['tenue']}"

    # Formato como texto: un hueco se ve como "—", nunca como 0 ni como "None".
    def dinero(v):
        return "—" if pd.isna(v) else f"${v:,.2f}"

    def pct(v):
        return "—" if pd.isna(v) else f"{v:+.2f}%"

    return (
        df.style.map(color_var, subset=["Var. PPP %"])
        .map(color_estado, subset=["Estado de captura"])
        .format({"PPP oficial": dinero, "Último": dinero, "Anterior": dinero, "Var. PPP %": pct})
    )


def render(datos: dict, vp: VistaPlan) -> None:
    precios: pd.DataFrame = datos["precios"]
    if not vp.fechas:
        st.info("El lakehouse todavía no tiene sesiones publicadas. La primera ejecución de la Lambda las cargará.")
        return

    c1, c2, c3 = st.columns([1.1, 1.6, 2.3])
    fecha = c1.selectbox("Sesión BMV", vp.fechas, index=0, key="mk_fecha")
    sesion_total = precios[precios["fecha"] == fecha]
    sectores = ["Todos los sectores"] + sorted(sesion_total["sector_economico"].unique())
    sector = c2.selectbox("Sector", sectores, key="mk_sector")
    with c3:
        if not tiene_acceso(vp.plan, "boletin_al_cierre"):
            st.caption("Su plan muestra el boletín con una sesión de retraso. "
                       "Professional lo publica al cierre de cada día hábil (16:45, hora de CDMX).")
        else:
            st.caption("Boletín al cierre: se actualiza cada día hábil a las 16:45, hora de Ciudad de México.")

    sesion = sesion_total if sector == sectores[0] else sesion_total[sesion_total["sector_economico"] == sector]
    k = an.kpis_sesion(sesion)

    cols = st.columns(5)
    with cols[0]:
        ui.kpi("Emisoras en la vista", str(k["total"]), "lista oficial de 15")
    with cols[1]:
        ui.kpi("PPP verificados", str(k["verificadas"]), f"{k['alzas']} al alza, {k['bajas']} a la baja", "")
    with cols[2]:
        ui.kpi("Huecos documentados", str(k["huecos"]), "sin imputar", "alerta" if k["huecos"] else "")
    with cols[3]:
        a = k["mayor_alza"]
        ui.kpi("Mayor alza", a["emisora"] if a else "—", ui.fmt_pct(a["variacion_ppp_vs_anterior_pct"]) if a else "",
               ui.tono(a["variacion_ppp_vs_anterior_pct"]) if a else "")
    with cols[4]:
        b = k["mayor_baja"]
        ui.kpi("Mayor baja", b["emisora"] if b else "—", ui.fmt_pct(b["variacion_ppp_vs_anterior_pct"]) if b else "",
               ui.tono(b["variacion_ppp_vs_anterior_pct"]) if b else "")

    ui.seccion("Cotizaciones del boletín", "verde y rojo indican dirección del PPP frente a la sesión anterior")
    tabla = sesion[["emisora", "serie", "sector_economico", "ppp_bmv_mxn", "ultimo_bmv_mxn", "anterior_bmv_mxn",
                    "variacion_ppp_vs_anterior_pct", "estado_captura"]].rename(columns={
        "emisora": "Emisora", "serie": "Serie", "sector_economico": "Sector", "ppp_bmv_mxn": "PPP oficial",
        "ultimo_bmv_mxn": "Último", "anterior_bmv_mxn": "Anterior", "variacion_ppp_vs_anterior_pct": "Var. PPP %",
        "estado_captura": "Estado de captura"})
    st.dataframe(_estilo_tabla(tabla), hide_index=True, height=min(38 * (len(tabla) + 1), 600))

    izq, der = st.columns([1.4, 1])
    with izq:
        ui.seccion("Variación media por sector", "solo emisoras con PPP verificado")
        sect = an.kpis_por_sector(sesion_total).dropna(subset=["variacion_media_pct"])
        if sect.empty:
            st.caption("Sin PPP verificados en la sesión.")
        else:
            fig = go.Figure(go.Bar(
                x=sect["variacion_media_pct"], y=sect["sector_economico"], orientation="h",
                marker_color=[C["sube"] if v > 0 else C["baja"] for v in sect["variacion_media_pct"]],
                text=[f"{v:+.2f}%" for v in sect["variacion_media_pct"]], textposition="outside",
                customdata=sect[["con_ppp", "huecos"]].to_numpy(),
                hovertemplate="%{y}<br>Variación media %{x:+.2f}%<br>Con PPP %{customdata[0]}, huecos %{customdata[1]}<extra></extra>",
            ))
            fig.update_layout(template=PLANTILLA, height=60 + 34 * len(sect), yaxis=dict(autorange="reversed"),
                              xaxis_title="Variación PPP %")
            st.plotly_chart(fig, key="mk_sectores")

    with der:
        ui.seccion("Firma del boletín", "SHA-256 del HTML oficial del que salió cada precio")
        firmas = an.firmas_sesion(sesion_total)
        for h in firmas["hashes"]:
            ui.html(f'<div class="pb-panel" style="margin-bottom:.5rem"><div class="pb-hash">{h}</div></div>')
        if firmas["estado"] == "FIRMAS_MULTIPLES":
            st.warning("Los precios de esta sesión provienen de más de una firma: el boletín se capturó en dos "
                       "momentos con contenido distinto. La auditoría forense (Enterprise) compara cada copia "
                       "de Bronze contra la fuente oficial.")
        if firmas["url"]:
            st.link_button("Abrir boletín en bmv.com.mx", firmas["url"])
        st.caption("Cada precio conserva la firma del archivo exacto de la capa Bronze. "
                   "Las emisoras ausentes del boletín se registran como huecos y nunca se rellenan.")
