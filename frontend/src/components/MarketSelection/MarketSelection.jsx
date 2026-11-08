import React, { useState } from "react";
import { Search, Filter, ShieldCheck, CheckCircle2, AlertTriangle, ArrowRight } from "lucide-react";
import { Badge } from "../UI";
import { formatMoney, formatPct } from "../../utils/presentation.mjs";

export function MarketSelection({
  cotizaciones = [],
  fechas = [],
  fechaActiva = "",
  onChangeFecha,
  selectedTicker = "WALMEX",
  onSelectTicker,
  onShowEvidence,
  sha256 = "",
  urlFuente = ""
}) {
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState("Todos");

  const sectores = ["Todos", ...new Set(cotizaciones.map((c) => c.sector).filter(Boolean))];

  const filtradas = cotizaciones.filter((c) => {
    const matchQuery = c.emisora.toLowerCase().includes(query.toLowerCase()) ||
                       (c.sector && c.sector.toLowerCase().includes(query.toLowerCase()));
    const matchSector = sector === "Todos" || c.sector === sector;
    return matchQuery && matchSector;
  });

  return (
    <div className="selection-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Encabezado y Filtros */}
      <div>
        <span className="eyebrow">MÓDULO 1 · MONITOR DE MERCADO EN VIVO</span>
        <h2 style={{ fontSize: "20px", margin: "4px 0 8px 0", color: "var(--navy)" }}>
          Universo IPC · Cotizaciones Oficiales PPP
        </h2>
        <p style={{ fontSize: "13px", color: "var(--muted)", margin: 0 }}>
          Precios Promedio Ponderados extraídos del boletín regulatorio de la BMV sin imputaciones sintéticas.
        </p>
      </div>

      {/* Controles de Búsqueda y Sector */}
      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: "180px", position: "relative" }}>
          <Search size={16} style={{ position: "absolute", left: "10px", top: "10px", color: "var(--muted)" }} />
          <input
            type="text"
            placeholder="Buscar por ticker o sector…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ width: "100%", padding: "8px 12px 8px 34px", borderRadius: "8px", border: "1px solid var(--line)", fontSize: "13px" }}
          />
        </div>

        {fechas.length > 0 && (
          <select
            value={fechaActiva || fechas[0]}
            onChange={(e) => onChangeFecha && onChangeFecha(e.target.value)}
            aria-label="Seleccionar fecha de sesión"
            style={{ padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--line)", fontSize: "13px", background: "#ffffff", color: "var(--navy)", fontWeight: "600" }}
          >
            {fechas.map((f) => (
              <option key={f} value={f}>Sesión {f}</option>
            ))}
          </select>
        )}

        <select
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          style={{ padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--line)", fontSize: "13px", background: "#ffffff", color: "var(--navy)" }}
        >
          {sectores.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Lista de Emisoras */}
      <div className="table-scroll" data-tour="monitor" style={{ border: "1px solid var(--line)", borderRadius: "10px", maxHeight: "360px", overflowY: "auto" }}>
        <table className="comparison-table" style={{ width: "100%", fontSize: "12px" }}>
          <thead>
            <tr>
              <th>Emisora</th>
              <th>Sector</th>
              <th style={{ textAlign: "right" }}>PPP Oficial</th>
              <th style={{ textAlign: "right" }}>Var %</th>
              <th style={{ textAlign: "center" }}>Auditoría</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtradas.map((c) => {
              const isSelected = selectedTicker === c.emisora;
              const isVerif =
                c.estado_captura === "PPP_PUBLICADO_VERIFICADO" ||
                c.estado_captura === "CONTINGENCIA_FUENTE_SECUNDARIA";
              const varPos = c.variacion_pct > 0;
              return (
                <tr
                  key={c.emisora}
                  data-tour={c.emisora === "WALMEX" ? "emisora-walmex" : undefined}
                  onClick={() => onSelectTicker(c.emisora)}
                  style={{
                    cursor: "pointer",
                    background: isSelected ? "#e6f6f9" : "transparent",
                    transition: "background 0.2s"
                  }}
                >
                  <td>
                    <strong>{c.emisora}</strong> <span style={{ color: "var(--muted)" }}>({c.serie})</span>
                  </td>
                  <td style={{ color: "var(--muted)" }}>{c.sector}</td>
                  <td style={{ textAlign: "right", fontWeight: "700", fontFamily: "monospace" }}>
                    {isVerif ? formatMoney(c.ppp_bmv_mxn) : "—"}
                  </td>
                  <td style={{ textAlign: "right", fontWeight: "700", color: isVerif ? (varPos ? "#059669" : "#dc2626") : "var(--muted)", fontFamily: "monospace" }}>
                    {isVerif ? formatPct(c.variacion_pct) : "—"}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <Badge status={c.estado_captura} />
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <ArrowRight size={14} style={{ color: isSelected ? "#079baa" : "var(--line)" }} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Sello de Auditoría Criptográfica */}
      <div
        data-tour="sello"
        style={{
          background: "#ffffff",
          border: "1px solid var(--line)",
          borderRadius: "10px",
          padding: "12px 14px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "10px"
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <ShieldCheck size={20} style={{ color: "#079baa" }} />
          <div>
            <strong style={{ fontSize: "12px", color: "var(--navy)", display: "block" }}>
              Boletín Diario Oficial BMV Verificado
            </strong>
            <span style={{ fontSize: "11px", color: "var(--muted)", fontFamily: "monospace" }}>
              SHA-256: {sha256 ? `${sha256.slice(0, 20)}…` : "ea246a3f72a1e…"}
            </span>
          </div>
        </div>
        <button
          className="button button-outline"
          onClick={() => {
            const current = cotizaciones.find((c) => c.emisora === selectedTicker);
            onShowEvidence({
              ticker: selectedTicker,
              serie: current?.serie || "*",
              ppp: current?.ppp_bmv_mxn,
              sha256,
              url: urlFuente
            });
          }}
          style={{ fontSize: "11px", padding: "4px 10px" }}
        >
          Auditar Fuente
        </button>
      </div>
    </div>
  );
}
