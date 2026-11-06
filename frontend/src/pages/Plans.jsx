import React, { useState } from "react";
import { Check, ArrowRight, ShieldCheck, Zap } from "lucide-react";
import { Header } from "../components/Header";
import { Button, Notice } from "../components/UI";
import { useAccount } from "../hooks/useAccount";
import { PLANS, planById } from "../plans.mjs";

export function Plans() {
  const account = useAccount();
  const currentPlan = planById(account.role);
  const [switching, setSwitching] = useState(null); // id del plan que se está activando
  const [error, setError] = useState("");

  async function handleSwitch(planId) {
    if (planId === account.role) return;
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
      <Header context="inner" />

      <main id="main-content" className="information-page container" style={{ maxWidth: "1080px", margin: "40px auto", padding: "0 20px" }}>
        <span className="eyebrow">SUSCRIPCIONES INSTITUCIONALES</span>
        <h1 style={{ color: "var(--navy)", fontSize: "36px", margin: "8px 0" }}>
          Planes y Niveles de Inferencia Cuantitativa
        </h1>
        <p className="page-lead" style={{ fontSize: "16px", color: "var(--muted)", maxWidth: "700px", lineHeight: "1.6", marginBottom: "24px" }}>
          Selecciona el nivel de acceso analítico para tu mesa de dinero o cartera individual. Puedes conmutar de plan en cualquier momento para evaluar las funciones en vivo.
        </p>

        <Notice tone="info">
          Modo Demostración Activo: La conmutación de planes es instantánea para permitir la evaluación completa de las capacidades multi-modelo y los bloqueos freemium.
        </Notice>

        {error && (
          <div style={{ margin: "12px 0", padding: "10px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px", fontSize: "13px", color: "#b91c1c" }}>
            {error}
          </div>
        )}

        <div style={{ margin: "24px 0", padding: "14px 20px", background: "#ffffff", border: "1px solid var(--line)", borderRadius: "10px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <span style={{ fontSize: "12px", color: "var(--muted)" }}>SESIÓN ACTUAL:</span>
            <strong style={{ display: "block", fontSize: "15px", color: "var(--navy)" }}>{account.user?.email || "—"}</strong>
          </div>
          <div style={{ textAlign: "right" }}>
            <span style={{ fontSize: "12px", color: "var(--muted)" }}>PLAN VIGENTE:</span>
            <strong style={{ display: "block", fontSize: "15px", color: "#079baa" }}>{currentPlan.name}</strong>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "24px", marginTop: "32px" }}>
          {PLANS.map((plan) => {
            const isActive = account.role === plan.id;
            const isSwitching = switching === plan.id;
            return (
              <article
                key={plan.id}
                style={{
                  background: isActive ? "#f0fdfa" : "#ffffff",
                  border: isActive ? "2px solid #079baa" : "1px solid var(--line)",
                  borderRadius: "16px",
                  padding: "28px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between"
                }}
              >
                <div>
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
                  disabled={isSwitching}
                  onClick={() => handleSwitch(plan.id)}
                  style={{ width: "100%", justifyContent: "center", opacity: isSwitching ? 0.7 : 1 }}
                >
                  {isActive ? "✓ Plan Activo" : isSwitching ? "Cambiando…" : `Activar Plan ${plan.name}`}
                </Button>
              </article>
            );
          })}
        </div>

        <div style={{ textAlign: "center", marginTop: "40px" }}>
          <a href="#/sistema" className="button button-primary" style={{ padding: "12px 28px", fontSize: "14px" }}>
            <span>Volver a la Terminal Cuantitativa</span>
            <ArrowRight size={16} />
          </a>
        </div>
      </main>
    </>
  );
}
