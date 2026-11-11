import React from "react";
import { Lock, LogIn, UserPlus, Check } from "lucide-react";
import { Header } from "../components/Header";
import { planById } from "../plans.mjs";

// Se muestra en #/sistema y #/ficha cuando no hay sesión iniciada.
export function TerminalGate() {
  const explorer = planById("explorer");

  return (
    <>
      <Header context="inner" />
      <main
        id="main-content"
        className="information-page container"
        style={{ maxWidth: "560px", margin: "60px auto", padding: "0 20px" }}
      >
        <div
          data-tour="terminal-gate"
          style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "16px", padding: "32px", boxShadow: "0 16px 45px rgba(9, 42, 73, 0.08)", textAlign: "center" }}
        >
          <span
            style={{ display: "inline-flex", width: 52, height: 52, borderRadius: "50%", alignItems: "center", justifyContent: "center", background: "#f0fdfa", color: "#079baa", marginBottom: 12 }}
          >
            <Lock size={24} aria-hidden="true" />
          </span>
          <span className="eyebrow" style={{ display: "block" }}>TERMINAL INSTITUCIONAL</span>
          <h1 style={{ fontSize: "24px", color: "var(--navy)", margin: "6px 0 10px" }}>
            Inicia sesión para abrir la terminal
          </h1>
          <p style={{ fontSize: "14px", color: "var(--muted)", lineHeight: 1.6, margin: "0 0 20px" }}>
            Las señales del panel G2, la serie histórica y la auditoría temporal están disponibles para usuarios
            registrados. Crear una cuenta es gratis.
          </p>

          <ul style={{ listStyle: "none", padding: 0, margin: "0 auto 24px", textAlign: "left", maxWidth: 380, fontSize: "13px", color: "var(--navy)" }}>
            {explorer.includes.slice(0, 4).map((item) => (
              <li key={item} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
                <Check size={16} style={{ color: "#10b981", flexShrink: 0 }} aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
          </ul>

          <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
            <a href="#/acceso" className="button button-primary" style={{ padding: "10px 22px", display: "inline-flex", alignItems: "center", gap: 6 }}>
              <LogIn size={16} aria-hidden="true" /> Iniciar sesión
            </a>
            <a href="#/registro" className="button button-outline" style={{ padding: "10px 22px", display: "inline-flex", alignItems: "center", gap: 6 }}>
              <UserPlus size={16} aria-hidden="true" /> Crear cuenta gratis
            </a>
          </div>
        </div>
      </main>
    </>
  );
}
