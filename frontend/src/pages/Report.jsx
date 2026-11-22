import React, { useEffect, useState } from "react";
import { ArrowLeft, Printer, ShieldCheck } from "lucide-react";
import { Logo, Badge, Button } from "../components/UI";
import { api } from "../services/api.mjs";
import { formatMoney, formatPct, formatProb, nombreModelo } from "../utils/presentation.mjs";

export function Report({ ticker = "WALMEX", senales = [], onBack }) {
  const real = import.meta.env.VITE_REQUIRE_REAL_API === "true";
  const goldEval = import.meta.env.VITE_GOLD_EVALUACION === "true";
  const [issuedAt] = useState(() =>
    new Date().toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" })
  );
  const [cargada, setCargada] = useState({ loading: false, data: null, error: "" });

  useEffect(() => {
    if ((real && !goldEval) || senales.length > 0) return undefined;
    const ctrl = new AbortController();
    setCargada({ loading: true, data: null, error: "" });
    api.terminal.senal(ticker, null, ctrl.signal)
      .then((data) => !ctrl.signal.aborted && setCargada({ loading: false, data, error: "" }))
      .catch((err) => !ctrl.signal.aborted && setCargada({ loading: false, data: null, error: err.message || "No se pudo consultar la señal." }));
    return () => ctrl.abort();
  }, [ticker, senales.length, real, goldEval]);

  if (real && !goldEval) {
    return <main className="container" style={{ maxWidth: 700, margin: "60px auto" }}>
      <h1>Ficha no disponible</h1>
      <p>La ficha se habilitará cuando las señales y su procedencia estén validadas. No se muestra información de ejemplo.</p>
      <button type="button" onClick={onBack}>Volver a la terminal</button>
    </main>;
  }

  const filas = senales.length > 0
    ? senales
    : (cargada.data?.modelos || []).filter((m) => m.generacion === "G2").map((m) => ({
        id: `${ticker}-${cargada.data?.fecha}-${m.modelo}`,
        modelo: m.modelo,
        prob: m.probabilidad,
        pred: m.clase === 1 ? "SUBIDA" : "NO_SUBIDA",
        consenso: cargada.data?.consensos?.G2 || "",
        ppp_base: cargada.data?.factor?.ppp_base ?? null,
        ret_rel: cargada.data?.factor?.ret_rel_pp ?? null,
      }));

  const primera = filas[0] || {};
  const fechaCorte = cargada.data?.fecha || primera.fecha_senal || "—";
  const consenso = cargada.data?.consensos?.G2 || primera.consenso || "SIN_CONSENSO";
  const pppBase = primera.ppp_base;
  const retRel = primera.ret_rel;

  return (
    <div style={{ background: "#f8fafc", minHeight: "100vh", padding: "24px 16px" }}>
      <div className="container" style={{ maxWidth: "860px", margin: "0 auto" }}>
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

        <article className="report-page" style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "14px", padding: "40px", boxShadow: "0 10px 30px rgba(0,0,0,0.05)" }}>
          <header className="report-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "2px solid var(--navy)", paddingBottom: "16px", marginBottom: "24px" }}>
            <Logo light={true} />
            <div style={{ textAlign: "right" }}>
              <strong style={{ fontSize: "14px", color: "var(--navy)", display: "block" }}>FICHA DE EVALUACIÓN CUANTITATIVA</strong>
              <small style={{ color: "var(--muted)", fontSize: "11px" }}>EMITIDA EL {issuedAt.toUpperCase()}</small>
            </div>
          </header>

          <span className="eyebrow">FICHA TÉCNICA DE AUDITORÍA Y CONSENSO BURSÁTIL · CORTE {fechaCorte}</span>
          <h1 style={{ fontSize: "28px", color: "var(--navy)", margin: "6px 0 16px 0" }}>
            Evaluación Prospectiva: {ticker}
          </h1>

          {cargada.error && <p role="alert" style={{ color: "#b91c1c", fontSize: 13 }}>{cargada.error}</p>}
          {cargada.loading && <p role="status" style={{ color: "var(--muted)", fontSize: 13 }}>Cargando señal desde archivo Gold en S3…</p>}

          <section className="report-section" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "16px", marginBottom: "20px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", fontSize: "13px" }}>
              <div>
                <small style={{ color: "var(--muted)", display: "block" }}>PRECIO BASE (t)</small>
                <strong style={{ fontSize: "18px", color: "var(--navy)", fontFamily: "monospace" }}>{pppBase != null ? formatMoney(pppBase) : "—"}</strong>
              </div>
              <div>
                <small style={{ color: "var(--muted)", display: "block" }}>FACTOR RELATIVO PANEL</small>
                <strong style={{ fontSize: "18px", color: retRel != null && retRel < 0 ? "#059669" : "#dc2626", fontFamily: "monospace" }}>
                  {retRel != null ? formatPct(retRel) : "—"}
                </strong>
              </div>
              <div>
                <small style={{ color: "var(--muted)", display: "block" }}>ESTADO DE CONSENSO</small>
                <div style={{ marginTop: "2px" }}><Badge status={consenso} /></div>
              </div>
            </div>
          </section>

          <section className="report-section" style={{ marginBottom: "24px" }}>
            <h2 style={{ fontSize: "16px", color: "var(--navy)", marginBottom: "10px" }}>Matriz de Inferencia del Panel G2 (Horizonte t+5)</h2>
            <table className="comparison-table" style={{ width: "100%", minWidth: 0, fontSize: "12px" }}>
              <thead>
                <tr>
                  <th style={{ width: "60%" }}>Modelo de análisis</th>
                  <th style={{ width: "20%", textAlign: "right" }}>Probabilidad</th>
                  <th style={{ width: "20%", textAlign: "center" }}>Pronóstico</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <strong>{nombreModelo(s.modelo)}</strong>
                      <small style={{ color: "var(--muted)", display: "block", marginTop: "4px" }}>
                        {s.modelo} · Estimación estadística del archivo Gold en S3
                      </small>
                    </td>
                    <td style={{ textAlign: "right", fontFamily: "monospace", fontWeight: "700" }}>{formatProb(s.prob)}</td>
                    <td style={{ textAlign: "center" }}>
                      <span style={{ fontWeight: "700", color: s.pred === "SUBIDA" ? "#059669" : "#dc2626" }}>
                        {s.pred}
                      </span>
                    </td>
                  </tr>
                ))}
                {!filas.length && !cargada.loading && (
                  <tr>
                    <td colSpan={3} style={{ textAlign: "center", color: "var(--muted)", padding: "14px" }}>
                      Sin señales registradas en el archivo histórico Gold para {ticker}.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>

          <section className="report-section" style={{ borderTop: "1px solid var(--line)", paddingTop: "16px", fontSize: "11px", color: "var(--muted)", lineHeight: "1.5" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
              <ShieldCheck size={16} style={{ color: "#079baa" }} />
              <strong style={{ color: "var(--navy)" }}>Trazabilidad y Gobernanza:</strong>
            </div>
            <div>Archivo histórico Gold en Amazon S3 (`gold/senales_g2/`) · Corte {fechaCorte} · Lectura verificada en AWS Lambda sin imputaciones sintéticas.</div>
            <div style={{ marginTop: "4px" }}>Probabilidades estadísticas en modo evaluación histórica; no constituyen recomendación ni asesoría de inversión. La emisión productiva continua permanece sujeta a la compuerta 21/21.</div>
          </section>
        </article>
      </div>
    </div>
  );
}
