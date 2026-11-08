import React from "react";
import {
  AlertCircle,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Layers,
  ShieldCheck,
  Clock,
  Sparkles,
  Info,
  Check,
  Building2,
  Lock,
  ExternalLink,
  ChevronRight
} from "lucide-react";
import { STATUS, DISCLAIMER } from "../utils/presentation.mjs";

export function Logo({ light = false }) {
  return (
    <a className={`brand ${light ? "brand-light" : ""}`} href="#/" aria-label="PRISMA BMV, inicio">
      {/* Isotipo Prisma Hexagonal */}
      <svg className="brand-mark" width="40" height="40" viewBox="0 0 48 48" fill="none">
        <defs>
          <linearGradient id="prismGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#089baa" />
            <stop offset="50%" stopColor="#10b981" />
            <stop offset="100%" stopColor="#062c50" />
          </linearGradient>
        </defs>
        <polygon points="24,4 44,14 44,34 24,44 4,34 4,14" fill="url(#prismGrad)" opacity="0.9" />
        <polygon points="24,4 44,14 24,24 4,14" fill="#ffffff" opacity="0.3" />
        <polygon points="24,24 44,14 44,34 24,44" fill="#000000" opacity="0.2" />
        <line x1="24" y1="4" x2="24" y2="44" stroke="#ffffff" strokeWidth="1.5" strokeDasharray="3 2" />
      </svg>
      {/* Wordmark Tipográfico */}
      <span className="brand-wordmark" style={{ display: "inline-flex", flexDirection: "column", marginLeft: "10px", lineHeight: "1.1" }}>
        <strong style={{ fontSize: "17px", fontWeight: "800", letterSpacing: "1px", color: light ? "#062c50" : "#ffffff", fontFamily: "Manrope, sans-serif" }}>
          PRISMA <span style={{ color: "#079baa" }}>BMV</span>
        </strong>
        <span style={{ fontSize: "10px", letterSpacing: "2.5px", fontWeight: "700", textTransform: "uppercase", color: light ? "#60758c" : "#99c4dd" }}>
          FinTech Analytics
        </span>
      </span>
    </a>
  );
}

export function Button({
  children,
  icon: Icon,
  variant = "primary",
  className = "",
  loading = false,
  disabled = false,
  ...props
}) {
  return (
    <button
      className={`button button-${variant} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? (
        <span className="geo-pulse-step-icon" style={{ display: "inline-block", width: 14, height: 14, borderRadius: "50%", border: "2px solid currentColor", borderRightColor: "transparent", animation: "spin 0.7s linear infinite" }} />
      ) : (
        Icon && <Icon size={16} aria-hidden="true" />
      )}
      <span>{children}</span>
    </button>
  );
}

export function Badge({ status, children }) {
  const normalizedKey =
    typeof status === "string" && status.startsWith("DIVERGENCIA_G2")
      ? "DIVERGENCIA_PANEL_G2"
      : status;
  const s = STATUS[normalizedKey] || {
    tone: "partial",
    label: typeof status === "string" && status.length > 0 ? status : "Estado no documentado",
  };
  return (
    <span className={`badge badge-${s.tone}`}>
      <span className="status-dot" aria-hidden="true" />
      {children || s.label}
    </span>
  );
}

export function Notice({ children = DISCLAIMER, tone = "info", className = "" }) {
  return (
    <div className={`notice notice-${tone} ${className}`}>
      <Info size={18} aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}

export function ErrorNotice({ error, retry }) {
  return (
    <div className="error-box" role="alert">
      <AlertCircle size={24} />
      <div>
        <strong>No pudimos completar la consulta</strong>
        <p>{error}</p>
        {retry && (
          <button className="button button-outline" onClick={retry}>
            Volver a intentar
          </button>
        )}
      </div>
    </div>
  );
}
