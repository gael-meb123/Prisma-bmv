import React from "react";
import { BrainCircuit, CheckCircle2, XCircle, AlertCircle, TrendingUp, TrendingDown, Layers, FileText, ArrowRight, Lock } from "lucide-react";
import { Badge, Button } from "../UI";
import { formatMoney, formatPct, formatProb, STATUS } from "../../utils/presentation.mjs";
import { canAccessTicker } from "../../plans.mjs";

export function AnalysisPanel({
  ticker = "WALMEX",
  senales = [],
  userRole = "explorer",
  onPlanGate,
  onOpenAudit,
  onOpenReport
}) {
  const isAllowed = canAccessTicker(userRole, ticker);

  if (!isAllowed) {
    return (
      <div className="analysis-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <span className="eyebrow">MÓDULO 2 · MOTOR PREDICTIVO IA (G2)</span>
        <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "28px", textAlign: "center" }}>
          <div style={{ width: 48, height: 48, borderRadius: "50%", background: "#fef3c7", color: "#d97706", display: "grid", placeItems: "center", margin: "0 auto 12px auto" }}>
            <Lock size={24} />
          </div>
          <h3 style={{ fontSize: "18px", color: "var(--navy)", margin: "0 0 8px 0" }}>
            Emisora {ticker} Bloqueada en el Plan Explorer
          </h3>
          <p style={{ fontSize: "13px", color: "var(--muted)", maxWidth: "420px", margin: "0 auto 18px auto", lineHeight: "1.5" }}>
            El plan gratuito Explorer incluye el análisis cuantitativo completo de <strong>WALMEX</strong>. Para consultar las probabilidades de {ticker} en los 3 modelos G2, actualiza tu cuenta.
          </p>
          <Button variant="primary" icon={ArrowRight} onClick={() => onPlanGate(ticker)}>
            Ver Planes para Desbloquear
          </Button>
        </div>
      </div>
    );
  }

  const primera = senales[0] || {};
  const consenso = primera.consenso || "CONSENSO_PANEL_G2_NO_SUBIDA";
  const pppBase = primera.ppp_base || 50.39;
  const retRel = primera.ret_rel || 0;
  const statusInfo = STATUS[consenso] || STATUS.CONSENSO_PANEL_G2_NO_SUBIDA;

  return (
    <div className="analysis-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Encabezado */}
      <div>
        <span className="eyebrow">MÓDULO 2 · MOTOR PREDICTIVO IA (PANEL G2)</span>
        <h2 style={{ fontSize: "20px", margin: "4px 0 6px 0", color: "var(--navy)" }}>
          Inferencia Prospectiva a 5 Sesiones: {ticker}
        </h2>
        <p style={{ fontSize: "13px", color: "var(--muted)", margin: 0 }}>
          Horizonte de maduración bursátil: <strong style={{ color: "var(--navy)" }}>Y_t = 1 si PPP(t+5) &gt; PPP(t)</strong>.
        </p>
      </div>

      {/* Tarjeta de Consenso y Precio Base */}
      <div data-tour="kpis" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
        <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "10px", padding: "14px" }}>
          <small style={{ color: "var(--muted)", fontWeight: "700", textTransform: "uppercase", fontSize: "10px", letterSpacing: "0.5px" }}>
            ESTADO DE CONSENSO
          </small>
          <div style={{ marginTop: "6px" }}>
            <Badge status={consenso} />
          </div>
          <p style={{ fontSize: "11px", color: "var(--muted)", margin: "8px 0 0 0", lineHeight: "1.4" }}>
            {statusInfo.description}
          </p>
        </div>

        <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "10px", padding: "14px" }}>
          <small style={{ color: "var(--muted)", fontWeight: "700", textTransform: "uppercase", fontSize: "10px", letterSpacing: "0.5px" }}>
            PRECIO BASE DE INFERENCIA (t)
          </small>
          <div style={{ fontSize: "22px", fontWeight: "800", color: "var(--navy)", fontFamily: "monospace", marginTop: "4px" }}>
            {formatMoney(pppBase)}
          </div>
          <p style={{ fontSize: "11px", color: "var(--muted)", margin: "4px 0 0 0" }}>
            PPP oficial auditado en sesión del 30 Oct 2026.
          </p>
        </div>

        <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "10px", padding: "14px" }}>
          <small style={{ color: "var(--muted)", fontWeight: "700", textTransform: "uppercase", fontSize: "10px", letterSpacing: "0.5px" }}>
            FACTOR REVERSIÓN RELATIVA
          </small>
          <div style={{ fontSize: "20px", fontWeight: "800", fontFamily: "monospace", marginTop: "4px", color: retRel < 0 ? "#059669" : "#dc2626" }}>
            {formatPct(retRel)}
          </div>
          <p style={{ fontSize: "11px", color: "var(--muted)", margin: "4px 0 0 0" }}>
            {retRel < -5 ? "Rezagada frente al panel (impulso de rebote)." : "Sobreextendida frente al panel."}
          </p>
        </div>
      </div>

      {/* Barras de Probabilidad de los 3 Modelos G2 */}
      <div data-tour="modelos" style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <strong style={{ fontSize: "13px", color: "var(--navy)", display: "flex", alignItems: "center", gap: "6px" }}>
            <Layers size={16} style={{ color: "#079baa" }} />
            Distribución de Probabilidades de Subida (Panel G2)
          </strong>
          <span style={{ fontSize: "11px", color: "var(--muted)", fontFamily: "monospace" }}>Umbral neutral: 50.0%</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {senales.map((s) => {
            const pct = (s.prob * 100);
            const isBull = s.prob >= 0.50;
            let alias = "V1 Calibrado";
            if (s.modelo.includes("V2")) alias = "V2 Zona Neutral";
            if (s.modelo.includes("V3")) alias = "V3 Alta Discriminación";

            return (
              <div key={s.id} style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "6px" }}>
                  <span><strong>{alias}</strong> <span style={{ color: "var(--muted)", fontSize: "10px" }}>({s.modelo})</span></span>
                  <span style={{ fontWeight: "700", fontFamily: "monospace", color: isBull ? "#059669" : "#dc2626" }}>
                    {formatProb(s.prob)} · {s.pred}
                  </span>
                </div>
                {/* Barra horizontal con marca central en 50% */}
                <div style={{ position: "relative", height: "10px", background: "#e2e8f0", borderRadius: "6px", overflow: "hidden" }}>
                  <div style={{ position: "absolute", top: 0, bottom: 0, left: "50%", width: "2px", background: "#64748b", zIndex: 2 }} />
                  <div
                    style={{
                      height: "100%",
                      width: `${Math.min(100, Math.max(0, pct))}%`,
                      background: isBull ? "linear-gradient(90deg, #059669, #10b981)" : "linear-gradient(90deg, #dc2626, #f87171)",
                      borderRadius: "6px",
                      transition: "width 0.5s ease"
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Botones de Acción */}
      <div data-tour="acciones" style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "4px" }}>
        <Button variant="outline" icon={Layers} onClick={onOpenAudit}>
          Auditar Maduración Temporal (t+1 a t+5)
        </Button>
        <Button variant="primary" icon={FileText} onClick={onOpenReport}>
          Generar Ficha Ejecutiva
        </Button>
      </div>
    </div>
  );
}
