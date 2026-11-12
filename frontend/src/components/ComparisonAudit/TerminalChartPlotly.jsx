import React from "react";
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import { formatMoney } from "../../utils/presentation.mjs";

const Plot = createPlotlyComponent(Plotly);

/**
 * Gráfica principal de la terminal: PPP oficial sesión por sesión.
 * Conserva el diseño original (franja azul, línea turquesa suavizada con relleno y rombo en la
 * señal activa). Acepta cualquier emisora; las sesiones sin PPP verificado llegan con ppp=null y se
 * dibujan como un corte en la línea (no se rellenan).
 */
export function TerminalChartPlotly({
  serie = [],
  ticker = "WALMEX",
  sector = "",
  height = 380,
  action = null,
}) {
  const fechas = serie.map((d) => d.fecha);
  const precios = serie.map((d) => (d.ppp == null ? null : d.ppp));
  const conPrecio = serie.filter((d) => d.ppp != null);
  const ultimo = conPrecio.length ? conPrecio[conPrecio.length - 1] : null;
  const huecos = serie.filter((d) => d.ppp == null);
  // Tramos de sesiones consecutivas con PPP (un hueco corta el tramo).
  const tramos = [];
  serie.forEach((d) => {
    if (d.ppp == null) {
      if (tramos.length && tramos[tramos.length - 1].length) tramos.push([]);
      return;
    }
    if (!tramos.length) tramos.push([]);
    tramos[tramos.length - 1].push(d);
  });
  // Rango del eje fijado a los precios: el relleno "tozeroy" no debe arrastrar el eje hasta 0.
  const valores = conPrecio.map((d) => d.ppp);
  const minimo = valores.length ? Math.min(...valores) : 0;
  const maximo = valores.length ? Math.max(...valores) : 1;
  const holgura = Math.max((maximo - minimo) * 0.12, maximo * 0.004, 0.01);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", width: "100%" }}>
      {/* Barra superior del panel visual */}
      <div
        style={{
          padding: "12px 16px",
          background: "#062c50",
          color: "#ffffff",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "10px",
          flexWrap: "wrap",
        }}
      >
        <div>
          <strong style={{ fontSize: "16px", fontFamily: "monospace" }}>{ticker}</strong>
          {sector && <span style={{ fontSize: "12px", color: "#8ee3ed", marginLeft: "8px" }}>{sector}</span>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "11px", color: "#d5ecf8" }}>PPP última sesión{ultimo ? ` (${ultimo.fecha})` : ""}:</span>
          <span style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "#10b981" }}>
            {ultimo ? formatMoney(ultimo.ppp) : "—"}
          </span>
          {action}
        </div>
      </div>

      {/* Gráfica Plotly interactiva */}
      <div style={{ flex: 1, minHeight: `${height}px`, background: "#f8fafc", position: "relative" }}>
        <Plot
          data={[
            // Relleno por tramo continuo: así el área no cruza por encima de un hueco.
            ...tramos.map((t, i) => ({
              x: t.map((d) => d.fecha),
              y: t.map((d) => d.ppp),
              type: "scatter",
              mode: "none",
              fill: "tozeroy",
              fillcolor: "rgba(7, 155, 170, 0.08)",
              line: { shape: "spline" },
              hoverinfo: "skip",
              showlegend: false,
              name: `tramo-${i}`,
            })),
            {
              x: fechas,
              y: precios,
              type: "scatter",
              mode: "lines+markers",
              connectgaps: false,
              name: `${ticker} PPP oficial`,
              line: { color: "#079baa", width: 3, shape: "spline" },
              marker: { color: "#062c50", size: 6, line: { color: "#079baa", width: 1.5 } },
              hovertemplate: "<b>Fecha:</b> %{x}<br><b>PPP oficial:</b> $%{y:.2f} MXN<extra></extra>",
            },
            ...(huecos.length
              ? [
                  {
                    x: huecos.map((d) => d.fecha),
                    y: huecos.map(() => null),
                    type: "scatter",
                    mode: "markers",
                    name: "Sin PPP en el boletín",
                    marker: { color: "#d97706", size: 9, symbol: "x" },
                    hoverinfo: "skip",
                    visible: "legendonly",
                  },
                ]
              : []),
            ...(ultimo
              ? [
                  {
                    x: [ultimo.fecha],
                    y: [ultimo.ppp],
                    type: "scatter",
                    mode: "markers+text",
                    name: "Señal activa (t)",
                    text: [` $${Number(ultimo.ppp).toFixed(2)}`],
                    textposition: "top center",
                    textfont: { family: "monospace", size: 12, color: "#059669" },
                    marker: { color: "#10b981", size: 12, symbol: "diamond" },
                    hoverinfo: "skip",
                  },
                ]
              : []),
          ]}
          layout={{
            autosize: true,
            height,
            margin: { l: 56, r: 24, t: 30, b: 40 },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            showlegend: true,
            legend: { orientation: "h", x: 0, y: 1.12, font: { size: 11, color: "#60758c" } },
            xaxis: {
              gridcolor: "#e2e8f0",
              linecolor: "#cbd5e1",
              tickfont: { size: 11, color: "#60758c", family: "monospace" },
              showgrid: true,
            },
            yaxis: {
              gridcolor: "#e2e8f0",
              linecolor: "#cbd5e1",
              tickfont: { size: 11, color: "#60758c", family: "monospace" },
              tickprefix: "$",
              showgrid: true,
              range: [minimo - holgura, maximo + holgura],
            },
          }}
          config={{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ["lasso2d", "select2d"],
          }}
          style={{ width: "100%", height: "100%" }}
          useResizeHandler
        />
      </div>

      {/* Pie del panel visual */}
      <div className="workspace-map-footer">
        <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span className="status-dot" style={{ background: "#10b981" }} />
          Serie histórica oficial BMV · {conPrecio.length} sesiones con PPP
          {huecos.length ? ` · ${huecos.length} sin dato (no se rellenan)` : ""}
        </span>
        <a href="#/fuentes">Fuentes y gobernanza ↗</a>
      </div>
    </div>
  );
}
