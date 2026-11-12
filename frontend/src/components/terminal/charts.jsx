/**
 * Gráficas de la terminal web. Son las mismas que tenía la terminal Streamlit, con la paleta
 * de la página (azul marino + turquesa). Verde y rojo indican dirección; ámbar, huecos.
 */
import React from "react";
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

const Plot = createPlotlyComponent(Plotly);

export const COLOR = {
  navy: "#062c50",
  teal: "#079baa",
  tealSoft: "rgba(7, 155, 170, 0.12)",
  up: "#0e9f6e",
  down: "#d64545",
  warn: "#d97706",
  grid: "#e6edf3",
  axis: "#5f7389",
  muted: "#94a3b8",
};

const FONT = { family: "Manrope, sans-serif", size: 12, color: COLOR.axis };
const MONO = { family: "JetBrains Mono, ui-monospace, monospace", size: 11, color: COLOR.axis };

function base(extra = {}) {
  return {
    autosize: true,
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: FONT,
    margin: { l: 12, r: 24, t: 10, b: 40 },
    hoverlabel: { bgcolor: "#ffffff", bordercolor: COLOR.grid, font: { ...FONT, color: COLOR.navy } },
    showlegend: false,
    ...extra,
  };
}

const CONFIG = { responsive: true, displayModeBar: false };

function Chart({ data, layout, height }) {
  return (
    <Plot
      data={data}
      layout={{ ...layout, height }}
      config={CONFIG}
      style={{ width: "100%", height }}
      useResizeHandler
    />
  );
}

/* Variación media del PPP por sector -------------------------------------- */
export function SectoresChart({ sectores = [] }) {
  const filas = sectores.filter((s) => s.variacion_media_pct != null).sort((a, b) => b.variacion_media_pct - a.variacion_media_pct);
  if (!filas.length) return null;
  const height = 70 + 34 * filas.length;
  const vals = filas.map((s) => s.variacion_media_pct);
  const span = Math.max(Math.max(...vals, 0) - Math.min(...vals, 0), 0.5);
  const rango = [Math.min(...vals, 0) - span * 0.28, Math.max(...vals, 0) + span * 0.28];
  return (
    <Chart
      height={height}
      data={[
        {
          type: "bar",
          orientation: "h",
          x: filas.map((s) => s.variacion_media_pct),
          y: filas.map((s) => s.sector),
          marker: { color: filas.map((s) => (s.variacion_media_pct >= 0 ? COLOR.up : COLOR.down)), line: { width: 0 } },
          text: filas.map((s) => `${s.variacion_media_pct > 0 ? "+" : ""}${s.variacion_media_pct.toFixed(2)}%`),
          textposition: "outside",
          textfont: MONO,
          cliponaxis: false,
          customdata: filas.map((s) => [s.con_ppp, s.huecos]),
          hovertemplate: "<b>%{y}</b><br>Variación media %{x:+.2f}%<br>Con PPP %{customdata[0]} · huecos %{customdata[1]}<extra></extra>",
        },
      ]}
      layout={base({
        margin: { l: 10, r: 56, t: 6, b: 36 },
        bargap: 0.38,
        xaxis: { range: rango, zeroline: true, zerolinecolor: COLOR.muted, gridcolor: COLOR.grid, ticksuffix: "%", tickfont: MONO, title: { text: "Variación del PPP vs. sesión anterior", font: { size: 11 } } },
        yaxis: { autorange: "reversed", automargin: true, tickfont: { ...FONT, color: COLOR.navy } },
      })}
    />
  );
}

