import React from "react";
import { Header } from "../components/Header";
import { useAccount } from "../hooks/useAccount";
import { publicRegistration } from "../lib/auth.mjs";

export function Experimental() {
  const account = useAccount();
  const yahooActiva = import.meta.env.VITE_YAHOO_OBSERVACIONES === "true";
  return <>
    <Header />
    <main id="main-content" className="bk-container" style={{ maxWidth: 900, padding: "64px 20px" }}>
      <span className="bk-eyebrow">PRISMA BMV · TERMINAL CUANTITATIVA EN AWS</span>
      <h1>Consulta de mercado, gobernanza y terminal</h1>
      <p>Conectada a la API institucional en AWS, almacenamiento versionado en Amazon S3 e identidad sobre Amazon Cognito y DynamoDB.</p>
      <div className="bk-alert bk-alert-info" role="status">
        Ingesta diaria BMV automatizada activa (ventana limpia hacia 21/21 sesiones). Señales G2, consenso y panel ajustado permanecen bloqueados hasta cerrar validaciones.
      </div>
      <p>
        {yahooActiva
          ? "Las observaciones secundarias de Yahoo Finance (.MX) están habilitadas en módulo separado como cierre diario reportado; nunca sustituyen el PPP oficial BMV ni alimentan modelos."
          : "Los datos secundarios de Yahoo Finance se mantienen separados del PPP oficial BMV y no alimentan modelos."}
      </p>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 18 }}>
        <a className="bk-btn bk-btn-primary" href={account.session ? "#/sistema" : "#/acceso"}>
          {account.session ? "Abrir mi terminal" : "Ingresar a la terminal"}
        </a>
        {publicRegistration && !account.session && <a className="bk-btn bk-btn-ghost" href="#/registro">Abrir cuenta Explorer</a>}
        <a className="bk-btn bk-btn-outline" href="#/planes">Ver planes</a>
      </div>
    </main>
  </>;
}

export function ExperimentalNoDisponible() {
  return <>
    <Header />
    <main id="main-content" className="bk-container" style={{ maxWidth: 800, padding: "64px 20px" }}>
      <h1>Sección en preparación</h1>
      <p>Esta sección se habilitará cuando concluya la validación integral de fuentes y modelos.</p>
      <a className="bk-btn bk-btn-primary" href="#/">Volver al inicio</a>
    </main>
  </>;
}
