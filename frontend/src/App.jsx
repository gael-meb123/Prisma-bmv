import React, { useState, useEffect, useRef } from "react";
import { Header } from "./components/Header";
import { Guide } from "./components/Guide";
import { Tour } from "./components/Tour";
import { PlanGate } from "./components/PlanGate";
import { LoadingDialog } from "./components/LoadingDialog";
import { EvidenceDialog } from "./components/EvidenceDialog";
import { MarketSelection } from "./components/MarketSelection/MarketSelection";
import { AnalysisPanel } from "./components/AnalysisPanel/AnalysisPanel";
import { ComparisonAudit } from "./components/ComparisonAudit/ComparisonAudit";
import { TerminalChartPlotly } from "./components/ComparisonAudit/TerminalChartPlotly";
import { Landing } from "./pages/Landing";
import { Plans } from "./pages/Plans";
import { Access } from "./pages/Access";
import { Methodology, Sources, InformationStates } from "./pages/Information";
import { Report } from "./pages/Report";
import { useCatalog } from "./hooks/useCatalog";
import { useAccount } from "./hooks/useAccount";
import { canAccessTicker } from "./plans.mjs";

function currentRoute() {
  return location.hash.startsWith("#/") ? location.hash.slice(1) : "/";
}

export default function App() {
  const catalog = useCatalog();
  const account = useAccount();
  const [route, setRoute] = useState(currentRoute);
  const [phase, setPhase] = useState("select"); // "select" | "analysis" | "audit"
  const [selectedTicker, setSelectedTicker] = useState("WALMEX");
  const [busy, setBusy] = useState(false);
  const [evidence, setEvidence] = useState(null);
  const [planGateTicker, setPlanGateTicker] = useState(null);

  // Escuchar cambios de ruta en el hash (#/sistema, #/planes, etc.)
  useEffect(() => {
    function handleHashChange() {
      const next = currentRoute();
      setRoute(next);
      window.scrollTo({ top: 0, behavior: "instant" });
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  // Filtrar señales activas para la emisora seleccionada
  const senalesTicker = catalog.senales.filter((s) => s.emisora === selectedTicker);
  const cotizacionTicker = catalog.mercado?.cotizaciones?.find((c) => c.emisora === selectedTicker);

  function handleSelectTicker(ticker) {
    setSelectedTicker(ticker);
    // Verificar si el ticker está permitido por el plan
    if (!canAccessTicker(account.role, ticker)) {
      setPlanGateTicker(ticker);
      return;
    }
    setBusy(true);
    setTimeout(() => {
      setBusy(false);
      setPhase("analysis");
    }, 400);
  }

  function handleOpenEvidence(ev) {
    setEvidence(ev);
  }

  // Enrutamiento de Vistas
  let content;
  if (route === "/") {
    content = <Landing />;
  } else if (route === "/planes") {
    content = <Plans />;
  } else if (route === "/acceso") {
    content = <Access />;
  } else if (route === "/metodologia") {
    content = <Methodology />;
  } else if (route === "/fuentes") {
    content = <Sources />;
  } else if (route === "/estados") {
    content = <InformationStates />;
  } else if (route.startsWith("/ficha")) {
    content = (
      <Report
        ticker={selectedTicker}
        senales={senalesTicker}
        onBack={() => {
          window.location.hash = "/sistema";
        }}
      />
    );
  } else if (route === "/sistema") {
    content = (
      <>
        <Header context="workspace" />

        <main id="main-content" className="workspace">
          {/* Panel Izquierdo Visual: Gráfica Financiera Plotly.js */}
          <section className="workspace-map" aria-label="Visualizador Cuantitativo Plotly">
            <TerminalChartPlotly
              serie={catalog.serie}
              ticker={selectedTicker}
              sector={cotizacionTicker?.sector}
            />
          </section>

          {/* Panel Derecho Analítico: Fases de Selección, Inferencia IA y Auditoría */}
          <section className="workspace-panel" aria-label="Panel Analítico Dual">
            {/* Navegación de Fases Internas */}
            <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid var(--line)", paddingBottom: "12px", marginBottom: "14px" }}>
              <button
                className={`button ${phase === "select" ? "button-primary" : "button-subtle"}`}
                onClick={() => setPhase("select")}
                style={{ padding: "6px 14px", fontSize: "12px" }}
              >
                1. Selección Mercado (BMV)
              </button>
              <button
                className={`button ${phase === "analysis" ? "button-primary" : "button-subtle"}`}
                onClick={() => {
                  if (canAccessTicker(account.role, selectedTicker)) {
                    setPhase("analysis");
                  } else {
                    setPlanGateTicker(selectedTicker);
                  }
                }}
                style={{ padding: "6px 14px", fontSize: "12px" }}
              >
                2. Inferencia IA (G2)
              </button>
              <button
                className={`button ${phase === "audit" ? "button-primary" : "button-subtle"}`}
                onClick={() => setPhase("audit")}
                style={{ padding: "6px 14px", fontSize: "12px" }}
              >
                3. Auditoría Temporal (t+5)
              </button>
            </div>

            {/* Renderizado de Módulos */}
            {phase === "select" && (
              <MarketSelection
                cotizaciones={catalog.mercado?.cotizaciones || []}
                selectedTicker={selectedTicker}
                onSelectTicker={handleSelectTicker}
                onShowEvidence={handleOpenEvidence}
                sha256={catalog.mercado?.kpis?.sha256_boletin}
                urlFuente={catalog.mercado?.kpis?.url_fuente}
              />
            )}

            {phase === "analysis" && (
              <AnalysisPanel
                ticker={selectedTicker}
                senales={senalesTicker}
                userRole={account.role}
                onPlanGate={(t) => setPlanGateTicker(t)}
                onOpenAudit={() => setPhase("audit")}
                onOpenReport={() => {
                  window.location.hash = "/ficha";
                }}
              />
            )}

            {phase === "audit" && (
              <ComparisonAudit
                ticker={selectedTicker}
                onBack={() => setPhase("analysis")}
                onOpenReport={() => {
                  window.location.hash = "/ficha";
                }}
              />
            )}
          </section>
        </main>
      </>
    );
  } else {
    content = (
      <>
        <Header context="inner" />
        <main className="container" style={{ padding: "80px 20px", textAlign: "center" }}>
          <h1>Página no encontrada</h1>
          <p>La dirección especificada no existe en la terminal.</p>
          <a href="#/" className="button button-primary">Volver al Inicio</a>
        </main>
      </>
    );
  }

  return (
    <>
      <a className="skip-link" href="#main-content">
        Saltar al contenido principal
      </a>

      {content}

      {/* Modal Nativo de Bloqueo Freemium */}
      {planGateTicker && (
        <PlanGate
          ticker={planGateTicker}
          onClose={() => setPlanGateTicker(null)}
        />
      )}

      {/* Modal de Carga con PrismiPulse */}
      <LoadingDialog
        active={busy}
        title={`Consultando modelos econométricos para ${selectedTicker}…`}
        detail="Ponderando cotizaciones oficiales e inferencia matricial IRLS…"
        steps={[
          { id: "quote", label: "Cotización oficial verificada", status: "complete" },
          { id: "g2", label: "Ejecución de los 3 modelos G2", status: "complete" },
          { id: "consensus", label: "Evaluación de consenso unánime", status: "active" }
        ]}
        onCancel={() => setBusy(false)}
      />

      {/* Modal de Auditoría de Evidencia SHA-256 */}
      {evidence && (
        <EvidenceDialog
          evidence={evidence}
          onClose={() => setEvidence(null)}
        />
      )}

      {/* Mascota Interactiva Prismi */}
      <Guide
        route={route}
        phase={phase}
        selectedTicker={selectedTicker}
        busy={busy}
      />

      {/* Tour Onboarding Interactivo */}
      <Tour route={route} />
    </>
  );
}
