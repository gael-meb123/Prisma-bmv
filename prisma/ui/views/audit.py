"""Módulo 2.3 - Auditoría temporal t+1 a t+5 y gobernanza de la arquitectura en AWS."""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from prisma.data import analytics as an
from prisma.domain import bmv_core as core
from prisma.plans import tiene_acceso
from prisma.settings import Settings
from prisma.ui import components as ui
from prisma.ui.contexto import VistaPlan, recortar
from prisma.ui.theme import COLORES as C
from prisma.ui.theme import PLANTILLA


def _grafico_trayectoria(tray: pd.DataFrame, emisora: str) -> go.Figure:
    obs = tray[tray["estado"] == "OBSERVADO"]
    fig = go.Figure()
    fig.add_hline(y=0, line_color=C["tenue"], line_width=1)
    fig.add_trace(go.Scatter(
        x=tray["paso"], y=tray["retorno_pct"], mode="lines+markers", connectgaps=False,
        line=dict(color=C["marca"], width=2), marker=dict(size=9, color=C["marca"]),
        customdata=tray[["fecha", "ppp"]].to_numpy(), name=emisora,
        hovertemplate="%{x} (%{customdata[0]})<br>PPP $%{customdata[1]:,.2f}<br>Retorno %{y:+.2f}%<extra></extra>",
    ))
    huecos = tray[tray["estado"] == "HUECO_DOCUMENTADO"]
    if not huecos.empty:
        fig.add_trace(go.Scatter(x=huecos["paso"], y=[0] * len(huecos), mode="markers", name="Sin PPP en boletín",
                                 marker=dict(symbol="x", size=11, color=C["alerta"]),
                                 hovertemplate="%{x}: emisora ausente del boletín<extra></extra>"))
    futuros = tray[tray["estado"] == "FUTURO"]
    if not futuros.empty:
        fig.add_trace(go.Scatter(x=futuros["paso"], y=[0] * len(futuros), mode="markers", name="Sesión por venir",
                                 marker=dict(symbol="circle-open", size=9, color=C["tenue"]),
                                 hovertemplate="%{x}: pendiente<extra></extra>"))
    fig.add_vline(x=len(tray) - 1, line_dash="dot", line_color=C["info"])
    rango = obs["retorno_pct"].abs().max() if not obs.empty else 1
    fig.update_layout(template=PLANTILLA, height=330, yaxis=dict(title="Retorno vs. PPP base t0 (%)",
                      range=[-max(rango, 1) * 1.35, max(rango, 1) * 1.35]),
                      xaxis=dict(title="Sesión BMV desde la señal", type="category"))
    return fig


def _diagrama_gobernanza(s: Settings) -> go.Figure:
    bucket = s.s3_bucket or "<bucket-privado>"
    nodos = [
        ("EventBridge Scheduler", "DisparadorDiarioBMV<br>cron(45 16 ? * MON-FRI *)<br>America/Mexico_City"),
        ("Lambda recolector-diario-bmv", "Python 3.11, 512 MB, 60 s<br>fuera de VPC (sin NAT Gateway)<br>Layer AWSSDKPandas-Python311"),
        ("bmv.com.mx boletín RSS", "HTML oficial del día"),
        ("S3 Bronze", f"s3://{bucket}/bronze/<br>boletin_YYYYMMDD.html + .sha256<br>inmutable"),
        ("S3 Silver", f"s3://{bucket}/silver/precios_ppp/YYYY/MM/<br>15 emisoras, cero imputación"),
        ("S3 Gold", f"s3://{bucket}/gold/senales_g1/ y senales_g2/<br>probabilidades y consensos"),
        ("Amazon Athena", "bmv_silver_ppp, bmv_gold_senales_g2<br>resultados en athena-results/"),
        ("Terminal Prisma BMV", "Streamlit (esta aplicación)"),
        ("CloudWatch Logs", "/aws/lambda/recolector-diario-bmv<br>retención 7 días"),
        ("IAM LabRole", "lectura/escritura en el bucket<br>consulta en Athena"),
    ]
    enlaces = [(0, 1, 3), (2, 1, 3), (1, 3, 3), (3, 4, 3), (4, 5, 2), (4, 6, 2), (5, 6, 2),
               (6, 7, 2), (4, 7, 1), (1, 8, 1), (9, 1, 1)]
    colores = [C["info"], C["marca"], C["tenue"], "#B07D48", "#9AA4B5", C["alerta"], C["info"], C["marca"], C["tenue"], C["tenue"]]
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=[n for n, _ in nodos], customdata=[d for _, d in nodos], color=colores,
                  pad=18, thickness=14, line=dict(color=C["regla"], width=1),
                  hovertemplate="<b>%{label}</b><br>%{customdata}<extra></extra>"),
        link=dict(source=[a for a, _, _ in enlaces], target=[b for _, b, _ in enlaces], value=[v for *_, v in enlaces],
                  color="rgba(138,147,163,0.22)"),
    ))
    fig.update_layout(template=PLANTILLA, height=360, font=dict(size=12))
    return fig


