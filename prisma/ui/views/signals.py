"""Módulo 2.2 - Motor de señales: semáforo de consenso, probabilidades por modelo y factor clave."""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from prisma.data import analytics as an
from prisma.domain import bmv_core as core
from prisma.plans import EMISORAS_SENALES, ENTERPRISE, tiene_acceso
from prisma.ui import components as ui
from prisma.ui.contexto import VistaPlan, recortar
from prisma.ui.theme import COLORES as C
from prisma.ui.theme import PLANTILLA

EMISORAS = EMISORAS_SENALES[ENTERPRISE]


def _grafico_probabilidades(tabla: pd.DataFrame) -> go.Figure:
    t = tabla.sort_values(["generacion", "nombre"], ascending=[False, True])
    colores, textos = [], []
    for _, r in t.iterrows():
        if not r["valida"]:
            colores.append(C["regla"])
            textos.append(f"{r['probabilidad'] * 100:.2f}%  anulada")
        else:
            colores.append(C["sube"] if r["probabilidad"] >= 0.5 else C["baja"])
            textos.append(f"{r['probabilidad'] * 100:.2f}%")
    fig = go.Figure(go.Bar(
        x=t["probabilidad"] * 100, y=t["nombre"], orientation="h", marker_color=colores,
        text=textos, textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>P(PPP t+5 > PPP t) = %{x:.2f}%<extra></extra>",
    ))
    fig.add_vline(x=50, line_dash="dot", line_color=C["marca"])
    lo = max(0, math.floor(min(t["probabilidad"].min() * 100, 50) / 5) * 5 - 5)
    hi = min(100, math.ceil(max(t["probabilidad"].max() * 100, 50) / 5) * 5 + 8)
    fig.update_layout(template=PLANTILLA, height=70 + 42 * len(t), xaxis=dict(range=[lo, hi], title="Probabilidad de subida a 5 sesiones (%)"),
                      yaxis=dict(autorange="reversed"), showlegend=False)
    return fig


def _grafico_contribuciones(contrib: dict[str, float]) -> go.Figure:
    nombres = {"intercepto": "Intercepto", "ret_10": "ret_10", "ret_10_rel_panel": "ret_10_rel_panel",
               "volatilidad_20": "volatilidad_20"}
    claves = list(contrib)
    fig = go.Figure(go.Waterfall(
        orientation="h", y=[nombres.get(k, k) for k in claves] + ["Log-odds total"],
        x=[contrib[k] for k in claves] + [0], measure=["relative"] * len(claves) + ["total"],
        increasing=dict(marker=dict(color=C["sube"])), decreasing=dict(marker=dict(color=C["baja"])),
        totals=dict(marker=dict(color=C["marca"])), connector=dict(line=dict(color=C["regla"])),
        hovertemplate="%{y}: %{x:+.4f}<extra></extra>",
    ))
    total = sum(contrib.values())
    fig.update_layout(template=PLANTILLA, height=240, yaxis=dict(autorange="reversed"),
                      xaxis_title=f"Aporte al log-odds (total {total:+.4f} ⇒ p = {1 / (1 + math.exp(-total)):.2%})")
    return fig