/* Probabilidad de subida por modelo (umbral 50 %) -------------------------- */
export function ProbabilidadesChart({ modelos = [] }) {
  if (!modelos.length) return null;
  const filas = [...modelos].sort((a, b) => (a.generacion === b.generacion ? a.nombre.localeCompare(b.nombre) : a.generacion < b.generacion ? 1 : -1));
  const pct = filas.map((m) => m.probabilidad * 100);
  const lo = Math.max(0, Math.floor(Math.min(...pct, 50) / 5) * 5 - 5);
  const hi = Math.min(100, Math.ceil(Math.max(...pct, 50) / 5) * 5 + 8);
  const height = 60 + 40 * filas.length;
  return (
    <Chart
      height={height}
      data={[
        {
          type: "bar",
          orientation: "h",
          x: pct,
          y: filas.map((m) => m.nombre),
          marker: {
            color: filas.map((m) => (!m.valida ? "#cbd5e1" : m.probabilidad >= 0.5 ? COLOR.up : COLOR.down)),
          },
          text: filas.map((m) => `${(m.probabilidad * 100).toFixed(2)}%${m.valida ? "" : " · anulada"}`),
          textposition: "outside",
          textfont: MONO,
          cliponaxis: false,
          hovertemplate: "<b>%{y}</b><br>P(PPP t+5 > PPP t) = %{x:.2f}%<extra></extra>",
        },
      ]}
      layout={base({
        margin: { l: 10, r: 70, t: 10, b: 40 },
        bargap: 0.35,
        shapes: [{ type: "line", x0: 50, x1: 50, yref: "paper", y0: 0, y1: 1, line: { color: COLOR.navy, width: 1.5, dash: "dot" } }],
        annotations: [{ x: 50, y: 1.02, yref: "paper", text: "50%", showarrow: false, font: { ...MONO, color: COLOR.navy } }],
        xaxis: { range: [lo, hi], gridcolor: COLOR.grid, ticksuffix: "%", tickfont: MONO, title: { text: "Probabilidad de que el PPP suba en 5 sesiones", font: { size: 11 } } },
        yaxis: { autorange: "reversed", automargin: true, tickfont: { ...FONT, color: COLOR.navy } },
      })}
    />
  );
}

/* Cascada del log-odds (factor clave) -------------------------------------- */
const NOMBRES_VAR = {
  intercepto: "Intercepto",
  ret_10: "Retorno 10 sesiones",
  ret_10_rel_panel: "Retorno relativo al panel",
  volatilidad_20: "Volatilidad 20 sesiones",
};

export function ContribucionesChart({ contribuciones = {} }) {
  const claves = Object.keys(contribuciones);
  if (!claves.length) return null;
  const total = claves.reduce((s, k) => s + (contribuciones[k] || 0), 0);
  const p = 1 / (1 + Math.exp(-total));
  let acum = 0;
  const puntos = [0];
  claves.forEach((k) => {
    acum += contribuciones[k] || 0;
    puntos.push(acum);
  });
  const ancho = Math.max(Math.max(...puntos) - Math.min(...puntos), 0.01);
  const rango = [Math.min(...puntos) - ancho * 0.3, Math.max(...puntos) + ancho * 0.3];
  return (
    <Chart
      height={250}
      data={[
        {
          type: "waterfall",
          orientation: "h",
          y: [...claves.map((k) => NOMBRES_VAR[k] || k), "Total (log-odds)"],
          x: [...claves.map((k) => contribuciones[k]), 0],
          measure: [...claves.map(() => "relative"), "total"],
          increasing: { marker: { color: COLOR.up } },
          decreasing: { marker: { color: COLOR.down } },
          totals: { marker: { color: COLOR.teal } },
          connector: { line: { color: COLOR.grid } },
          text: [...claves.map((k) => `${contribuciones[k] >= 0 ? "+" : ""}${contribuciones[k].toFixed(4)}`), `${total >= 0 ? "+" : ""}${total.toFixed(4)}`],
          textposition: "outside",
          textfont: MONO,
          cliponaxis: false,
          hovertemplate: "%{y}: %{x:+.4f}<extra></extra>",
        },
      ]}
      layout={base({
        margin: { l: 10, r: 70, t: 10, b: 44 },
        xaxis: { range: rango, gridcolor: COLOR.grid, tickfont: MONO, zeroline: true, zerolinecolor: COLOR.muted, title: { text: `Aporte al log-odds · total ${total >= 0 ? "+" : ""}${total.toFixed(4)} ⇒ p = ${(p * 100).toFixed(2)}%`, font: { size: 11 } } },
        yaxis: { autorange: "reversed", automargin: true, tickfont: { ...FONT, color: COLOR.navy } },
      })}
    />
  );
}

