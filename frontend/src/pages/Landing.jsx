import React from "react";
import {
  ArrowRight,
  TrendingUp,
  ShieldCheck,
  Database,
  BrainCircuit,
  BarChart3,
  Check,
  Scale,
  Sparkles,
  ExternalLink,
  Lock
} from "lucide-react";
import { Header } from "../components/Header";
import { Logo, Button } from "../components/UI";
import { PLANS } from "../plans.mjs";

export function Landing() {
  const benefits = [
    [
      Scale,
      "Eliminación de Distorsiones de Cierre",
      "Las subastas de cierre en brokers convencionales sufren distorsiones por lotes ilíquidos. El PPP oficial pondera el 100% de los lotes reales negociados."
    ],
    [
      BrainCircuit,
      "Consenso Econométrico Multi-Modelo (G2)",
      "Panel balanceado de regresión logística agrupada (Pooled Logit) optimizado mediante el algoritmo Newton-Raphson IRLS puro a 5 sesiones bursátiles."
    ],
    [
      Database,
      "Data Lakehouse Serverless en AWS",
      "Ingesta automática diaria a las 16:45 CDMX mediante EventBridge y Lambda, con sellado criptográfico SHA-256 sobre el boletín oficial."
    ]
  ];

  const faqs = [
    [
      "¿Por qué es superior el Precio Promedio Ponderado (PPP) frente al precio de cierre?",
      "El último precio de cierre en brokers minoristas puede manipularse o distorsionarse en los últimos 5 minutos de subasta. El PPP de la BMV considera el volumen ponderado de toda la jornada, siendo el estándar regulatorio para la liquidación de derivados y fondos institucionales."
    ],
    [
      "¿Cómo funciona el consenso del Panel G2?",
      "Ejecuta simultáneamente 3 variantes ortogonales del modelo logístico (V1 Calibrado, V2 Zona Neutral y V3 Alta Discriminación). Una señal de compra exige convergencia unánime sobre el horizonte prospectivo a 5 sesiones (t+5)."
    ],
    [
      "¿Qué incluye el plan gratuito Explorer?",
      "Acceso libre al monitoreo en vivo de las 15 emisoras del IPC, inferencia prospectiva completa para WALMEX, sello criptográfico SHA-256 y consultas a Prismi AI."
    ]
  ];

  return (
    <>
      <Header context="landing" />

      <main id="main-content" className="landing">
        {/* Sección Hero */}
        <section className="hero" style={{ padding: "64px 20px 48px 20px", background: "linear-gradient(180deg, #f5f8fb 0%, #eaf1f6 100%)" }}>
          <div className="container" style={{ maxWidth: "1080px", margin: "0 auto", textAlign: "center" }}>
            <span className="eyebrow" style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <Sparkles size={14} style={{ color: "#079baa" }} />
              PLATAFORMA CUANTITATIVA INSTITUCIONAL · BOLSA MEXICANA DE VALORES
            </span>

            <h1 data-tour="hero" style={{ fontSize: "clamp(32px, 4.5vw, 54px)", color: "var(--navy)", margin: "16px 0", lineHeight: "1.15" }}>
              Inferencia Bursátil sobre <br />
              <em style={{ color: "var(--teal-dark)" }}>Precios Oficiales Ponderados (PPP)</em>
            </h1>

            <p className="hero-lead" style={{ fontSize: "17px", color: "var(--muted)", maxWidth: "760px", margin: "0 auto 28px auto", lineHeight: "1.6" }}>
              Supera el sesgo de las subastas de cierre. Prisma BMV ingesta y audita directamente el boletín regulatorio de la BMV, procesando modelos econométricos de panel (G2) para anticipar rendimientos acumulados en el horizonte a 5 sesiones.
            </p>

            <div style={{ display: "flex", gap: "14px", justifyContent: "center", flexWrap: "wrap" }}>
              <a href="#/sistema" data-tour="cta-sistema" className="button button-primary" style={{ padding: "12px 28px", fontSize: "15px", background: "#079baa", borderColor: "#1fd2ea" }}>
                <span>Ingresar a la Terminal Cuantitativa</span>
                <ArrowRight size={16} />
              </a>
              <a href="#/planes" className="button button-outline" style={{ padding: "12px 24px", fontSize: "15px" }}>
                Ver Planes de Suscripción
              </a>
            </div>
          </div>
        </section>

        {/* Sección de Comparativa: Cierre vs PPP Oficial */}
        <section data-tour="por-que-ppp" className="section container" style={{ maxWidth: "1080px", margin: "48px auto", padding: "0 20px" }}>
          <div style={{ textAlign: "center", marginBottom: "32px" }}>
            <span className="eyebrow">FUNDAMENTO CUANTITATIVO</span>
            <h2 style={{ color: "var(--navy)", fontSize: "28px" }}>¿Por qué PPP Oficial y no Precio de Cierre?</h2>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px" }}>
            <div style={{ background: "#ffffff", border: "1.5px solid #fecdd3", borderRadius: "14px", padding: "24px" }}>
              <strong style={{ color: "#e11d48", fontSize: "15px", textTransform: "uppercase", letterSpacing: "0.5px", display: "block", marginBottom: "8px" }}>
                ✕ Precio de Cierre Convencional (Retail)
              </strong>
              <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.6" }}>
                El último precio transaccionado suele determinarse en subastas de cierre ilíquidas, donde posturas aisladas distorsionan artificialmente la cotización sin reflejar la valoración ponderada del mercado.
              </p>
            </div>

            <div style={{ background: "#ffffff", border: "1.5px solid #a7f3d0", borderRadius: "14px", padding: "24px" }}>
              <strong style={{ color: "#059669", fontSize: "15px", textTransform: "uppercase", letterSpacing: "0.5px", display: "block", marginBottom: "8px" }}>
                ✓ PPP Oficial BMV (Prisma Analytics)
              </strong>
              <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.6" }}>
                El Precio Promedio Ponderado oficial considera el 100% del volumen negociado a lo largo de toda la jornada bursátil. Es el estándar regulatorio inviolable para la valoración y liquidación patrimonial.
              </p>
            </div>
          </div>
        </section>

        {/* Pilares Tecnológicos */}
        <section id="capacidades" data-tour="capacidades" className="section container" style={{ maxWidth: "1080px", margin: "48px auto", padding: "0 20px" }}>
          <div style={{ textAlign: "center", marginBottom: "32px" }}>
            <span className="eyebrow">METODOLOGÍA INSTITUCIONAL</span>
            <h2 style={{ color: "var(--navy)", fontSize: "28px" }}>Pilares de Alta Disponibilidad y Rigor Matemático</h2>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "20px" }}>
            {benefits.map(([Icon, title, desc]) => (
              <article key={title} style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "14px", padding: "24px" }}>
                <div style={{ width: 42, height: 42, borderRadius: "10px", background: "#e6f6f9", color: "#079baa", display: "grid", placeItems: "center", marginBottom: "14px" }}>
                  <Icon size={22} />
                </div>
                <h3 style={{ fontSize: "16px", color: "var(--navy)", marginBottom: "8px" }}>{title}</h3>
                <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.6", margin: 0 }}>{desc}</p>
              </article>
            ))}
          </div>
        </section>

        {/* Sección de Planes Freemium */}
        <section id="planes" data-tour="planes" className="section container" style={{ maxWidth: "1080px", margin: "48px auto", padding: "0 20px" }}>
          <div style={{ textAlign: "center", marginBottom: "32px" }}>
            <span className="eyebrow">SUSCRIPCIONES FLEXIBLES</span>
            <h2 style={{ color: "var(--navy)", fontSize: "28px" }}>Planes Diseñados para Cada Perfil Cuantitativo</h2>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(290px, 1fr))", gap: "20px" }}>
            {PLANS.map((plan) => {
              const isPro = plan.id === "profesional";
              return (
                <div
                  key={plan.id}
                  style={{
                    background: isPro ? "linear-gradient(180deg, #f0fdfa 0%, #ffffff 100%)" : "#ffffff",
                    border: isPro ? "2px solid #079baa" : "1px solid var(--line)",
                    borderRadius: "16px",
                    padding: "28px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    position: "relative"
                  }}
                >
                  {isPro && (
                    <span style={{ position: "absolute", top: "-12px", left: "50%", transform: "translateX(-50%)", background: "#079baa", color: "#ffffff", fontSize: "11px", fontWeight: "800", padding: "3px 12px", borderRadius: "20px", textTransform: "uppercase" }}>
                      Recomendado
                    </span>
                  )}
                  <div>
                    <span className="eyebrow">{plan.audience}</span>
                    <h3 style={{ fontSize: "22px", color: "var(--navy)", margin: "4px 0" }}>{plan.name}</h3>
                    <div style={{ fontSize: "28px", fontWeight: "800", color: "var(--navy)", fontFamily: "monospace", margin: "12px 0 6px 0" }}>
                      {plan.price.amount} <small style={{ fontSize: "12px", color: "var(--muted)", fontWeight: "500" }}>{plan.price.detail}</small>
                    </div>
                    <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.5", marginBottom: "18px" }}>{plan.summary}</p>
                    <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px 0", fontSize: "13px", color: "var(--navy)" }}>
                      {plan.includes.map((inc) => (
                        <li key={inc} style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                          <Check size={16} style={{ color: "#10b981", flexShrink: 0 }} />
                          <span>{inc}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <a href="#/planes" className={`button ${isPro ? "button-primary" : "button-outline"}`} style={{ textAlign: "center", justifyContent: "center" }}>
                    Elegir Plan {plan.name}
                  </a>
                </div>
              );
            })}
          </div>
        </section>

        {/* Preguntas Frecuentes */}
        <section id="preguntas" className="section container" style={{ maxWidth: "860px", margin: "48px auto", padding: "0 20px" }}>
          <div style={{ textAlign: "center", marginBottom: "28px" }}>
            <span className="eyebrow">PREGUNTAS FRECUENTES</span>
            <h2 style={{ color: "var(--navy)", fontSize: "26px" }}>Resolución de Consultas Metodológicas</h2>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {faqs.map(([pregunta, respuesta]) => (
              <details key={pregunta} style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "10px", padding: "16px 20px", cursor: "pointer" }}>
                <summary style={{ fontWeight: "700", color: "var(--navy)", fontSize: "14px" }}>{pregunta}</summary>
                <p style={{ margin: "10px 0 0 0", fontSize: "13px", color: "var(--muted)", lineHeight: "1.6" }}>{respuesta}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Pie Institucional */}
        <footer style={{ borderTop: "1px solid var(--line)", background: "#ffffff", padding: "36px 20px", textAlign: "center", fontSize: "12px", color: "var(--muted)" }}>
          <div className="container" style={{ maxWidth: "1080px", margin: "0 auto" }}>
            <strong style={{ color: "var(--navy)", fontSize: "14px" }}>PRISMA BMV</strong>
            <p style={{ margin: "6px 0 0 0" }}>
              Plataforma Cuantitativa y Gobernanza Cloud de la Bolsa Mexicana de Valores. © 2026.
            </p>
          </div>
        </footer>
      </main>
    </>
  );
}