def render(datos: dict, vp: VistaPlan) -> None:
    g1 = recortar(datos["g1"], "fecha_senal", vp.fecha_corte)
    g2 = recortar(datos["g2"], "fecha_senal", vp.fecha_corte)
    puede_g2 = tiene_acceso(vp.plan, "panel_g2")

    st.caption(r"Objetivo de todos los modelos: $Y_t = \mathbb{1}(\mathrm{PPP}_{t+5} > \mathrm{PPP}_t)$, "
               "la dirección del PPP oficial cinco sesiones hábiles BMV después de la señal.")
    c1, c2 = st.columns([1, 1])
    emisora = c1.selectbox("Emisora", EMISORAS,
                           format_func=lambda e: e if e in vp.emisoras else f"{e} (Professional)", key="sg_em")
    if emisora not in vp.emisoras:
        ui.bloqueo("panel_g2",
                   f"La señal de {emisora} sale del panel multiemisora de 2ª generación, que compara cada emisora "
                   "contra el resto del panel con el factor ret_10_rel_panel.", "sg_em")
        return

    fechas = sorted(set(g1[g1["emisora"] == emisora]["fecha_senal"]) |
                    (set(g2[g2["emisora"] == emisora]["fecha_senal"]) if puede_g2 else set()), reverse=True)
    if not fechas:
        st.info("No hay señales emitidas para esta emisora en las fechas visibles de su plan.")
        return
    fecha = c2.selectbox("Fecha de la señal", fechas, key="sg_fecha")

    tabla = an.tabla_probabilidades(g1, g2, emisora, fecha, incluir_g2=puede_g2,
                                    solo_base_g1=not tiene_acceso(vp.plan, "g1_todos_los_modelos"))
    if tabla.empty:
        st.info("Sin probabilidades registradas para esta combinación.")
        return
    consensos = an.consenso_por_generacion(tabla)

    # --- Semáforo -----------------------------------------------------------
    fila_g2 = g2[(g2["emisora"] == emisora) & (g2["fecha_senal"] == fecha)] if puede_g2 else pd.DataFrame()
    cols = st.columns(4)
    with cols[0]:
        if tiene_acceso(vp.plan, "consenso_semaforo"):
            todas = tabla[tabla["valida"]]["clase"].tolist()
            ui.semaforo(an.consenso_desde_clases(todas), "Consenso global (G1 + G2)")
        else:
            r = tabla.iloc[0]
            ui.semaforo(an.SUBIDA if r["clase"] == 1 else an.NO_SUBIDA, "Modelo base G1")
    with cols[1]:
        if "G1" in consensos and tiene_acceso(vp.plan, "consenso_semaforo"):
            ui.semaforo(consensos["G1"], "1ª generación (individual)")
        else:
            ui.kpi("1ª generación", f"{tabla.iloc[0]['probabilidad'] * 100:.2f}%", "modelo base, P(subida)")
    with cols[2]:
        if "G2" in consensos:
            ui.semaforo(consensos["G2"], "2ª generación (panel)")
        else:
            ui.kpi("2ª generación", "—", "panel multiemisora en Professional", "tenue")
    with cols[3]:
        if not fila_g2.empty:
            r0 = fila_g2.iloc[0]
            ui.kpi("PPP base t0", f"${r0['ppp_base_t']:,.2f}", f"objetivo {r0['fecha_objetivo_h5']}")
        else:
            r1 = g1[(g1["emisora"] == emisora) & (g1["fecha_senal"] == fecha)].iloc[0]
            ui.kpi("PPP base t0", f"${r1['ppp_base_mxn']:,.2f}", f"objetivo {r1['fecha_objetivo_h5']}")

    if (tabla["valida"] == False).any():  # noqa: E712
        st.caption("Las barras grises son señales anuladas por gobernanza (insumos sin fuente documentada); "
                   "se muestran por transparencia y no cuentan para el consenso.")

    izq, der = st.columns([1.25, 1])
    with izq:
        ui.seccion("Probabilidad de subida por modelo", "la línea punteada marca el umbral de 50%")
        st.plotly_chart(_grafico_probabilidades(tabla), key="sg_probs")

    with der:
        ui.seccion("Factor clave: ret_10_rel_panel", "retorno a 10 sesiones menos la media del panel")
        if not tiene_acceso(vp.plan, "ret_10_rel_panel"):
            ui.bloqueo("ret_10_rel_panel", "La descomposición de la señal y el retorno relativo frente al panel "
                       "forman parte del análisis de 2ª generación.", "sg_rel")
        elif fila_g2.empty:
            st.caption("Esta fecha no tiene señal de panel G2 para la emisora (ventana de 21 sesiones incompleta).")
        else:
            modelo = st.selectbox("Modelo a descomponer", fila_g2["modelo_g2"].tolist(),
                                  format_func=lambda m: an.NOMBRES_MODELO.get(m, m), key="sg_mod")
            fila = fila_g2[fila_g2["modelo_g2"] == modelo].iloc[0]
            exp = an.explicar_factor(datos["modelos"], fila)
            a, b = st.columns(2)
            with a:
                ui.kpi("ret_10_rel_panel", f"{exp.ret_rel_pct:+.2f} pp", "frente a la media del panel",
                       ui.tono(exp.ret_rel_pct))
            with b:
                ui.kpi("Desviación vs. su historia", "—" if exp.z_rel is None else f"{exp.z_rel:+.2f} σ",
                       "escalador oficial de la emisora")
            st.write(exp.lectura)
            if exp.contribuciones:
                st.plotly_chart(_grafico_contribuciones(exp.contribuciones), key="sg_contrib")
                st.caption("Descomposición con los parámetros congelados del registro oficial. G2-V3 se reentrena "
                           "con la historia purgada hasta cada corte, por lo que su probabilidad registrada puede "
                           "diferir ligeramente de esta reconstrucción.")

    # --- Control de calidad ---------------------------------------------------
    if puede_g2 and not g2.empty:
        inc = an.inconsistencias_consenso(g2)
        with st.expander("Control de calidad del registro de señales"):
            if inc.empty:
                st.write("Todas las etiquetas de consenso registradas coinciden con las clases de cada modelo.")
            else:
                st.write("Etiquetas registradas que no coinciden con las clases de los modelos:")
                st.dataframe(inc, hide_index=True)
            st.write(f"Variables del panel G2: {', '.join(core.VARIABLES_G2)}. "
                     "Ventana estricta de 21 sesiones con PPP verificado; sin ventana completa no hay señal.")
