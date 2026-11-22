import React from "react";
import { Header } from "../components/Header";
import { useAccount } from "../hooks/useAccount";
import { publicRegistration } from "../lib/auth.mjs";

export function Experimental() {
  const account = useAccount();
  return <>
    <Header />
    <main id="main-content" className="bk-container" style={{ maxWidth: 900, padding: "64px 20px" }}>
      <span className="bk-eyebrow">PRISMA BMV · VERSIÓN EXPERIMENTAL</span>
      <h1>Consulta de mercado y terminal</h1>
      <p>Esta versión conecta con la API y Cognito de prueba. La cobertura es parcial y los datos pueden no estar actualizados.</p>
      <div className="bk-alert bk-alert-info" role="status">
        La ingesta automática está pausada. Señales, seguimiento y panel estadístico ajustado aún no están disponibles.
      </div>
      <p>Los datos de contingencia de Yahoo se identifican por separado y no son PPP oficiales de BMV. No se muestran precios secundarios en esta versión.</p>
      <a className="bk-btn bk-btn-primary" href={account.session ? "#/sistema" : "#/acceso"}>
        {account.session ? "Abrir mi terminal" : "Ingresar con una cuenta de prueba"}
      </a>
      {publicRegistration && !account.session && <a className="bk-btn bk-btn-ghost" href="#/registro">Abrir cuenta Explorer</a>}
    </main>
  </>;
}

export function ExperimentalNoDisponible() {
  return <>
    <Header />
    <main id="main-content" className="bk-container" style={{ maxWidth: 800, padding: "64px 20px" }}>
      <h1>Sección en preparación</h1>
      <p>Esta función todavía no está disponible en la versión experimental.</p>
      <a className="bk-btn bk-btn-primary" href="#/">Volver al inicio</a>
    </main>
  </>;
}