def render(datos: dict, vp: VistaPlan, settings: Settings) -> None:
    precios = recortar(datos["precios"], "fecha", vp.fecha_corte)
    g1 = recortar(datos["g1"], "fecha_senal", vp.fecha_corte)
    g2 = recortar(datos["g2"], "fecha_senal", vp.fecha_corte) if tiene_acceso(vp.plan, "panel_g2") else pd.DataFrame()
    if not tiene_acceso(vp.plan, "g1_todos_los_modelos") and not g1.empty:
        g1 = g1[g1["id_senal"].map(an.modelo_g1) == an.MODELO_BASE_G1]
    if vp.fecha_corte is None:
        st.info("Sin sesiones disponibles.")
        return

    seg = an.seguimiento(g1, g2, precios, vp.fecha_corte)
    if seg.empty:
        st.info("Sin señales para auditar en las fechas visibles de su plan.")
        return
    seg = seg[seg["emisora"].isin(vp.emisoras)]

    st.caption(f"Mark-to-market recalculado con los PPP verificados hasta el {vp.fecha_corte}. "
               "Una señal solo se resuelve con el PPP publicado exactamente en t+5.")
    c1, c2 = st.columns(2)
    emisora = c1.selectbox("Emisora", sorted(seg["emisora"].unique()), key="au_em")
    sub = seg[seg["emisora"] == emisora]
    fechas = sorted(sub["fecha_senal"].unique(), reverse=True)
    con_precio = set(sub.loc[sub["acierto_parcial_en_curso"].notna(), "fecha_senal"])
    defecto = next((i for i, f in enumerate(fechas) if f in con_precio), 0)
    fecha = c2.selectbox("Señal emitida el", fechas, index=defecto, key="au_fecha")
    corte = sub[sub["fecha_senal"] == fecha]
    r0 = corte.iloc[0]

    cols = st.columns(4)
    with cols[0]:
        ui.kpi("Estado", str(r0["estado_resolucion"]).replace("_", " "), f"objetivo {r0['fecha_objetivo_h5']}")
    with cols[1]:
        ui.kpi("PPP base t0", f"${r0['ppp_base_t']:,.2f}", str(fecha))
    with cols[2]:
        ret = r0.get("retorno_parcial_pct")
        f_parcial = str(r0.get("fecha_parcial_reciente") or "")
        sub_txt = f"al {f_parcial}" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", f_parcial) else "sin sesiones posteriores aún"
        ui.kpi("Retorno acumulado", ui.fmt_pct(ret), sub_txt, ui.tono(ret))
    with cols[3]:
        parciales = corte["acierto_parcial_en_curso"].dropna()
        ui.kpi("Modelos acertando", f"{int(parciales.sum())} de {len(parciales)}" if len(parciales) else "—",
               "acierto_parcial_en_curso")

    izq, der = st.columns([1.35, 1])
    with izq:
        ui.seccion("Trayectoria del PPP desde t0", "las sesiones sin PPP no se interpolan")
        tray = an.trayectoria(precios, emisora, fecha, r0["fecha_objetivo_h5"], float(r0["ppp_base_t"]))
        st.plotly_chart(_grafico_trayectoria(tray, emisora), key="au_tray")
    with der:
        ui.seccion("Efectividad en curso por modelo")
        filas = []
        for _, r in corte.sort_values(["generacion", "modelo_g2"]).iterrows():
            ac = r["acierto_parcial_en_curso"]
            estado = ("Va acertando", "sube") if ac is True else (("Va fallando", "baja") if ac is False else ("Sin precio aún", "tenue"))
            if r["estado_resolucion"] == "RESUELTA_T+5":
                ok = int(r["acierto_direccional_t5"]) == 1
                estado = ("Acertó en t+5", "sube") if ok else ("Falló en t+5", "baja")
            pred = "SUBIDA" if int(r["prediccion_clase"]) == 1 else "NO_SUBIDA"
            filas.append(
                f'<div class="pb-panel" style="margin-bottom:.45rem;display:flex;justify-content:space-between;align-items:center">'
                f'<div><div>{an.NOMBRES_MODELO.get(r["modelo_g2"], r["modelo_g2"])}</div>'
                f'<div class="pb-kpi-s">P(subida) {r["probabilidad_subida"] * 100:.2f}% → {pred}</div></div>'
                f'{ui.chip(estado[0], estado[1])}</div>'
            )
        ui.html("".join(filas))

    ui.seccion("Marcador por modelo", "todas las señales visibles para su plan")
    marc = an.marcador_modelos(seg)
    st.dataframe(
        marc, hide_index=True,
        column_config={
            "generacion": "Gen.", "modelo": "Modelo", "senales": "Señales", "en_seguimiento": "Con precio parcial",
            "aciertos_parciales": "Aciertos parciales",
            "tasa_parcial_pct": st.column_config.NumberColumn("Tasa parcial", format="%.1f%%"),
            "resueltas_t5": "Resueltas t+5", "aciertos_t5": "Aciertos t+5",
            "brier_t5": st.column_config.NumberColumn("Brier t+5", format="%.4f"),
        },
    )
    st.caption("Una tasa parcial con pocas señales es inestable: un acierto o error cambia decenas de puntos. "
               "La métrica que cuenta es la resolución en t+5 y su Brier score.")

    # --- Gobernanza ---------------------------------------------------------
    ui.seccion("Gobernanza en la nube", "pase el cursor sobre cada componente para ver su configuración")
    st.plotly_chart(_diagrama_gobernanza(settings), key="au_gob")
    _controles_calidad(datos, precios)


