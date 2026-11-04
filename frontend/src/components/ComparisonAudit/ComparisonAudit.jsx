import React from "react";
import { Clock, ShieldCheck, Database, Cloud, Terminal, CheckCircle2, ArrowLeft, Server } from "lucide-react";
import { Button } from "../UI";

export function ComparisonAudit({ ticker = "WALMEX", onBack, onOpenReport }) {
  const stepsTimeline = [
    { paso: "t (Emisión)", fecha: "30 Oct 2026", estado: "Vigente", detalle: "Señal generada al cierre BMV. PPP Base = $50.39." },
    { paso: "t + 1", fecha: "03 Nov 2026", estado: "En curso", detalle: "Evaluación preliminar de volatilidad intradiaria." },
    { paso: "t + 2", fecha: "04 Nov 2026", estado: "En espera", detalle: "Monitoreo del diferencial relativo acumulado vs panel." },
    { paso: "t + 3", fecha: "05 Nov 2026", estado: "En espera", detalle: "Prueba de persistencia estadística en el spread." },
    { paso: "t + 4", fecha: "06 Nov 2026", estado: "En espera", detalle: "Ventana de pre-liquidación cuantitativa." },
    { paso: "t + 5 (Liquidación)", fecha: "09 Nov 2026", estado: "Horizonte", detalle: "Cómputo formal del payoff: Y_t = 1 si PPP(t+5) > 50.39." },
  ];

  return (
    <div className="comparison-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Botón Volver y Título */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <button
          onClick={onBack}
          style={{ background: "transparent", border: 0, cursor: "pointer", display: "flex", alignItems: "center", color: "var(--teal-dark)", fontWeight: "700", fontSize: "13px" }}
        >
          <ArrowLeft size={16} style={{ marginRight: 4 }} />
          Volver a Análisis
        </button>
      </div>

      <div>
        <span className="eyebrow">MÓDULO 3 · AUDITORÍA TEMPORAL Y GOBERNANZA CLOUD</span>
        <h2 style={{ fontSize: "20px", margin: "4px 0 6px 0", color: "var(--navy)" }}>
          Ciclo de Maduración Bursátil: {ticker} ($t$ a $t+5$)
        </h2>
        <p style={{ fontSize: "13px", color: "var(--muted)", margin: 0 }}>
          Supervisión sesión por sesión hasta la liquidación de la hipótesis estadística.
        </p>
      </div>

      {/* Grid del Ciclo de Vida Temporal */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "8px" }}>
        {stepsTimeline.map((s, idx) => {
          const isFirst = idx === 0;
          return (
            <div
              key={s.paso}
              style={{
                background: isFirst ? "#e6f6f9" : "#ffffff",
                border: isFirst ? "1.5px solid #079baa" : "1px solid var(--line)",
                borderRadius: "8px",
                padding: "10px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between"
              }}
            >
              <div>
                <strong style={{ fontSize: "12px", color: "var(--navy)", display: "block" }}>{s.paso}</strong>
                <span style={{ fontSize: "10px", color: "var(--muted)", fontFamily: "monospace" }}>{s.fecha}</span>
              </div>
              <p style={{ fontSize: "11px", color: "var(--muted)", margin: "8px 0 0 0", lineHeight: "1.3" }}>
                {s.detalle}
              </p>
            </div>
          );
        })}
      </div>

      {/* Gobernanza Cloud Data Lakehouse AWS */}
      <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "16px" }}>
        <h3 style={{ fontSize: "14px", color: "var(--navy)", margin: "0 0 12px 0", display: "flex", alignItems: "center", gap: "6px" }}>
          <Cloud size={18} style={{ color: "#079baa" }} />
          Gobernanza Serverless del Data Lakehouse en AWS
        </h3>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "10px" }}>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: "11px", fontWeight: "700", color: "#079baa" }}>EVENTBRIDGE</span>
            <div style={{ fontSize: "12px", fontWeight: "700", fontFamily: "monospace", marginTop: "2px" }}>16:45 CDMX</div>
            <p style={{ fontSize: "10px", color: "var(--muted)", margin: "4px 0 0 0" }}>Disparo cron diario tras el cierre bursátil.</p>
          </div>

          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: "11px", fontWeight: "700", color: "#10b981" }}>AWS LAMBDA</span>
            <div style={{ fontSize: "12px", fontWeight: "700", fontFamily: "monospace", marginTop: "2px" }}>IRLS NumPy</div>
            <p style={{ fontSize: "10px", color: "var(--muted)", margin: "4px 0 0 0" }}>Ingesta HTML e inferencia matricial pura.</p>
          </div>

          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: "11px", fontWeight: "700", color: "#d97706" }}>AMAZON S3</span>
            <div style={{ fontSize: "12px", fontWeight: "700", fontFamily: "monospace", marginTop: "2px" }}>Medallion Lake</div>
            <p style={{ fontSize: "10px", color: "var(--muted)", margin: "4px 0 0 0" }}>Bronze (HTML), Silver (CSV), Gold (Parquet).</p>
          </div>

          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: "11px", fontWeight: "700", color: "#6366f1" }}>AMAZON ATHENA</span>
            <div style={{ fontSize: "12px", fontWeight: "700", fontFamily: "monospace", marginTop: "2px" }}>SQL Serverless</div>
            <p style={{ fontSize: "10px", color: "var(--muted)", margin: "4px 0 0 0" }}>Auditoría regulatoria e interoperabilidad.</p>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: "10px", marginTop: "4px" }}>
        <Button variant="primary" onClick={onOpenReport}>
          Imprimir Ficha Ejecutiva de Auditoría
        </Button>
      </div>
    </div>
  );
}
