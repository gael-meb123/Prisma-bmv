import React, { useState } from "react";
import { ArrowRight, Lock, Mail, User, ShieldCheck } from "lucide-react";
import { Header } from "../components/Header";
import { Button, Logo } from "../components/UI";
import { useAccount } from "../hooks/useAccount";

export function Access() {
  const account = useAccount();
  const [email, setEmail] = useState("analista@fondo.com");
  const [name, setName] = useState("Analista Cuantitativo");
  const [selectedPlan, setSelectedPlan] = useState("explorer");

  function handleSubmit(e) {
    e.preventDefault();
    account.enter(email, name, selectedPlan);
    window.location.hash = "/sistema";
  }

  return (
    <>
      <Header context="auth" />

      <main id="main-content" className="information-page container" style={{ maxWidth: "460px", margin: "60px auto", padding: "0 20px" }}>
        <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "16px", padding: "32px", boxShadow: "0 16px 45px rgba(9, 42, 73, 0.08)" }}>
          <div style={{ textAlign: "center", marginBottom: "24px" }}>
            <span className="eyebrow">TERMINAL INSTITUCIONAL</span>
            <h1 style={{ fontSize: "24px", color: "var(--navy)", margin: "6px 0" }}>Iniciar Sesión</h1>
            <p style={{ fontSize: "13px", color: "var(--muted)", margin: 0 }}>
              Accede a las señales en vivo y al consenso econométrico G2.
            </p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "var(--navy)", marginBottom: "4px" }}>
                Nombre del Analista
              </label>
              <div style={{ position: "relative" }}>
                <User size={16} style={{ position: "absolute", left: "10px", top: "11px", color: "var(--muted)" }} />
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px 8px 34px", borderRadius: "8px", border: "1px solid var(--line)", fontSize: "13px" }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "var(--navy)", marginBottom: "4px" }}>
                Correo Corporativo
              </label>
              <div style={{ position: "relative" }}>
                <Mail size={16} style={{ position: "absolute", left: "10px", top: "11px", color: "var(--muted)" }} />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px 8px 34px", borderRadius: "8px", border: "1px solid var(--line)", fontSize: "13px" }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "var(--navy)", marginBottom: "4px" }}>
                Plan de Inicio
              </label>
              <select
                value={selectedPlan}
                onChange={(e) => setSelectedPlan(e.target.value)}
                style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--line)", fontSize: "13px", background: "#ffffff" }}
              >
                <option value="explorer">Explorer (Sin costo · WALMEX)</option>
                <option value="profesional">Professional ($49 USD/mes · Panel 15 Emisoras)</option>
                <option value="enterprise">Enterprise ($199 USD/mes · Acceso API)</option>
              </select>
            </div>

            <Button variant="primary" type="submit" style={{ width: "100%", justifyContent: "center", marginTop: "8px" }}>
              <span>Entrar a Prisma BMV</span>
              <ArrowRight size={16} />
            </Button>
          </form>
        </div>
      </main>
    </>
  );
}
