import React, { useEffect, useState } from "react";
import {
  BarChart3,
  BrainCircuit,
  Cloud,
  FileText,
  Home,
  LayoutDashboard,
  Lock,
  LogOut,
  Menu,
  ShieldCheck,
  Tag,
  Timer,
  Users,
} from "lucide-react";
import { Logo } from "../components/UI";
import { Mascot } from "../components/Mascot";
import { iniciales } from "../components/Header";
import { PlanGate } from "../components/PlanGate";
import { EvidenceDialog } from "../components/EvidenceDialog";
import { Calidad, Gobernanza, Mercado, Resumen, Senales, Seguimiento } from "../components/terminal/Secciones";
import { useAccount } from "../hooks/useAccount";
import { useTerminalData } from "../hooks/useTerminalData";
import { canAccessTicker, PLANS } from "../plans.mjs";

export const SECCIONES = [
  { id: "resumen", label: "Resumen", icon: LayoutDashboard, titulo: "Resumen de tu terminal" },
  { id: "mercado", label: "Mercado", icon: BarChart3, titulo: "Monitor de mercado" },
  { id: "senales", label: "Señales", icon: BrainCircuit, titulo: "Señales de los modelos", porEmisora: true },
  { id: "seguimiento", label: "Seguimiento t+5", icon: Timer, titulo: "Seguimiento de señales", porEmisora: true },
  { id: "calidad", label: "Calidad de modelos", icon: ShieldCheck, titulo: "Calidad de los modelos" },
  { id: "gobernanza", label: "Datos y gobernanza", icon: Cloud, titulo: "Datos y gobernanza en AWS" },
];
const IDS = SECCIONES.map((s) => s.id);

export const EMISORAS = ["WALMEX", "GMEXICO", "GFNORTE", "AMX", "FEMSA", "CEMEX", "BIMBO", "GAP", "PE&OLES", "AC", "ASUR", "GFINBUR", "VESTA", "LIVEPOL", "GRUMA"];

export function seccionDeRuta(route) {
  const parte = route.replace(/^\/sistema\/?/, "").split("/")[0];
  return IDS.includes(parte) ? parte : null;
}

function saludo() {
  const h = new Date().getHours();
  if (h < 12) return "Buenos días";
  if (h < 19) return "Buenas tardes";
  return "Buenas noches";
}