/* Trayectoria del PPP de t0 a t+5 ------------------------------------------ */
export function TrayectoriaChart({ trayectoria = [], emisora = "" }) {
  if (!trayectoria.length) return null;
  const obs = trayectoria.filter((t) => t.estado === "OBSERVADO");
  const huecos = trayectoria.filter((t) => t.estado === "HUECO_DOCUMENTADO");
  const futuros = trayectoria.filter((t) => t.estado === "FUTURO");
  const rango = Math.max(1, ...obs.map((t) => Math.abs(t.retorno_pct || 0))) * 1.35;
  return (
    <Chart
      height={320}
      data={[
        {
          type: "scatter",
          mode: "lines+markers",
          connectgaps: false,
          x: trayectoria.map((t) => t.paso),
          y: trayectoria.map((t) => t.retorno_pct),
          line: { color: COLOR.teal, width: 3, shape: "spline" },
          marker: { size: 10, color: COLOR.navy, line: { color: COLOR.teal, width: 2 } },
          fill: "tozeroy",
          fillcolor: COLOR.tealSoft,
          customdata: trayectoria.map((t) => [t.fecha, t.ppp]),
          name: emisora,
          hovertemplate: "<b>%{x}</b> (%{customdata[0]})<br>PPP $%{customdata[1]:,.2f}<br>Retorno %{y:+.2f}%<extra></extra>",
        },
        {
          type: "scatter",
          mode: "markers",
          x: huecos.map((t) => t.paso),
          y: huecos.map(() => 0),
          marker: { symbol: "x", size: 13, color: COLOR.warn },
          name: "Sin PPP en el boletín",
          hovertemplate: "%{x}: la emisora no apareció en el boletín (no se rellena)<extra></extra>",
        },
        {
          type: "scatter",
          mode: "markers",
          x: futuros.map((t) => t.paso),
          y: futuros.map(() => 0),
          marker: { symbol: "circle-open", size: 11, color: COLOR.muted, line: { width: 2 } },
          name: "Sesión por venir",
          customdata: futuros.map((t) => t.fecha),
          hovertemplate: "%{x} (%{customdata}): pendiente<extra></extra>",
        },
      ]}
      layout={base({
        showlegend: true,
        legend: { orientation: "h", x: 0, y: 1.12, font: { size: 11 } },
        margin: { l: 56, r: 20, t: 30, b: 44 },
        shapes: [
          { type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: COLOR.navy, width: 1 } },
          { type: "line", x0: "t+5", x1: "t+5", yref: "paper", y0: 0, y1: 1, line: { color: COLOR.teal, width: 1.5, dash: "dot" } },
        ],
        xaxis: { type: "category", categoryorder: "array", categoryarray: trayectoria.map((t) => t.paso), tickfont: MONO, title: { text: "Sesión BMV desde la señal", font: { size: 11 } } },
        yaxis: { range: [-rango, rango], gridcolor: COLOR.grid, ticksuffix: "%", tickfont: MONO, zeroline: false, title: { text: "Retorno vs. PPP base", font: { size: 11 } } },
      })}
    />
  );
}

/* Marcador por modelo ------------------------------------------------------- */
export function MarcadorChart({ modelos = [] }) {
  if (!modelos.length) return null;
  const nombres = modelos.map((m) => m.nombre);
  const tasaT5 = modelos.map((m) => (m.resueltas_t5 ? (m.aciertos_t5 / m.resueltas_t5) * 100 : null));
  const height = 80 + 44 * modelos.length;
  return (
    <Chart
      height={height}
      data={[
        {
          type: "bar",
          orientation: "h",
          name: "Aciertos parciales (en curso)",
          y: nombres,
          x: modelos.map((m) => m.tasa_parcial_pct),
          marker: { color: COLOR.teal },
          customdata: modelos.map((m) => [m.aciertos_parciales, m.en_seguimiento]),
          hovertemplate: "<b>%{y}</b><br>Parcial: %{x:.1f}% (%{customdata[0]} de %{customdata[1]})<extra></extra>",
        },
        {
          type: "bar",
          orientation: "h",
          name: "Aciertos en t+5 (resueltas)",
          y: nombres,
          x: tasaT5,
          marker: { color: COLOR.navy },
          customdata: modelos.map((m) => [m.aciertos_t5, m.resueltas_t5, m.brier_t5]),
          hovertemplate: "<b>%{y}</b><br>t+5: %{x:.1f}% (%{customdata[0]} de %{customdata[1]})<br>Brier %{customdata[2]:.4f}<extra></extra>",
        },
      ]}
      layout={base({
        showlegend: true,
        barmode: "group",
        bargap: 0.3,
        legend: { orientation: "h", x: 0, y: 1.0, yanchor: "bottom", font: { size: 11 } },
        margin: { l: 10, r: 20, t: 56, b: 40 },
        shapes: [{ type: "line", x0: 50, x1: 50, yref: "paper", y0: 0, y1: 1, line: { color: COLOR.muted, width: 1, dash: "dot" } }],
        xaxis: { range: [0, 100], ticksuffix: "%", gridcolor: COLOR.grid, tickfont: MONO },
        yaxis: { autorange: "reversed", automargin: true, tickfont: { ...FONT, color: COLOR.navy } },
      })}
    />
  );
}

