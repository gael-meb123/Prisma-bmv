import React from "react";
import { Lock, LogIn, UserPlus, Check } from "lucide-react";
import { Header, Footer } from "../components/Header";
import { EmptyArt } from "../components/Illustrations";
import { planById } from "../plans.mjs";

// Se muestra en #/sistema y #/ficha cuando no hay sesión iniciada.
export function TerminalGate() {
  const explorer = planById("explorer");

  return (
    <>
      <Header />
      <main
        id="main-content"
        className="information-page container"
        style={{ maxWidth: "560px", margin: "60px auto", padding: "0 20px" }}
      >
        <div
          data-tour="terminal-gate"
          style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "16px", padding: "32px", boxShadow: "0 16px 45px rgba(9, 42, 73, 0.08)", textAlign: "center" }}
        >
          <EmptyArt locked size={140} />
          <span className="bk-eyebrow" style={{ display: "block" }}>Banca en línea · Terminal</span>
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
            <a href="#/acceso" className="bk-btn bk-btn-navy">
              <LogIn size={16} aria-hidden="true" /> Ingresar
            </a>
            <a href="#/registro" className="bk-btn bk-btn-outline">
              <UserPlus size={16} aria-hidden="true" /> Abrir cuenta gratis
            </a>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
