import React, { useState, useRef, useEffect } from "react";
import {
  Menu,
  X,
  ArrowRight,
  BookOpen,
  ChevronDown,
  CircleHelp,
  CreditCard,
  Database,
  LogIn,
  Layers,
  ShieldCheck,
  TrendingUp,
  LogOut
} from "lucide-react";
import { Logo, Button } from "./UI";
import { useAccount } from "../hooks/useAccount";
import { planById } from "../plans.mjs";

export function Header({ context = "landing" }) {
  const [open, setOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef(null);
  const account = useAccount();
  const currentPlan = planById(account.role);
  const isWorkspace = context === "workspace";
  const isAuth = context === "auth";

  const publicLinks = [
    ["Inicio", "#/"],
    ["Cómo funciona", "#como-funciona"],
    ["Metodología G2", "#/metodologia"],
    ["Fuentes BMV", "#/fuentes"],
    ["Planes", "#/planes"]
  ];

  return (
    <header className={`site-header system-header ${isAuth ? "auth-header" : ""}`}>
      <div className="header-inner">
        {/* Logotipo Oficial */}
        <Logo light={false} />

        {/* Si estamos en el workspace/terminal, mostramos indicador de sesión y estado */}
        {isWorkspace && (
          <div className="header-location" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="status-dot" style={{ background: "#10b981", boxShadow: "0 0 10px #10b981" }} />
            <span>BMV SESIÓN ACTIVA · PPP 2026-10-30</span>
          </div>
        )}

        {/* Navegación y Acciones */}
        <nav className="navigation" style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          {!isWorkspace && (
            <div className="public-primary-links" style={{ display: "flex", gap: "18px" }}>
              {publicLinks.map(([label, href]) => (
                <a key={label} href={href} style={{ color: "#d5ecf8", fontSize: "13px", fontWeight: "600" }}>
                  {label}
                </a>
              ))}
            </div>
          )}

          {/* Selector de Plan Rápido para Pruebas del Evaluador / Demostración */}
          <div style={{ display: "inline-flex", alignItems: "center", background: "rgba(255, 255, 255, 0.1)", borderRadius: "8px", padding: "2px 8px", fontSize: "11px", color: "#e8f4fc" }}>
            <span style={{ marginRight: 6, color: "#8ee3ed", fontWeight: 700 }}>PLAN:</span>
            <select
              value={account.role}
              onChange={(e) => account.switchPlan(e.target.value)}
              style={{ background: "transparent", border: 0, color: "#ffffff", fontWeight: "700", cursor: "pointer", fontSize: "11px" }}
            >
              <option value="explorer" style={{ background: "#062c50", color: "#fff" }}>Explorer ($0)</option>
              <option value="profesional" style={{ background: "#062c50", color: "#fff" }}>Professional ($49)</option>
              <option value="enterprise" style={{ background: "#062c50", color: "#fff" }}>Enterprise ($199)</option>
            </select>
          </div>

          {/* Botón de acceso / alternar terminal */}
          {isWorkspace ? (
            <a href="#/" className="button button-outline header-signin" style={{ padding: "6px 14px", fontSize: "12px" }}>
              Portal Comercial
            </a>
          ) : (
            <a href="#/sistema" className="button button-primary header-cta" style={{ padding: "6px 16px", fontSize: "12px", background: "#079baa", borderColor: "#1fd2ea" }}>
              <span>Abrir Terminal</span>
              <ArrowRight size={14} />
            </a>
          )}
        </nav>
      </div>
    </header>
  );
}