def _controles_calidad(datos: dict, precios: pd.DataFrame) -> None:
    checks = []
    inc = an.inconsistencias_consenso(datos["g2"]) if not datos["g2"].empty else pd.DataFrame()
    checks.append(("Etiquetas de consenso coherentes con las clases", inc.empty,
                   "sin discrepancias" if inc.empty else f"{len(inc)} discrepancias"))
    multiples = [f for f, s in precios.groupby("fecha") if an.firmas_sesion(s)["estado"] == "FIRMAS_MULTIPLES"]
    checks.append(("Una sola firma SHA-256 por sesión", not multiples,
                   "todas las sesiones" if not multiples else f"revisar {', '.join(multiples)}"))
    imputados = precios[(precios["estado_captura"] == core.ESTADO_HUECO) & precios["ppp_bmv_mxn"].notna()]
    checks.append(("Huecos sin valores imputados", imputados.empty,
                   f"{int((precios['estado_captura'] == core.ESTADO_HUECO).sum())} huecos conservados"))
    anuladas = datos["g1"][~datos["g1"]["valida"]] if not datos["g1"].empty else pd.DataFrame()
    checks.append(("Señales anuladas excluidas del consenso", True, f"{len(anuladas)} anuladas"))
    filas = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:.35rem 0;border-bottom:1px solid var(--regla)">'
        f'<span>{n}</span>{ui.chip(d, "sube" if ok else "baja")}</div>'
        for n, ok, d in checks
    )
    ui.html(f'<div class="pb-panel"><div class="pb-kpi-l">Controles de integridad calculados sobre los datos cargados</div>{filas}</div>')
