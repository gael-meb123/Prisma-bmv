import React, { useEffect, useRef } from "react";
import { Lock, ArrowRight, X } from "lucide-react";

export function PlanGate({ reason = "ticker", ticker = "GMEXICO", onClose }) {
  const ref = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    if (!node.open) node.showModal();
    function cancel(event) {
      event.preventDefault();
      closeRef.current();
    }
    node.addEventListener("cancel", cancel);
    return () => {
      node.removeEventListener("cancel", cancel);
      if (node.open) node.close();
    };
  }, []);

  return (
    <dialog className="plan-gate" ref={ref} aria-labelledby="plan-gate-title">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
        <span className="badge badge-partial">
          <Lock size={12} style={{ marginRight: 4 }} /> Función Reservada
        </span>
        <button
          type="button"
          onClick={onClose}
          style={{ background: "transparent", border: 0, cursor: "pointer", color: "var(--muted)" }}
          aria-label="Cerrar modal"
        >
          <X size={20} />
        </button>
      </div>

      <h2 id="plan-gate-title">
        La emisora {ticker} está reservada para el Plan Professional.
      </h2>

      <p>
        El plan gratuito <strong>Explorer</strong> incluye el acceso libre y completo a <strong>WALMEX</strong> y el monitoreo general de las 15 emisoras de la BMV. Para desbloquear las señales prospectivas de {ticker}, GMEXICO, GFNORTE, AMX y la matriz de consenso de 3 modelos simultáneos, actualiza tu suscripción.
      </p>

      <div className="plans-actions" style={{ display: "flex", gap: "10px", marginTop: "20px" }}>
        <a className="button button-primary" href="#/planes" onClick={onClose}>
          <span>Ver Planes de Suscripción</span>
          <ArrowRight size={16} />
        </a>
        <button type="button" className="button button-outline" onClick={onClose}>
          Permanecer en Explorer
        </button>
      </div>
    </dialog>
  );
}