/* Gobernanza del lakehouse (Sankey) ---------------------------------------- */
const COLOR_NODOS = [COLOR.teal, COLOR.navy, "#94a3b8", "#b07d48", "#8a9bb0", "#d4a017", COLOR.teal, COLOR.navy, "#94a3b8", "#94a3b8"];

export function GobernanzaSankey({ nodos = [], enlaces = [] }) {
  if (!nodos.length) return null;
  return (
    <Chart
      height={380}
      data={[
        {
          type: "sankey",
          arrangement: "snap",
          node: {
            label: nodos.map((n) => n.nombre),
            customdata: nodos.map((n) => n.detalle),
            color: nodos.map((_, i) => COLOR_NODOS[i % COLOR_NODOS.length]),
            pad: 18,
            thickness: 16,
            line: { color: "#ffffff", width: 1 },
            hovertemplate: "<b>%{label}</b><br>%{customdata}<extra></extra>",
          },
          link: {
            source: enlaces.map((e) => e.origen),
            target: enlaces.map((e) => e.destino),
            value: enlaces.map((e) => e.valor),
            color: "rgba(7, 155, 170, 0.16)",
          },
        },
      ]}
      layout={base({ margin: { l: 10, r: 10, t: 10, b: 10 }, font: { ...FONT, color: COLOR.navy } })}
    />
  );
}

/* Diagrama de confiabilidad (calibración) ----------------------------------- */
export function CalibracionChart({ bins = [], etiqueta = "Modelo" }) {
  if (!bins.length) return null;
  const xs = bins.map((b) => b.prob_media);
  const ys = bins.map((b) => b.frecuencia_observada);
  const lo = Math.min(...xs, ...ys) - 0.02;
  const hi = Math.max(...xs, ...ys) + 0.02;
  return (
    <Chart
      height={300}
      data={[
        { type: "scatter", mode: "lines", x: [lo, hi], y: [lo, hi], name: "Calibración ideal", line: { color: COLOR.muted, dash: "dash", width: 1.5 }, hoverinfo: "skip" },
        {
          type: "scatter",
          mode: "lines+markers",
          x: xs,
          y: ys,
          name: etiqueta,
          line: { color: COLOR.teal, width: 3 },
          // El tamaño del punto crece con el número de observaciones del tramo.
          marker: { color: COLOR.navy, size: bins.map((b) => (b.n ? Math.max(7, Math.min(26, 4 + Math.sqrt(b.n) * 0.7)) : 8)), line: { color: "#ffffff", width: 1.5 } },
          customdata: bins.map((b) => b.n ?? "—"),
          hovertemplate: "Predicha %{x:.1%}<br>Observada %{y:.1%}<br>Observaciones: %{customdata}<extra></extra>",
        },
      ]}
      layout={base({
        showlegend: true,
        legend: { orientation: "h", x: 0, y: 1.1, font: { size: 11 } },
        margin: { l: 56, r: 16, t: 30, b: 46 },
        xaxis: { range: [lo, hi], gridcolor: COLOR.grid, tickfont: MONO, tickformat: ".0%", title: { text: "Probabilidad predicha", font: { size: 11 } } },
        yaxis: { range: [lo, hi], gridcolor: COLOR.grid, tickfont: MONO, tickformat: ".0%", title: { text: "Frecuencia observada", font: { size: 11 } } },
      })}
    />
  );
}
