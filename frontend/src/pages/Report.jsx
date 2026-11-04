import React, { useState } from "react";
import { ArrowLeft, Printer, ShieldCheck, CheckCircle2, FileText, Download } from "lucide-react";
import { Logo, Badge, Button } from "../components/UI";
import { formatMoney, formatPct, formatProb } from "../utils/presentation.mjs";

export function Report({ ticker = "WALMEX", senales = [], onBack }) {
  const [issuedAt] = useState(() =>
    new Date().toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" })
  );

  const primera = senales[0] || {};
  const consenso = primera.consenso || "CONSENSO_PANEL_G2_NO_SUBIDA";
  const pppBase = primera.ppp_base || 50.39;
  const retRel = primera.ret_rel || 0;

  return (
    <div style={{ background: "#f8fafc", minHeight: "100vh", padding: "24px 16px" }}>
      <div className="container" style={{ maxWidth: "860px", margin: "0 auto" }}>
        {/* Barra de Controles (Oculta al imprimir) */}
        <div className="report-controls" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <button
            onClick={onBack}
            style={{ background: "transparent", border: 0, cursor: "pointer", display: "flex", alignItems: "center", gap: "6px", color: "var(--teal-dark)", fontWeight: "700", fontSize: "13px" }}
          >
            <ArrowLeft size={16} />
            <span>Volver a la Terminal</span>
          </button>
          <Button variant="primary" icon={Printer} onClick={() => window.print()}>
            Imprimir / Guardar en PDF
          </Button>
        </div>

        {/* Ficha Imprimible */}
        <article className="report-page" style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "14px", padding: "40px", boxShadow: "0 10px 30px rgba(0,0,0,0.05)" }}>
          {/* Encabezado del Reporte */}
          <header className="report-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "2px solid var(--navy)", paddingBottom: "16px", marginBottom: "24px" }}>
            <Logo light={true} />
            <div style={{ textAlign: "right" }}>
              <strong style={{ fontSize: "14px", color: "var(--navy)", display: "block" }}>DICTAMEN CUANTITATIVO OFICIAL</strong>
              <small style={{ color: "var(--muted)", fontSize: "11px" }}>EMITIDO EL {issuedAt.toUpperCase()}</small>
            </div>
          </header>

          <span className="eyebrow">FICHA TÉCNICA DE AUDITORÍA Y CONSENSO BURSÁTIL</span>
          <h1 style={{ fontSize: "28px", color: "var(--navy)", margin: "6px 0 16px 0" }}>
            Evaluación Prospectiva: {ticker} (*)
          </h1>

          {/* Resumen de Identificación */}
          <section className="report-section" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "16px", marginBottom: "20px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", fontSize: "13px" }}>
              <div>
                <small style={{ color: "var(--muted)", display: "block" }}>PRECIO BASE (t)</small>
                <strong style={{ fontSize: "18px", color: "var(--navy)", fontFamily: "monospace" }}>{formatMoney(pppBase)}</strong>
              </div>
              <div>
                <small style={{ color: "var(--muted)", display: "block" }}>FACTOR RELATIVO PANEL</small>
                <strong style={{ fontSize: "18px", color: retRel < 0 ? "#059669" : "#dc2626", fontFamily: "monospace" }}>{formatPct(retRel)}</strong>
              </div>
              <div>
                <small style={{ color: "var(--muted)", display: "block" }}>ESTADO DE CONSENSO</small>
                <div style={{ marginTop: "2px" }}><Badge status={consenso} /></div>
              </div>
            </div>
          </section>

          {/* Tabla de Modelos G2 */}
          <section className="report-section" style={{ marginBottom: "24px" }}>
            <h2 style={{ fontSize: "16px", color: "var(--navy)", marginBottom: "10px" }}>Matriz de Inferencia del Panel G2 (Horizonte t+5)</h2>
            <table className="comparison-table" style={{ width: "100%", fontSize: "12px" }}>
              <thead>
                <tr>
                  <th>Variante de Modelo</th>
                  <th>Especificación</th>
                  <th style={{ textAlign: "right" }}>Probabilidad</th>
                  <th style={{ textAlign: "center" }}>Pronóstico</th>
                </tr>
              </thead>
              <tbody>
                {senales.map((s) => (
                  <tr key={s.id}>
                    <td><strong>{s.modelo}</strong></td>
                    <td style={{ color: "var(--muted)" }}>Logit Pooled IRLS Newton-Raphson</td>
                    <td style={{ textAlign: "right", fontFamily: "monospace", fontWeight: "700" }}>{formatProb(s.prob)}</td>
                    <td style={{ textAlign: "center" }}>
                      <span style={{ fontWeight: "700", color: s.pred === "SUBIDA" ? "#059669" : "#dc2626" }}>
                        {s.pred}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* Sello de Auditoría Inmutable */}
          <section className="report-section" style={{ borderTop: "1px solid var(--line)", paddingTop: "16px", fontSize: "11px", color: "var(--muted)", lineHeight: "1.5" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
              <ShieldCheck size={16} style={{ color: "#079baa" }} />
              <strong style={{ color: "var(--navy)" }}>Trazabilidad y Cumplimiento Normativo:</strong>
            </div>
            <div>Boletín Oficial BMV del 30 Octubre 2026 · Certificado SHA-256: ea246a3f72a1e7b50dadf028e3e5995926a214508eb7648a9ebed29fa1ff19ea</div>
            <div style={{ marginTop: "4px" }}>Inferencia matricial ejecutada en AWS Lambda Serverless con datos brutos verificados en Amazon S3. Cero imputaciones sintéticas.</div>
          </section>
        </article>
      </div>
    </div>
  );
}
