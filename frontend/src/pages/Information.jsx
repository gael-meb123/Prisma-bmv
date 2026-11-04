import React from "react";
import { ArrowRight, BookOpen, Database, ShieldCheck, Scale, CheckCircle2 } from "lucide-react";
import { Header } from "../components/Header";
import { Badge, Notice } from "../components/UI";
import { STATUS } from "../utils/presentation.mjs";

export function Methodology() {
  return (
    <>
      <Header context="inner" />
      <main id="main-content" className="information-page container" style={{ maxWidth: "1000px", margin: "40px auto", padding: "0 20px" }}>
        <span className="eyebrow">METODOLOGÍA ECONOMÉTRICA</span>
        <h1 style={{ color: "var(--navy)", fontSize: "36px", margin: "8px 0" }}>
          Panel G2 Pooled Logit e Inferencia IRLS Newton-Raphson
        </h1>
        <p className="page-lead" style={{ fontSize: "16px", color: "var(--muted)", lineHeight: "1.6", marginBottom: "32px" }}>
          La formulación econométrica de Prisma BMV descarta las redes neuronales opacas de caja negra. El Panel G2 modela el horizonte prospectivo a 5 sesiones bursátiles con rigurosa convergencia determinista.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "20px" }}>
          <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "20px" }}>
            <span style={{ fontSize: "12px", fontWeight: "700", color: "#079baa", textTransform: "uppercase" }}>01 · Variable Objetivo Prospectiva</span>
            <h3 style={{ fontSize: "16px", color: "var(--navy)", margin: "8px 0" }}>Horizonte a 5 Sesiones (t+5)</h3>
            <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.5" }}>
              Y_t = 1 si PPP(t+5) &gt; PPP(t), 0 de lo contrario. Evita el ruido intradiario al evaluar el rendimiento acumulado neto en una semana bursátil completa.
            </p>
          </div>

          <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "20px" }}>
            <span style={{ fontSize: "12px", fontWeight: "700", color: "#10b981", textTransform: "uppercase" }}>02 · Regresor Ortogonal Clave</span>
            <h3 style={{ fontSize: "16px", color: "var(--navy)", margin: "8px 0" }}>ret_10_rel_panel</h3>
            <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.5" }}>
              Diferencial relativo frente a las demás emisoras del panel a 10 sesiones. Captura anomalías de sobreventa extrema donde la media estadística ejerce presión de reversión alcista.
            </p>
          </div>

          <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "20px" }}>
            <span style={{ fontSize: "12px", fontWeight: "700", color: "#d97706", textTransform: "uppercase" }}>03 · Optimización Matricial Pura</span>
            <h3 style={{ fontSize: "16px", color: "var(--navy)", margin: "8px 0" }}>IRLS Newton-Raphson</h3>
            <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: "1.5" }}>
              Cálculo iterativo directo sobre matrices NumPy sin librerías externas opacas. Convergencia garantizada con tolerancia estricta de 10^-7.
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
    </>
  );
}

export function Sources() {
  return (
    <>
      <Header context="inner" />
      <main id="main-content" className="information-page container" style={{ maxWidth: "1000px", margin: "40px auto", padding: "0 20px" }}>
        <span className="eyebrow">INTEGRIDAD Y REGULACIÓN</span>
        <h1 style={{ color: "var(--navy)", fontSize: "36px", margin: "8px 0" }}>
          Fuentes Oficiales BMV y Verificación SHA-256
        </h1>
        <p className="page-lead" style={{ fontSize: "16px", color: "var(--muted)", lineHeight: "1.6", marginBottom: "32px" }}>
          La procedencia de los datos en Prisma BMV es 100% oficial y auditable. Cada boletín bursátil descargado por AWS Lambda es sellado con un hash criptográfico inmutable.
        </p>

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
    </>
  );
}

export function InformationStates() {
  return (
    <>
      <Header context="inner" />
      <main id="main-content" className="information-page container" style={{ maxWidth: "1000px", margin: "40px auto", padding: "0 20px" }}>
        <span className="eyebrow">DICCIONARIO DE ESTADOS</span>
        <h1 style={{ color: "var(--navy)", fontSize: "36px", margin: "8px 0" }}>
          Estados de Auditoría e Inferencia
        </h1>
        <p className="page-lead" style={{ fontSize: "16px", color: "var(--muted)", lineHeight: "1.6", marginBottom: "32px" }}>
          Cada cifra mostrada en la terminal cuenta con una semántica explícita para evitar interpretaciones ambiguas.
        </p>

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
    </>
  );
}
