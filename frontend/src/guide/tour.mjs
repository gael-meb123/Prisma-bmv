// Recorrido guiado de Prisma BMV con Prismi, el billete superhéroe.
// Texto 100% estático: no llama a la API ni a ningún servicio.
//
// Cada paso define:
//  - id:         identificador estable
//  - route:      ruta (hash) donde vive el paso: "/", "/sistema", ...
//  - phase:      (opcional, solo /sistema) fase que el tour activa: "select" | "analysis" | "audit"
//  - target:     lista de selectores CSS; se usa el primero que exista y sea visible.
//                Recomendado: marcar el elemento con data-tour="..." y dejar un respaldo.
//                null = Prismi se coloca al centro sin resaltar nada.
//  - expression: happy | idle | thinking | unsure | surprised
//  - pose:       (opcional) fuerza la pose; si no, Prismi apunta hacia el objetivo
//  - title, body, emphasis: textos del globo
//  - advanceOn:  "click" = el paso avanza cuando el usuario hace clic en el objetivo
//  - hint:       texto de la instrucción para pasos con clic
//  - optional:   si el objetivo no aparece, el paso se salta en silencio
//  - dock:       Prismi vuela a la esquina donde vive el asistente (paso final)

// Progreso por parte del recorrido:
//  - "public":   vista general (landing). Sin sesión termina invitando a entrar.
//  - "terminal": la terminal por dentro. Se ofrece al entrar con sesión.
//  - "full":     las dos seguidas (si ya hay sesión la primera vez).
const DONE_KEYS = { public: "prisma.tour.public.done", terminal: "prisma.tour.terminal.done" };
const LEGACY_DONE_KEY = "prisma.tour.done";
const CHOICE_KEY = "prisma.guide.choice";

// --- Parte 1: vista general --------------------------------------------------
const PUBLIC_STEPS = [
  {
    id: "hola",
    route: "/",
    target: ['[data-tour="hero"]', ".hero h1"],
    expression: "happy",
    pose: "wave",
    title: "¡Hola! Soy Prismi",
    body: "Soy el billete con superpoderes de Prisma BMV. Te voy a llevar volando por la terminal para que veas qué hace cada parte.",
    emphasis: "Unos 2 minutos",
  },
  {
    id: "ppp",
    route: "/",
    target: ['[data-tour="por-que-ppp"]', "#main-content.landing > section:nth-of-type(2)"],
    expression: "idle",
    title: "Mi superpoder: el PPP oficial",
    body: "No uso el precio de cierre. Uso el Precio Promedio Ponderado que publica la BMV en su boletín diario: pondera todo el volumen de la sesión y es más difícil de mover con unas pocas operaciones.",
    emphasis: "Dato oficial, no sintético",
  },
  {
    id: "capacidades",
    route: "/",
    target: ['[data-tour="capacidades"]', "#capacidades"],
    expression: "idle",
    title: "Los pilares",
    body: "Aquí ves en qué se apoya la terminal: datos auditables, modelos estadísticos validados y señales que se comprueban contra el resultado real.",
    emphasis: "Rigor antes que promesas",
  },
  {
    id: "planes",
    route: "/",
    target: ['[data-tour="planes"]', "#planes"],
    expression: "happy",
    title: "Los planes",
    body: "Explorer es gratuito y abre WALMEX. Los planes de pago desbloquean el resto de emisoras del IPC.",
    emphasis: "Empieza gratis con WALMEX",
  },
];

// Cierre de la parte 1 cuando NO hay sesión: señala el botón de acceso.
const LOGIN_STEP = {
  id: "acceso",
  route: "/",
  target: ['[data-tour="login"]', 'a[href="#/acceso"]'],
  expression: "happy",
  title: "La terminal es para usuarios",
  body: "Para entrar necesitas una cuenta. Inicia sesión aquí o crea una gratis con el plan Explorer. En cuanto entres, te enseño la terminal por dentro.",
  emphasis: "Registro gratuito · plan Explorer",
  advanceOn: "click",
  hint: "Haz clic en «Iniciar sesión»",
};

// Puente entre partes cuando SÍ hay sesión: el botón que abre la terminal.
const ENTER_STEP = {
    id: "entrar",
    route: "/",
    target: ['[data-tour="cta-sistema"]', '.hero a[href="#/sistema"]'],
    expression: "happy",
    title: "Entremos a la terminal",
    body: "Este botón abre la terminal de análisis. Púlsalo y te alcanzo del otro lado.",
    advanceOn: "click",
    hint: "Haz clic en el botón resaltado",
  };

// --- Parte 2: la terminal ----------------------------------------------------
const TERMINAL_WELCOME = {
  id: "bienvenida",
  route: "/sistema",
  phase: "select",
  target: null,
  expression: "happy",
  pose: "wave",
  title: "¡Ya estás dentro!",
  body: "Esta es la terminal de análisis. Te enseño cada parte: la gráfica, el monitor, los modelos y la auditoría.",
  emphasis: "Unos 90 segundos",
};

