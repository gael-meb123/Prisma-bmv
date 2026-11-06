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
  LogOut,
  Users
} from "lucide-react";
import { Logo, Button } from "./UI";
import { useAccount } from "../hooks/useAccount";
import { planById } from "../plans.mjs";

export function Header({ context = "landing" }) {
  const [open, setOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [planError, setPlanError] = useState("");
  const moreRef = useRef(null);
  const account = useAccount();
  const currentPlan = planById(account.role);
  const isWorkspace = context === "workspace";
  const isAuth = context === "auth";
  const hasSession = Boolean(account.session);
  const isAdmin = account.userRole === "admin";

  const publicLinks = [
    ["Inicio", "#/"],
    ["Cómo funciona", "#/#capacidades"],
    ["Metodología G2", "#/metodologia"],
    ["Fuentes BMV", "#/fuentes"],
    ["Planes", "#/planes"]
  ];

  async function handlePlanChange(e) {
    setPlanError("");
    try {
      await account.switchPlan(e.target.value);
    } catch (err) {
      setPlanError(err.message || "No se pudo cambiar el plan.");
    }
  }

  async function handleLogout() {
    await account.leave();
    window.location.hash = "/";
  }

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

          {/* Selector de Plan (demo): solo con sesión iniciada */}
          <div
            title={hasSession ? "Cambio de plan simulado (modo demo)" : "Inicia sesión para cambiar de plan"}
            style={{ display: "inline-flex", alignItems: "center", background: "rgba(255, 255, 255, 0.1)", borderRadius: "8px", padding: "2px 8px", fontSize: "11px", color: "#e8f4fc", opacity: hasSession ? 1 : 0.5 }}
          >
            <span style={{ marginRight: 6, color: "#8ee3ed", fontWeight: 700 }}>PLAN:</span>
            <select
              value={account.role}
              onChange={handlePlanChange}
              disabled={!hasSession}
              style={{ background: "transparent", border: 0, color: "#ffffff", fontWeight: "700", cursor: hasSession ? "pointer" : "not-allowed", fontSize: "11px" }}
            >
              <option value="explorer" style={{ background: "#062c50", color: "#fff" }}>Explorer ($0)</option>
              <option value="professional" style={{ background: "#062c50", color: "#fff" }}>Professional ($49)</option>
              <option value="enterprise" style={{ background: "#062c50", color: "#fff" }}>Enterprise ($199)</option>
            </select>
          </div>
          {planError && (
            <span role="alert" style={{ fontSize: "11px", color: "#fca5a5" }}>{planError}</span>
          )}

          {/* Enlace a administración: solo admins */}
          {hasSession && isAdmin && (
            <a href="#/admin" style={{ color: "#8ee3ed", fontSize: "12px", fontWeight: "700", display: "inline-flex", alignItems: "center", gap: "4px" }}>
              <Users size={14} /> Admin
            </a>
          )}

          {/* Sesión: entrar o salir */}
          {hasSession ? (
            <button
              type="button"
              onClick={handleLogout}
              className="button button-outline"
              style={{ padding: "6px 14px", fontSize: "12px", display: "inline-flex", alignItems: "center", gap: "6px" }}
            >
              <LogOut size={14} /> Salir
            </button>
          ) : (
            <a href="#/acceso" data-tour="login" className="button button-outline" style={{ padding: "6px 14px", fontSize: "12px", display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <LogIn size={14} /> Iniciar sesión
            </a>
          )}

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