export function Terminal({ route, seccion, setSeccion, selectedTicker, setSelectedTicker, senalesTicker, onOpenReport }) {
  const account = useAccount();
  const [menuOpen, setMenuOpen] = useState(false);
  const [fecha, setFecha] = useState(null); // null = última sesión
  const [fechaSenal, setFechaSenal] = useState(null);
  const [planGate, setPlanGate] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [planError, setPlanError] = useState("");

  const emisora = selectedTicker;
  const permitido = canAccessTicker(account.role, emisora);
  const datos = useTerminalData({ emisora, fecha, fechaSenal, permitido, conSesion: Boolean(account.session) });
  const actual = SECCIONES.find((s) => s.id === seccion) || SECCIONES[0];

  // /sistema/<seccion> abre esa sección (accesos rápidos de la landing).
  useEffect(() => {
    const s = seccionDeRuta(route);
    if (s) setSeccion(s);
  }, [route, setSeccion]);

  // El recorrido guiado cambia de sección con el evento prisma:tour-phase.
  useEffect(() => {
    function onPhase(e) {
      if (IDS.includes(e.detail)) setSeccion(e.detail);
    }
    window.addEventListener("prisma:tour-phase", onPhase);
    return () => window.removeEventListener("prisma:tour-phase", onPhase);
  }, [setSeccion]);

  function irA(id) {
    setSeccion(id);
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function seleccionarEmisora(t) {
    if (!canAccessTicker(account.role, t)) {
      setPlanGate(t);
      return;
    }
    setFechaSenal(null);
    setSelectedTicker(t);
  }

  async function cambiarPlan(e) {
    setPlanError("");
    try {
      await account.switchPlan(e.target.value);
    } catch (err) {
      setPlanError(err.message || "No se pudo cambiar el plan.");
    }
  }

  async function salir() {
    await account.leave();
    window.location.hash = "/";
  }

  const ctx = {
    account,
    emisora,
    datos,
    permitido,
    irA,
    fechaSenal,
    setFechaSenal,
    senalesTicker,
    onOpenReport,
    onSelectTicker: seleccionarEmisora,
    onPlanGate: (t) => setPlanGate(t),
    onShowEvidence: (ev) => setEvidence(ev),
    puedeVer: (t) => canAccessTicker(account.role, t),
  };

  const fechas = datos.fechas.data || [];
  const nombre = account.user?.name || account.user?.email || "";

  return (
    <div className={`tm ${menuOpen ? "is-menu-open" : ""}`}>
      <div className="tm-overlay" onClick={() => setMenuOpen(false)} aria-hidden="true" />

      {/* ---------------------------------------------------- Menú lateral */}
      <aside className="tm-side" aria-label="Menú de la terminal">
        <Logo />
        <div className="tm-usercard">
          <div className="tm-usercard-top">
            <span className="bk-avatar">{iniciales(account.user?.name, account.user?.email)}</span>
            <div style={{ minWidth: 0 }}>
              <strong style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{nombre.split(" ")[0] || "Mi cuenta"}</strong>
              <span>Plan {account.plan.name}</span>
            </div>
          </div>
          <label style={{ display: "grid", gap: 4, fontSize: 11, color: "#9fc0d6", fontWeight: 700 }}>
            Cambiar plan (demo)
            <select value={account.role} onChange={cambiarPlan}>
              {PLANS.map((p) => (
                <option key={p.id} value={p.id}>{p.name} · {p.price.amount}</option>
              ))}
            </select>
          </label>
          {planError && <span role="alert" style={{ color: "#fca5a5", fontSize: 11 }}>{planError}</span>}
        </div>

        <nav className="tm-nav" data-tour="menu" aria-label="Secciones">
          <span className="tm-nav-label">Mi terminal</span>
          {SECCIONES.map(({ id, label, icon: Icon, porEmisora }) => (
            <button
              key={id}
              type="button"
              className={seccion === id ? "is-active" : ""}
              aria-current={seccion === id ? "page" : undefined}
              onClick={() => irA(id)}
            >
              <Icon size={18} /> {label}
              {porEmisora && !permitido && <Lock size={13} className="tm-lock" aria-label="Fuera de tu plan" />}
            </button>
          ))}
        </nav>

        <div className="tm-side-foot tm-nav">
          <button type="button" onClick={onOpenReport}><FileText size={17} /> Ficha ejecutiva</button>
          <a href="#/planes"><Tag size={17} /> Planes</a>
          {account.userRole === "admin" && <a href="#/admin"><Users size={17} /> Administración</a>}
          <a href="#/"><Home size={17} /> Portal</a>
          <button type="button" onClick={salir}><LogOut size={17} /> Cerrar sesión</button>
        </div>
      </aside>

      {/* ---------------------------------------------------- Contenido */}
      <div className="tm-main">
        <header className="tm-top">
          <button type="button" className="tm-icon-btn tm-mobile-toggle" onClick={() => setMenuOpen(true)} aria-label="Abrir menú">
            <Menu size={18} />
          </button>
          <div className="tm-top-title">
            <strong>{actual.titulo}</strong>
            <span>{saludo()}{nombre ? `, ${nombre.split(" ")[0]}` : ""} · datos oficiales del boletín BMV</span>
          </div>
          <div className="tm-top-controls">
            <div className="tm-control" data-tour="selector-emisora">
              <label htmlFor="tm-emisora">Emisora</label>
              <select id="tm-emisora" value={emisora} onChange={(e) => seleccionarEmisora(e.target.value)}>
                {EMISORAS.map((t) => (
                  <option key={t} value={t}>
                    {t}{canAccessTicker(account.role, t) ? "" : " 🔒"}
                  </option>
                ))}
              </select>
            </div>
            {fechas.length > 0 && (
              <div className="tm-control">
                <label htmlFor="tm-fecha">Sesión</label>
                <select id="tm-fecha" value={fecha || fechas[0]} onChange={(e) => setFecha(e.target.value === fechas[0] ? null : e.target.value)}>
                  {fechas.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
            )}
            <button
              type="button"
              className="tm-icon-btn"
              onClick={() => window.dispatchEvent(new CustomEvent("prisma:open-guide"))}
              aria-label="Abrir a Prismi"
              title="Pregúntale a Prismi"
              style={{ width: 44, height: 44, padding: 0, overflow: "hidden" }}
            >
              <Mascot size={30} expression="happy" title="" />
            </button>
          </div>
        </header>

        <main id="main-content" className="tm-content">
          {seccion === "resumen" && <Resumen ctx={ctx} />}
          {seccion === "mercado" && <Mercado ctx={ctx} />}
          {seccion === "senales" && <Senales ctx={ctx} />}
          {seccion === "seguimiento" && <Seguimiento ctx={ctx} />}
          {seccion === "calidad" && <Calidad ctx={ctx} />}
          {seccion === "gobernanza" && <Gobernanza ctx={ctx} />}
          <p className="bk-muted" style={{ fontSize: 12, margin: "8px 0 0" }}>
            Probabilidades estadísticas sobre el PPP oficial de la BMV; no constituyen recomendación ni asesoría de inversión.
          </p>
        </main>
      </div>

      {planGate && <PlanGate ticker={planGate} onClose={() => setPlanGate(null)} />}
      {evidence && <EvidenceDialog evidence={evidence} onClose={() => setEvidence(null)} />}
    </div>
  );
}
