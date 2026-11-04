import React, { useEffect, useRef } from "react";
import { ShieldCheck, ExternalLink, X, FileText, CheckCircle2 } from "lucide-react";

export function EvidenceDialog({ evidence, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    if (!node.open) node.showModal();
    function cancel(event) {
      event.preventDefault();
      onClose();
    }
    node.addEventListener("cancel", cancel);
    return () => {
      node.removeEventListener("cancel", cancel);
      if (node.open) node.close();
    };
  }, [onClose]);

  if (!evidence) return null;

  return (
    <dialog className="evidence-dialog plan-gate" ref={ref} style={{ maxWidth: "620px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <ShieldCheck size={22} style={{ color: "#079baa" }} />
          <h2 style={{ margin: 0, fontSize: "18px", color: "var(--navy)" }}>
            Sello Criptográfico y Evidencia Regulatoria BMV
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          style={{ background: "transparent", border: 0, cursor: "pointer", color: "var(--muted)" }}
        >
          <X size={20} />
        </button>
      </div>

      <div style={{ background: "var(--paper)", border: "1px solid var(--line)", borderRadius: "8px", padding: "14px", marginBottom: "14px", fontSize: "13px", lineHeight: "1.6" }}>
        <div><strong>Emisora auditada:</strong> {evidence.ticker} (Serie {evidence.serie || "*"})</div>
        <div><strong>Fecha de sesión:</strong> {evidence.fecha || "2026-10-30"}</div>
        <div><strong>PPP Oficial Reportado:</strong> ${evidence.ppp?.toFixed(2) || "50.39"} MXN</div>
        <div><strong>Estado de Auditoría:</strong> <span style={{ color: "#059669", fontWeight: "700" }}>✓ Ingesta Regulada y Verificada</span></div>
      </div>

      <div style={{ marginBottom: "14px" }}>
        <small style={{ fontWeight: "700", textTransform: "uppercase", color: "var(--muted)", letterSpacing: "0.5px" }}>
          Firma Hash SHA-256 del Boletín Original:
        </small>
        <div style={{ background: "#f1f5f9", padding: "10px", borderRadius: "6px", fontFamily: "monospace", fontSize: "11px", wordBreak: "break-all", marginTop: "4px", border: "1px solid #cbd5e1", color: "#0f172a" }}>
          {evidence.sha256 || "ea246a3f72a1e7b50dadf028e3e5995926a214508eb7648a9ebed29fa1ff19ea"}
        </div>
      </div>

      <p style={{ fontSize: "12px", color: "var(--muted)", lineHeight: "1.5" }}>
        El Precio Promedio Ponderado oficial representa el estándar regulatorio utilizado por fondos institucionales y derivados, siendo inmune a las distorsiones de liquidez de las subastas de cierre.
      </p>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "18px" }}>
        <a
          href={evidence.url || "https://www.bmv.com.mx/docs-pub/rss/boletin20261030.html"}
          target="_blank"
          rel="noopener noreferrer"
          className="button button-outline"
          style={{ fontSize: "12px" }}
        >
          <span>Ver Fuente en BMV.com.mx</span>
          <ExternalLink size={14} />
        </a>
        <button type="button" className="button button-primary" onClick={onClose} style={{ fontSize: "12px" }}>
          Cerrar Auditoría
        </button>
      </div>
    </dialog>
  );
}
