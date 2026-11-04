import React from "react";
import { Check } from "lucide-react";
import { useDelayedFlag } from "../hooks/useDelayedFlag";
import "./geo-pulse.css";

export function PrismiPulseIcon({ compact = false }) {
  const size = compact ? 28 : 54;
  return (
    <span className={`geo-pulse-icon${compact ? " geo-pulse-icon-compact" : ""}`} aria-hidden="true">
      <svg viewBox="0 0 100 100" fill="none" width={size} height={size}>
        {/* Ondas concéntricas de pulso financiero */}
        {[0, 1, 2].map((idx) => (
          <circle
            key={idx}
            cx="50"
            cy="50"
            r={24 + idx * 10}
            stroke={idx === 0 ? "#079baa" : "#10b981"}
            strokeWidth="1.5"
            opacity={0.7 - idx * 0.2}
            className="geo-pulse-wave"
            style={{ "--wave-index": idx }}
          />
        ))}
        {/* Vela japonesa en el centro */}
        <line x1="50" y1="26" x2="50" y2="36" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" />
        <rect x="42" y="36" width="16" height="28" rx="3" fill="#10b981" stroke="#059669" strokeWidth="1.5" />
        <line x1="50" y1="64" x2="50" y2="74" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
    </span>
  );
}

export function PrismiPulse({
  title = "Consultando boletín oficial BMV e inferencia IA…",
  detail,
  variant = "panel",
  steps = [],
  delay = 0,
}) {
  const visible = useDelayedFlag(true, delay);
  if (!visible) return null;

  return (
    <div className={`geo-pulse geo-pulse-${variant}`} role="status" aria-live="polite">
      <PrismiPulseIcon />
      <div className="geo-pulse-copy">
        <strong className="geo-pulse-title">{title}</strong>
        {detail && <p className="geo-pulse-detail">{detail}</p>}
      </div>
      {steps.length > 0 && (
        <ol className="geo-pulse-steps" aria-label="Estado de la consulta">
          {steps.map((step) => (
            <li
              key={step.id}
              className={`geo-pulse-step-${step.status}`}
              aria-current={step.status === "active" ? "step" : undefined}
            >
              <span className="geo-pulse-step-icon" aria-hidden="true">
                {step.status === "complete" ? <Check size={12} /> : step.status === "active" ? <span /> : null}
              </span>
              <span>
                {step.label}
                <span className="geo-pulse-sr">
                  {step.status === "complete"
                    ? ": completado"
                    : step.status === "active"
                    ? ": en curso"
                    : ": pendiente"}
                </span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
