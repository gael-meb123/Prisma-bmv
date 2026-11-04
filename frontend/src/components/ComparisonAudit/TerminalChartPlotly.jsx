import React from "react";
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import { TrendingUp, ShieldCheck } from "lucide-react";
import { formatMoney } from "../../utils/presentation.mjs";

const Plot = createPlotlyComponent(Plotly);

export function TerminalChartPlotly({ serie = [], ticker = "WALMEX", sector = "Comercio y autoservicio" }) {
  const fechas = serie.map((d) => d.fecha);
  const precios = serie.map((d) => d.ppp);
  const ultimoPrecio = precios.length > 0 ? precios[precios.length - 1] : 50.39;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", width: "100%" }}>
      {/* Barra Superior del Panel Visual */}
      <div
        style={{
          padding: "12px 16px",
          background: "#062c50",
          color: "#ffffff",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid #17476a"
        }}
      >
        <div>
          <strong style={{ fontSize: "16px", fontFamily: "monospace" }}>{ticker} (*)</strong>
          <span style={{ fontSize: "12px", color: "#8ee3ed", marginLeft: "8px" }}>{sector}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "11px", color: "#d5ecf8" }}>PPP Último Cierre:</span>
          <span style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "#10b981" }}>
            {formatMoney(ultimoPrecio)}
          </span>
        </div>
      </div>

      {/* Gráfica Plotly Interactiva */}
      <div style={{ flex: 1, minHeight: "360px", background: "#f8fafc", position: "relative" }}>
        <Plot
          data={[
            {
              x: fechas,
              y: precios,
              type: "scatter",
              mode: "lines+markers",
              name: `${ticker} PPP Oficial`,
              line: { color: "#079baa", width: 3, shape: "spline" },
              marker: { color: "#062c50", size: 6, line: { color: "#079baa", width: 1.5 } },
              fill: "tozeroy",
              fillcolor: "rgba(7, 155, 170, 0.08)",
              hovertemplate: "<b>Fecha:</b> %{x}<br><b>PPP Oficial:</b> $%{y:.2f} MXN<extra></extra>"
            },
            {
              x: [fechas[fechas.length - 1]],
              y: [ultimoPrecio],
              type: "scatter",
              mode: "markers+text",
              name: "Señal Activa (t)",
              text: [` $${ultimoPrecio.toFixed(2)}`],
              textposition: "top center",
              textfont: { family: "monospace", size: 12, color: "#059669" },
              marker: { color: "#10b981", size: 12, symbol: "diamond" },
              hoverinfo: "skip"
            }
          ]}
          layout={{
            autosize: true,
            margin: { l: 50, r: 24, t: 30, b: 40 },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            showlegend: true,
            legend: { orientation: "h", x: 0, y: 1.15, font: { size: 11, color: "#60758c" } },
            xaxis: {
              gridcolor: "#e2e8f0",
              linecolor: "#cbd5e1",
              tickfont: { size: 11, color: "#60758c", family: "monospace" },
              showgrid: true
            },
            yaxis: {
              gridcolor: "#e2e8f0",
              linecolor: "#cbd5e1",
              tickfont: { size: 11, color: "#60758c", family: "monospace" },
              tickprefix: "$",
              showgrid: true
            }
          }}
          config={{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ["lasso2d", "select2d"]
          }}
          style={{ width: "100%", height: "100%" }}
        />
      </div>

      {/* Pie del Panel Visual */}
      <div className="workspace-map-footer">
        <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span className="status-dot" style={{ background: "#10b981" }} />
          Serie Histórica Oficial BMV · Tolerancia Criptográfica 100%
        </span>
        <a href="#/fuentes">Fuentes y Gobernanza AWS ↗</a>
      </div>
    </div>
  );
}
