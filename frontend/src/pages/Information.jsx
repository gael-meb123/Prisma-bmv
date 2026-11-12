import React from "react";
import { ArrowRight, BookOpen, Database, ShieldCheck, Scale, CheckCircle2 } from "lucide-react";
import { Header, Footer, PageHero } from "../components/Header";
import { Badge, Notice } from "../components/UI";
import { STATUS } from "../utils/presentation.mjs";

export function Methodology() {
  return (
    <>
      <Header />
      <PageHero eyebrow="Metodología econométrica" title="Panel G2 Pooled Logit e Inferencia IRLS Newton-Raphson" lead="La formulación econométrica de Prisma BMV descarta las redes neuronales opacas de caja negra. El Panel G2 modela el horizonte prospectivo a 5 sesiones bursátiles con rigurosa convergencia determinista." />
      <main id="main-content" className="information-page bk-container bk-page-body" style={{ maxWidth: "1080px", paddingBottom: "24px" }}>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "20px" }}>
          <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "20px" }}>
            <span style={{ fontSize: "12px", fontWeight: "700", color: "#079baa", textTransform: "uppercase" }}>01 · Variable Objetivo Ajustada</span>
            <h3 style={{ fontSize: "16px", color: "var(--navy)", margin: "8px 0" }}>Retorno Total a 5 Sesiones (t+5)</h3>
            <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.5" }}>
              Y_t = 1 si PPP_adj(t+5) &gt; PPP(t), integrando 284 eventos corporativos verificados (dividendos y splits) para eliminar falsos negativos en ventanas ex-dividendo.
            </p>
          </div>

          <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "20px" }}>
            <span style={{ fontSize: "12px", fontWeight: "700", color: "#10b981", textTransform: "uppercase" }}>02 · Cinco Variantes G2 + Gap Intradiario</span>
            <h3 style={{ fontSize: "16px", color: "var(--navy)", margin: "8px 0" }}>V1–V5 y G2_V4_F1_GAP</h3>
            <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.5" }}>
              Combina reversión relativa transversal (ret_10_rel_panel), agotamiento corto DM5 (V4), adaptación por régimen/sector (V5) y el diferencial intradiario Último Hecho vs PPP (gap_uh_ppp).
            </p>
          </div>

          <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "20px" }}>
            <span style={{ fontSize: "12px", fontWeight: "700", color: "#d97706", textTransform: "uppercase" }}>03 · Calibración y Asignación ¼-Kelly</span>
            <h3 style={{ fontSize: "16px", color: "var(--navy)", margin: "8px 0" }}>IRLS + Kelly Fraccional</h3>
            <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.5" }}>
              Probabilidades calibradas (ECE = 0.0123, BSS &gt; 0) acopladas a una política ¼-Kelly con zona de abstención p &lt; 0.52 y costos de 20 bps round-trip (Sharpe Neto +1.04 en TEST).
            </p>
          </div>
        </div>

        <div style={{ marginTop: "32px", textAlign: "center" }}>
          <a href="#/sistema" className="button button-primary" style={{ padding: "10px 24px" }}>
            <span>Abrir Terminal con Modelos G2</span>
            <ArrowRight size={16} />
          </a>
        </div>
      </main>
      <Footer />
    </>
  );
}

export function Sources() {
  return (
    <>
      <Header />
      <PageHero eyebrow="Integridad y regulación" title="Fuentes Oficiales BMV y Verificación SHA-256" lead="La procedencia de los datos en Prisma BMV es 100% oficial y auditable. Cada boletín bursátil descargado por AWS Lambda es sellado con un hash criptográfico inmutable." />
      <main id="main-content" className="information-page bk-container bk-page-body" style={{ maxWidth: "1080px", paddingBottom: "24px" }}>

        <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "14px", padding: "24px", marginBottom: "24px" }}>
          <h3 style={{ color: "var(--navy)", fontSize: "18px", margin: "0 0 12px 0" }}>Boletín Bursátil Diario de la BMV</h3>
          <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.6" }}>
            Documento regulatorio oficial publicado al cierre de cada jornada bursátil en <code style={{ color: "var(--teal-dark)", background: "#eef8f8", padding: "2px 6px", borderRadius: "4px" }}>https://www.bmv.com.mx/docs-pub/rss/boletinYYYYMMDD.html</code>. Contiene los Precios Promedio Ponderados oficiales negociados por los intermediarios bursátiles autorizados por la CNBV.
          </p>
          <div style={{ marginTop: "14px", display: "flex", gap: "10px", alignItems: "center" }}>
            <span className="badge badge-available">
              <CheckCircle2 size={12} style={{ marginRight: 4 }} />
              Verificación Criptográfica Diaria Habilitada
            </span>
          </div>
        </div>

        <div style={{ textAlign: "center", marginTop: "28px" }}>
          <a href="#/sistema" className="button button-primary" style={{ padding: "10px 24px" }}>
            <span>Ver Cotizaciones en la Terminal</span>
            <ArrowRight size={16} />
          </a>
        </div>
      </main>
      <Footer />
    </>
  );
}

export function InformationStates() {
  return (
    <>
      <Header />
      <PageHero eyebrow="Diccionario de estados" title="Estados de Auditoría e Inferencia" lead="Cada cifra mostrada en la terminal cuenta con una semántica explícita para evitar interpretaciones ambiguas." />
      <main id="main-content" className="information-page bk-container bk-page-body" style={{ maxWidth: "1080px", paddingBottom: "24px" }}>

        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          {Object.entries(STATUS).map(([key, item]) => (
            <div key={key} style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "10px", padding: "16px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "16px" }}>
              <div>
                <strong style={{ fontSize: "14px", color: "var(--navy)", display: "block" }}>{item.label}</strong>
                <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "var(--muted)" }}>{item.description}</p>
              </div>
              <Badge status={key} />
            </div>
          ))}
        </div>
      </main>
      <Footer />
    </>
  );
}
