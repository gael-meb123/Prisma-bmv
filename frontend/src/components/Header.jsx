import React, { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ChevronDown,
  CircleHelp,
  LayoutDashboard,
  Lock,
  LogOut,
  Menu,
  ShieldCheck,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { Logo } from "./UI";
import { PageHeroArt } from "./Illustrations";
import { useAccount } from "../hooks/useAccount";
import { useMarketStatus } from "../hooks/useMarketStatus";
import { PLANS } from "../plans.mjs";

const LINKS = [
  ["Inicio", "#/"],
  ["Cómo funciona", "#/#como-funciona"],
  ["Metodología", "#/metodologia"],
  ["Fuentes BMV", "#/fuentes"],
  ["Planes", "#/planes"],
];

export function iniciales(nombre = "", email = "") {
  const base = (nombre || email.split("@")[0] || "?").trim();
  const partes = base.split(/[\s._-]+/).filter(Boolean);
  return ((partes[0]?.[0] || "") + (partes[1]?.[0] || "")).toUpperCase() || "?";
}

export function Header() {
  const account = useAccount();
  const status = useMarketStatus();
  const [menuOpen, setMenuOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [planError, setPlanError] = useState("");
  const userRef = useRef(null);
  const hasSession = Boolean(account.session);
  const isAdmin = account.userRole === "admin";
  const route = typeof location !== "undefined" ? location.hash.replace(/^#/, "") || "/" : "/";

  useEffect(() => {
    function onDoc(e) {
      if (userRef.current && !userRef.current.contains(e.target)) setUserOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

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
    <>
      {/* Barra utilitaria (estilo portal bancario) */}
      <div className="bk-util">
        <div className="bk-container bk-util-inner">
          <div className="bk-util-left">
            <span className="bk-util-status">
              <span className="bk-dot bk-dot-live" aria-hidden="true" />
              {status
                ? `Mercado BMV · sesión ${status.fecha} · ${status.verificadas}/${status.total} PPP verificados`
                : "Mercado BMV · boletín oficial"}
            </span>
          </div>
          <div className="bk-util-right">
            <a href="#/fuentes"><ShieldCheck size={13} style={{ verticalAlign: "-2px", marginRight: 4 }} />Seguridad</a>
            <a href="#/estados"><CircleHelp size={13} style={{ verticalAlign: "-2px", marginRight: 4 }} />Ayuda</a>
            <a href="#/planes">Planes</a>
          </div>
        </div>
      </div>

      <header className="bk-header">
        <div className="bk-container bk-header-inner">
          <Logo light />

          <nav className={`bk-nav ${menuOpen ? "is-open" : ""}`} aria-label="Navegación principal">
            {LINKS.map(([label, href]) => (
              <a
                key={label}
                href={href}
                className={href === `#${route}` ? "is-active" : ""}
                onClick={() => setMenuOpen(false)}
              >
                {label}
              </a>
            ))}
          </nav>

          <div className="bk-header-actions">
            {hasSession ? (
              <>
                <a href="#/sistema" className="bk-btn bk-btn-primary bk-btn-sm bk-hide-sm" data-tour="cta-sistema-header">
                  <LayoutDashboard size={15} /> Mi terminal
                </a>
                <div className="bk-user" ref={userRef}>
                  <button type="button" className="bk-user-btn" onClick={() => setUserOpen((v) => !v)} aria-expanded={userOpen}>
                    <span className="bk-avatar">{iniciales(account.user?.name, account.user?.email)}</span>
                    <span className="bk-hide-sm">{account.user?.name?.split(" ")[0] || "Mi cuenta"}</span>
                    <ChevronDown size={14} />
                  </button>
                  {userOpen && (
                    <div className="bk-user-menu" role="menu">
                      <div className="bk-user-menu-head">
                        <strong>{account.user?.name || "Mi cuenta"}</strong>
                        <span>{account.user?.email}</span>
                      </div>
                      <label className="bk-plan-select">
                        Plan (demo)
                        <select value={account.role} onChange={handlePlanChange}>
                          {PLANS.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name} ({p.price.amount})
                            </option>
                          ))}
                        </select>
                      </label>
                      {planError && <p role="alert" style={{ color: "#b91c1c", fontSize: 12, margin: "0 10px 6px" }}>{planError}</p>}
                      <a href="#/sistema"><LayoutDashboard size={15} /> Ir a mi terminal</a>
                      {isAdmin && <a href="#/admin"><Users size={15} /> Administración</a>}
                      <button type="button" className="bk-user-item" onClick={handleLogout}>
                        <LogOut size={15} /> Cerrar sesión
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                <a href="#/registro" className="bk-btn bk-btn-outline bk-btn-sm bk-hide-sm">
                  <UserPlus size={15} /> Abrir cuenta
                </a>
                <a href="#/acceso" data-tour="login" className="bk-btn bk-btn-navy bk-btn-sm">
                  <Lock size={14} /> Ingresar
                </a>
              </>
            )}
            <button
              type="button"
              className="bk-menu-btn"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label={menuOpen ? "Cerrar menú" : "Abrir menú"}
              aria-expanded={menuOpen}
            >
              {menuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>
      </header>
    </>
  );
}

export function Footer() {
  return (
    <footer className="bk-footer">
      <div className="bk-container bk-footer-grid">
        <div>
          <Logo />
          <p style={{ marginTop: 14, maxWidth: 320 }}>
            Inteligencia cuantitativa sobre el Precio Promedio Ponderado oficial de la Bolsa Mexicana de Valores. Datos
            auditables, sin imputaciones.
          </p>
        </div>
        <div>
          <h4>Plataforma</h4>
          <a href="#/sistema">Terminal</a>
          <a href="#/planes">Planes</a>
          <a href="#/registro">Abrir cuenta</a>
        </div>
        <div>
          <h4>Transparencia</h4>
          <a href="#/metodologia">Metodología</a>
          <a href="#/fuentes">Fuentes y gobernanza</a>
          <a href="#/estados">Estados de los datos</a>
        </div>
        <div>
          <h4>Ayuda</h4>
          <a href="#/acceso">Ingresar</a>
          <a href="#/#faq">Preguntas frecuentes</a>
          <a href="#/fuentes">Seguridad</a>
        </div>
      </div>
      <div className="bk-container bk-footer-legal">
        <span>© 2026 Prisma BMV · Plataforma de análisis cuantitativo.</span>
        <span>Probabilidades estadísticas; no constituyen recomendación ni asesoría de inversión.</span>
      </div>
    </footer>
  );
}

/* Encabezado de páginas internas con arte vectorial */
export function PageHero({ eyebrow, title, lead, children }) {
  return (
    <section className="bk-page-hero">
      <PageHeroArt />
      <div className="bk-container" style={{ position: "relative" }}>
        {eyebrow && <span className="bk-eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {lead && <p>{lead}</p>}
        {children}
      </div>
    </section>
  );
}

export function CtaLink({ href, children }) {
  return (
    <a href={href} className="bk-btn bk-btn-primary">
      {children} <ArrowRight size={16} />
    </a>
  );
}
