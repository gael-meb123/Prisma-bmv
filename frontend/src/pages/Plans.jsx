import React, { useState } from "react";
import { Check, ArrowRight, ShieldCheck } from "lucide-react";
import { Header, Footer, PageHero } from "../components/Header";
import { PlanCardArt } from "../components/Illustrations";
import { Button, Notice } from "../components/UI";
import { useAccount } from "../hooks/useAccount";
import { PLANS, planById } from "../plans.mjs";

export function Plans() {
  const real = import.meta.env.VITE_REQUIRE_REAL_API === "true";
  const account = useAccount();
  const currentPlan = planById(account.role);
  const [switching, setSwitching] = useState(null);
  const [error, setError] = useState("");
  const isAdmin = account.userRole === "admin";

  async function handleSwitch(planId) {
    if (planId === account.role) return;
    if (real) {
      if (isAdmin) window.location.hash = "/admin";
      return;
    }
    setSwitching(planId);
    setError("");
    try {
      await account.switchPlan(planId);
    } catch (err) {
      setError(err.message || "No se pudo cambiar el plan.");
    } finally {
      setSwitching(null);
    }
  }

  return (
    <>
      <Header />
      <PageHero
        eyebrow="Suscripciones institucionales"
        title="Planes y Cobertura Cuantitativa BMV"
        lead="Escalera calibrada en MXN/USD para el mercado accionario mexicano con cobertura ampliada del IPC-35, verificación SHA-256 y gobernanza en AWS."
      />
      <main id="main-content" className="information-page bk-container bk-page-body" style={{ maxWidth: "1080px", paddingBottom: "24px" }}>

        <Notice tone="info">
          {real
            ? "Los planes y permisos se verifican en servidor mediante Amazon Cognito y DynamoDB. Las señales G2 y el panel ajustado permanecerán bloqueados en todos los planes hasta concluir la ventana limpia 21/21 y las validaciones de eventos corporativos."
            : "Modo Demostración Activo: La conmutación de planes es instantánea para permitir la evaluación completa de los bloqueos freemium."}
        </Notice>

        {error && (
          <div style={{ margin: "12px 0", padding: "10px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px", fontSize: "13px", color: "#b91c1c" }}>
            {error}
          </div>
        )}

        <div style={{ margin: "24px 0", padding: "14px 20px", background: "#ffffff", border: "1px solid var(--line)", borderRadius: "10px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <span style={{ fontSize: "12px", color: "var(--muted)" }}>SESIÓN ACTUAL:</span>
            <strong style={{ display: "block", fontSize: "15px", color: "var(--navy)" }}>{account.user?.email || "Sin sesión iniciada"}</strong>
          </div>
          <div style={{ textAlign: "right" }}>
            <span style={{ fontSize: "12px", color: "var(--muted)" }}>PLAN VIGENTE:</span>
            <strong style={{ display: "block", fontSize: "15px", color: "#079baa" }}>{account.session ? currentPlan.name : "Explorer (público)"}</strong>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "24px", marginTop: "32px" }}>
          {PLANS.map((plan) => {
            const isActive = account.session && account.role === plan.id;
            const isSwitching = switching === plan.id;
            let label = `Activar Plan ${plan.name}`;
            let disabled = isSwitching;
            if (isActive) {
              label = "✓ Plan Activo";
              disabled = true;
            } else if (real) {
              if (!account.session) {
                label = plan.id === "explorer" ? "Crear cuenta Explorer" : "Iniciar sesión para consultar";
                disabled = false;
              } else if (isAdmin) {
                label = "Gestionar en Administración";
                disabled = false;
              } else {
                label = "Solicitar cambio al administrador";
                disabled = true;
              }
            }
            return (
              <article
                key={plan.id}
                style={{
                  background: isActive ? "#f0fdfa" : "#ffffff",
                  border: isActive ? "2px solid #079baa" : "1px solid var(--line)",
                  borderRadius: "16px",
                  padding: "22px",
                  boxShadow: "var(--bk-shadow)",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between"
                }}
              >
                <div>
                  <div style={{ borderRadius: "14px", overflow: "hidden", marginBottom: "16px" }}>
                    <PlanCardArt plan={plan.id} />
                  </div>
                  <span className="eyebrow">{plan.audience}</span>
                  <h2 style={{ fontSize: "22px", color: "var(--navy)", margin: "4px 0" }}>{plan.name}</h2>
                  <div style={{ fontSize: "28px", fontWeight: "800", color: "var(--navy)", fontFamily: "monospace", margin: "14px 0 6px 0" }}>
                    {plan.price.amount} <small style={{ fontSize: "12px", color: "var(--muted)" }}>{plan.price.detail}</small>
                  </div>
                  <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.5", marginBottom: "20px" }}>{plan.summary}</p>

                  <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px 0", fontSize: "13px", color: "var(--navy)" }}>
                    {plan.includes.map((inc) => (
                      <li key={inc} style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                        <Check size={16} style={{ color: "#10b981", flexShrink: 0 }} />
                        <span>{inc}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <Button
                  variant={isActive ? "outline" : "primary"}
                  disabled={disabled}
                  onClick={() => {
                    if (real && !account.session) {
                      window.location.hash = plan.id === "explorer" ? "/registro" : "/acceso";
                      return;
                    }
                    handleSwitch(plan.id);
                  }}
                  style={{ width: "100%", justifyContent: "center", opacity: disabled ? 0.72 : 1 }}
                >
                  {isSwitching ? "Cambiando…" : label}
                </Button>
              </article>
            );
          })}
        </div>

        <div style={{ marginTop: "24px", padding: "14px 18px", background: "#f8fafc", border: "1px solid var(--line)", borderRadius: "10px", fontSize: "12.5px", color: "var(--muted)", display: "flex", gap: "10px", alignItems: "center" }}>
          <ShieldCheck size={18} style={{ color: "#079baa", flexShrink: 0 }} />
          <span>Precios de referencia en MXN (~USD equivalentes). La cobertura de señales probabilísticas se habilitará únicamente al acreditar la ventana limpia 21/21, conciliación de avisos corporativos BMV y auditoría sin fuga.</span>
        </div>

        <div style={{ textAlign: "center", marginTop: "36px" }}>
          <a href="#/sistema" className="button button-primary" style={{ padding: "12px 28px", fontSize: "14px" }}>
            <span>Volver a la Terminal Cuantitativa</span>
            <ArrowRight size={16} />
          </a>
        </div>
      </main>
      <Footer />
    </>
  );
}