const TERMINAL_STEPS = [
  {
    id: "grafica",
    route: "/sistema",
    phase: "select",
    target: ['[data-tour="grafica"]', ".workspace-map"],
    expression: "idle",
    title: "La serie histórica",
    body: "Esta gráfica muestra el PPP oficial de la emisora sesión por sesión. Puedes acercarte, moverte y pasar el cursor para ver cada valor.",
    emphasis: "Cada punto viene de un boletín",
  },
  {
    id: "fases",
    route: "/sistema",
    phase: "select",
    target: ['[data-tour="fases"]', ".workspace-panel > div:first-child"],
    expression: "idle",
    title: "Tres módulos",
    body: "1) Seleccionas la emisora, 2) ves la predicción de los modelos y 3) auditas qué tan bien acertaron. Te los enseño en ese orden.",
    emphasis: "Selección → Inferencia → Auditoría",
  },
  {
    id: "monitor",
    route: "/sistema",
    phase: "select",
    target: ['[data-tour="monitor"]', ".selection-panel .table-scroll"],
    expression: "idle",
    title: "El monitor de mercado",
    body: "Cada fila es una emisora del IPC con su PPP oficial y su variación. Si una emisora no apareció en el boletín, se muestra con guion: aquí no se inventan datos.",
    emphasis: "Sin imputaciones",
  },
  {
    id: "sello",
    route: "/sistema",
    phase: "select",
    target: ['[data-tour="sello"]', ".selection-panel > div:last-child"],
    expression: "happy",
    title: "El sello SHA-256",
    body: "Cada boletín tiene una huella digital SHA-256. Si alguien cambiara un solo número, la huella ya no coincidiría. Con «Ver evidencia» puedes revisarla.",
    emphasis: "Datos verificables",
  },
  {
    id: "elegir",
    route: "/sistema",
    phase: "select",
    target: ['[data-tour="emisora-walmex"]', ".selection-panel tbody tr"],
    expression: "happy",
    title: "Elige una emisora",
    body: "Haz clic en una fila para analizarla. WALMEX está incluida en el plan gratuito.",
    advanceOn: "click",
    hint: "Haz clic en la fila resaltada",
  },
  {
    id: "kpis",
    route: "/sistema",
    phase: "analysis",
    target: ['[data-tour="kpis"]', ".analysis-panel > div:nth-child(2)"],
    expression: "idle",
    title: "El punto de partida",
    body: "Estos indicadores resumen la emisora hoy: el PPP base del que parte la predicción y su rendimiento frente al resto del panel.",
    emphasis: "PPP base = precio de hoy",
  },
  {
    id: "modelos",
    route: "/sistema",
    phase: "analysis",
    target: ['[data-tour="modelos"]', ".analysis-panel > div:nth-child(3)"],
    expression: "thinking",
    title: "Los tres modelos",
    body: "V1 Calibrado, V2 Zona Neutral y V3 Alta Discriminación estiman la probabilidad de que el PPP suba en 5 sesiones. La barra muestra qué tan lejos está cada uno del 50 %.",
    emphasis: "Si los tres coinciden, hay consenso",
  },
  {
    id: "acciones",
    route: "/sistema",
    phase: "analysis",
    target: ['[data-tour="acciones"]', ".analysis-panel > div:nth-child(4)"],
    expression: "idle",
    title: "Auditoría y ficha",
    body: "Desde aquí abres la auditoría temporal o descargas la ficha con el resumen de la señal.",
    optional: true,
  },
  {
    id: "auditoria",
    route: "/sistema",
    phase: "audit",
    target: ['[data-tour="auditoria"]', ".workspace-panel"],
    expression: "surprised",
    title: "La prueba de fuego",
    body: "Cinco sesiones después, cada señal se compara con el PPP real. Aquí se ve si el modelo acertó o no, sin borrar los errores.",
    emphasis: "Las señales se auditan",
  },
  {
    id: "final",
    route: "/sistema",
    target: null,
    dock: true,
    expression: "happy",
    pose: "cheer",
    title: "¡Listo, ya conoces la terminal!",
    body: "Me quedo aquí en la esquina. Si tienes dudas sobre el PPP, los modelos o una emisora, haz clic en mí y pregúntame.",
    emphasis: "Prisma BMV no es asesoría de inversión",
  },
];

export function buildSteps(part = "full") {
  if (part === "public") return [...PUBLIC_STEPS, LOGIN_STEP];
  if (part === "terminal") return [TERMINAL_WELCOME, ...TERMINAL_STEPS];
  return [...PUBLIC_STEPS, ENTER_STEP, ...TERMINAL_STEPS];
}

// Compatibilidad: el recorrido completo.
export const TOUR_STEPS = buildSteps("full");

function read(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Ignorar entornos sin localStorage.
  }
}

/** ¿Ya se vio esa parte? part: "public" | "terminal" | "full" */
export function tourDone(part = "full") {
  if (read(LEGACY_DONE_KEY) === "1") return true;
  if (part === "full") return read(DONE_KEYS.public) === "1" && read(DONE_KEYS.terminal) === "1";
  return read(DONE_KEYS[part]) === "1";
}

export function markTourDone(part = "full") {
  if (part === "public" || part === "full") write(DONE_KEYS.public, "1");
  if (part === "terminal" || part === "full") write(DONE_KEYS.terminal, "1");
}

export function resetTour() {
  write(LEGACY_DONE_KEY, null);
  write(DONE_KEYS.public, null);
  write(DONE_KEYS.terminal, null);
  write(CHOICE_KEY, null);
  write(CHOICE_KEY + ".terminal", null);
}

/** Lo que eligió el usuario al ofrecerle esa parte: "tour" | "chat" | null */
export function guideChoice(part = "public") {
  const value = read(part === "terminal" ? CHOICE_KEY + ".terminal" : CHOICE_KEY);
  return value === "tour" || value === "chat" ? value : null;
}

export function saveGuideChoice(choice, part = "public") {
  write(part === "terminal" ? CHOICE_KEY + ".terminal" : CHOICE_KEY, choice);
}

/** Arranca el recorrido. part: "public" | "terminal" | "full" */
export function startTour(part = "full") {
  window.dispatchEvent(new CustomEvent("prisma:tour-start", { detail: { part } }));
}
