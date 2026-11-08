import React, { useState, useEffect } from "react";
import { api } from "../../services/api.mjs";
import { TrendingUp, TrendingDown, Activity, Globe, DollarSign, Percent, ShieldCheck, X, Cloud, Zap } from "lucide-react";
import { formatMoney, formatPct } from "../../utils/presentation.mjs";

export function MacroTicker() {
  const [data, setData] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    async function loadStream() {
      const stream = await api.getMacroStream();
      setData(stream);
    }
    loadStream();
    // Refresco periódico cada 30 segundos en la terminal
    const interval = setInterval(loadStream, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!data) return null;

  const { macro_nacional = [], mercados_globales = [], variables_financieras = [] } = data;
  const items = [...macro_nacional, ...mercados_globales, ...variables_financieras];

  return (
    <div className="macro-ticker-wrapper" style={{ borderBottom: "1px solid var(--line)", background: "#06233d", color: "#ffffff", overflow: "hidden", position: "relative" }}>
      {/* Etiqueta Fija Izquierda */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 10,
          background: "linear-gradient(90deg, #041a2e 80%, rgba(4, 26, 46, 0))",
          padding: "0 18px 0 12px",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          fontSize: "11px",
          fontWeight: "800",
          letterSpacing: "0.5px"
        }}
      >
        <span className="status-dot" style={{ background: "#10b981", boxShadow: "0 0 8px #10b981" }} />
        <span style={{ color: "#60d7e7" }}>STREAM MACRO & GLOBAL</span>
      </div>

      {/* Cinta Desplazable Continua (Marquee) */}
      <div
        className="macro-ticker-track"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "28px",
          padding: "7px 0 7px 200px",
          whiteSpace: "nowrap",
          width: "max-content",
          animation: "marqueeScroll 38s linear infinite",
          animationPlayState: isPaused ? "paused" : "running",
          cursor: "pointer"
        }}
      >
        {/* Renderizado doble para efecto continuo sin saltos */}
        {[...items, ...items].map((item, idx) => {
          const varVal = item.variacion_pct ?? item.variacion_bps;
          const isPos = varVal > 0;
          const isZero = varVal === 0 || varVal == null;

          return (
            <div
              key={`${item.id}-${idx}`}
              onClick={() => setSelectedItem(item)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "12px",
                fontFamily: "Manrope, sans-serif",
                background: "rgba(255, 255, 255, 0.05)",
                padding: "3px 10px",
                borderRadius: "6px",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                transition: "background 0.2s"
              }}
              title="Clic para ver análisis macroeconómico"
            >
              <strong style={{ color: "#d5ecf8", fontSize: "11px", fontFamily: "monospace" }}>
                {item.simbolo}
              </strong>

              <span style={{ fontWeight: "700", color: "#ffffff", fontFamily: "monospace" }}>
                {item.unidad === "%" || item.unidad === "% anual"
                  ? `${item.valor.toFixed(2)}%`
                  : item.unidad === "MXN"
                  ? `$${item.valor.toFixed(4)}`
                  : item.unidad === "pts"
                  ? item.valor.toLocaleString("es-MX")
                  : item.unidad === "USD" || item.unidad === "USD/barril" || item.unidad === "USD/oz" || item.unidad === "USD/lb"
                  ? `$${item.valor.toFixed(2)}`
                  : item.valor}
              </span>

              {item.variacion_pct != null && (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "2px",
                    fontSize: "10px",
                    fontWeight: "700",
                    fontFamily: "monospace",
                    color: isZero ? "#94a3b8" : isPos ? "#34d399" : "#f87171"
                  }}
                >
                  {isPos ? <TrendingUp size={11} /> : !isZero ? <TrendingDown size={11} /> : null}
                  {isPos ? `+${item.variacion_pct.toFixed(2)}%` : isZero ? "0.00%" : `${item.variacion_pct.toFixed(2)}%`}
                </span>
              )}

              {item.variacion_bps != null && (
                <span style={{ fontSize: "10px", fontWeight: "700", color: isPos ? "#38bdf8" : "#f87171", fontFamily: "monospace" }}>
                  {isPos ? `+${item.variacion_bps} bps` : `${item.variacion_bps} bps`}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Modal de Detalle al hacer clic en cualquier indicador */}
      {selectedItem && (
        <dialog
          className="plan-gate"
          open
          style={{
            position: "fixed",
            zIndex: 1050,
            maxWidth: "520px",
            background: "#ffffff",
            borderRadius: "14px",
            padding: "24px",
            boxShadow: "0 24px 60px rgba(0, 0, 0, 0.35)",
            border: "1px solid var(--line)"
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
            <div>
              <span className="eyebrow">VARIABLE MACRO & FINANCIERA GLOBAL</span>
              <h2 style={{ fontSize: "20px", color: "var(--navy)", margin: "4px 0" }}>
                {selectedItem.nombre || selectedItem.simbolo}
              </h2>
            </div>
            <button
              onClick={() => setSelectedItem(null)}
              style={{ background: "transparent", border: 0, cursor: "pointer", color: "var(--muted)" }}
              aria-label="Cerrar modal"
            >
              <X size={20} />
            </button>
          </div>

          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "16px", marginBottom: "16px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", fontSize: "13px" }}>
              <div>
                <small style={{ color: "var(--muted)", display: "block" }}>VALOR ACTUAL</small>
                <strong style={{ fontSize: "22px", color: "var(--navy)", fontFamily: "monospace" }}>
                  {selectedItem.valor} {selectedItem.unidad}
                </strong>
              </div>
              <div>
                <small style={{ color: "var(--muted)", display: "block" }}>VARIACIÓN DE MERCADO</small>
                <strong style={{ fontSize: "18px", color: selectedItem.variacion_pct >= 0 ? "#059669" : "#dc2626", fontFamily: "monospace" }}>
                  {selectedItem.variacion_pct != null ? formatPct(selectedItem.variacion_pct) : selectedItem.variacion_bps ? `${selectedItem.variacion_bps} bps` : "—"}
                </strong>
              </div>
            </div>
          </div>

          <div style={{ fontSize: "13px", color: "var(--navy)", lineHeight: "1.6", marginBottom: "16px" }}>
            <strong>Impacto Cuantitativo en el Panel G2:</strong>
            <p style={{ margin: "4px 0", color: "var(--muted)" }}>
              {selectedItem.id === "usd_mxn"
                ? "El tipo de cambio impacta directamente a las emisoras exportadoras (como GMEXICO) y con pasivos en moneda extranjera. Su comportamiento modula el residuo de volatilidad en los 3 modelos G2."
                : selectedItem.id === "tasa_interes" || selectedItem.id === "tiie_28"
                ? "La tasa de política monetaria determina el costo de fondeo y margen financiero bancario (GFNORTE) e influye en la tasa de descuento de flujos para el universo del IPC."
                : selectedItem.id === "inflacion_inpc"
                ? "La persistencia inflacionaria presiona los márgenes brutos de emisoras de consumo masivo (WALMEX, BIMBO, FEMSA), impactando su spread relativo."
                : selectedItem.id === "cobre"
                ? "Precio internacional del cobre: factor fundamental para el volumen de ventas y EBITDA proyectado de GMEXICO."
                : selectedItem.id === "sp500" || selectedItem.id === "nasdaq"
                ? "Beta transversal del mercado estadounidense: determina la dirección del flujo de capitales foráneos hacia el mercado accionario mexicano."
                : "Variable macrofinanciera integrada en la ingesta del Lakehouse para calibración de volatilidad y análisis prospectivo."}
            </p>
          </div>

          <div style={{ background: "#e6f6f9", border: "1px solid #79b7ce7a", borderRadius: "8px", padding: "10px 14px", display: "flex", alignItems: "center", gap: "8px", fontSize: "11px", color: "var(--navy)" }}>
            <Cloud size={16} style={{ color: "#079baa", flexShrink: 0 }} />
            <span>
              <strong>Arquitectura AWS:</strong> Ingesta serverless con AWS Lambda + S3 a <strong>$0.00 USD/mes</strong> (100% Free Tier).
            </span>
          </div>

          <div style={{ marginTop: "18px", textAlign: "right" }}>
            <button className="button button-primary" onClick={() => setSelectedItem(null)} style={{ fontSize: "12px", padding: "6px 16px" }}>
              Cerrar Detalle
            </button>
          </div>
        </dialog>
      )}
    </div>
  );
}
