import React, { lazy, Suspense, useEffect, useState } from "react";
import { Header, Footer } from "./components/Header";
import { Guide } from "./components/Guide";
import { Tour } from "./components/Tour";
import { Landing } from "./pages/Landing";
import { Plans } from "./pages/Plans";
import { Access } from "./pages/Access";
import { Methodology, Sources, InformationStates } from "./pages/Information";
import { useCatalog } from "./hooks/useCatalog";
import { useAccount } from "./hooks/useAccount";
import { Admin } from "./pages/Admin";
import { TerminalGate } from "./pages/TerminalGate";
import { EmptyArt } from "./components/Illustrations";
import { MacroTicker } from "./components/MacroTicker/MacroTicker";
import { Security } from "./pages/Security";
import { Experimental, ExperimentalNoDisponible } from "./pages/Experimental";
import { isCognito } from "./lib/auth.mjs";
const Report = lazy(() => import("./pages/Report").then(m => ({ default: m.Report })));
const Terminal = lazy(() => import("./pages/Terminal").then(m => ({ default: m.Terminal })));

// "#/ruta#ancla" → "/ruta" (el ancla la usa cada página para desplazarse).
function currentRoute() {
  if (!location.hash.startsWith("#/")) return "/";
  return location.hash.slice(1).split("#")[0] || "/";
}

// Las rutas de la terminal exigen sesión iniciada.
const isTerminalRoute = (route) => route.startsWith("/sistema") || route.startsWith("/ficha");

// Al iniciar/cerrar sesión o cambiar de plan, la app se vuelve a montar para que
// los datos (señales, serie) se recarguen con los permisos nuevos.
export default function App() {
  const account = useAccount();
  const identidad = account.session?.user_id || account.session?.user?.id || account.profile?.id || "anon";
  const key = isCognito ? identidad : `${identidad}:${account.role}`;
  return <AppInner key={key} />;
}

function AppInner() {
  const real = import.meta.env.VITE_REQUIRE_REAL_API === "true";
  // La ficha y las señales no están validadas en el modo de API real.
  const catalog = useCatalog(import.meta.env.VITE_REQUIRE_REAL_API !== "true");
  const account = useAccount();
  const [route, setRoute] = useState(currentRoute);
  const [seccion, setSeccion] = useState("resumen");
  const [selectedTicker, setSelectedTicker] = useState("WALMEX");

  useEffect(() => {
    function handleHashChange() {
      setRoute(currentRoute());
      if (!location.hash.split("#")[2]) window.scrollTo({ top: 0, behavior: "instant" });
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  // Señales en el formato de la ficha ejecutiva y de la auditoría institucional.
  const senalesTicker = catalog.senales.filter((s) => s.emisora === selectedTicker);

  let content;
  if (isTerminalRoute(route) && !account.ready) {
    content = (
      <>
        <Header />
        <main id="main-content" className="bk-container" style={{ padding: "80px 0", textAlign: "center", color: "var(--bk-muted)" }}>
          Verificando sesión…
        </main>
      </>
    );
  } else if (isTerminalRoute(route) && !account.session) {
    content = <TerminalGate />;
  } else if (route === "/") {
    content = real ? <Experimental /> : <Landing />;
  } else if (real && ["/metodologia", "/fuentes", "/estados"].includes(route)) {
    content = <ExperimentalNoDisponible />;
  } else if (route === "/planes") {
    content = <Plans />;
  } else if (route === "/acceso" || route === "/registro") {
    content = <Access key={route} initialMode={route === "/registro" ? "register" : "login"} />;
  } else if (route === "/admin") {
    content = <Admin />;
  } else if (route === "/seguridad") {
    content = <Security />;
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
  } else if (route.startsWith("/sistema")) {
    content = (
      <Terminal
        route={route}
        seccion={seccion}
        setSeccion={setSeccion}
        selectedTicker={selectedTicker}
        setSelectedTicker={setSelectedTicker}
        senalesTicker={senalesTicker}
        onOpenReport={() => {
          window.location.hash = "/ficha";
        }}
      />
    );
  } else {
    content = (
      <>
        <Header />
        <main className="bk-container" style={{ padding: "80px 0", textAlign: "center" }}>
          <EmptyArt />
          <h1 style={{ color: "var(--bk-navy)" }}>Página no encontrada</h1>
          <p>La dirección no existe en Prisma BMV.</p>
          <a href="#/" className="bk-btn bk-btn-primary">Volver al inicio</a>
        </main>
        <Footer />
      </>
    );
  }

  return (
    <>
      <a className="skip-link" href="#main-content">
        Saltar al contenido principal
      </a>

      <Suspense fallback={<main id="main-content" className="bk-container" role="status">Cargando sección…</main>}>
        {content}
      </Suspense>

      {/* Prismi: asistente cuantitativo en AWS con guardrails y contexto real */}
      <Guide route={route} phase={seccion} selectedTicker={selectedTicker} />
      {!real && <Tour route={route} />}
      {!real && <MacroTicker />}
    </>
  );
}
