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
  phase: "resumen",
  target: null,
  expression: "happy",
  pose: "wave",
  title: "¡Ya estás dentro!",
  body: "Esta es tu terminal, organizada como tu banca en línea. Te enseño el menú, tus gráficas y cómo pedirme que te explique cada una.",
  emphasis: "Unos 2 minutos",
};

const TERMINAL_STEPS = [
  {
    id: "menu",
    route: "/sistema",
    phase: "resumen",
    target: ['[data-tour="menu"]', ".tm-nav"],
    expression: "idle",
    title: "Tu menú",
    body: "Como en tu banco: Resumen, Mercado, Señales, Seguimiento, Calidad de modelos y Datos. El candado indica secciones que tu plan no abre para la emisora elegida.",
    emphasis: "Todo a un clic",
  },
  {
    id: "selector",
    route: "/sistema",
    phase: "resumen",
    target: ['[data-tour="selector-emisora"]', ".tm-top-controls"],
    expression: "idle",
    title: "Elige emisora y sesión",
    body: "Aquí cambias la emisora que analizas y la sesión del boletín. Todas las gráficas se actualizan con tu elección.",
    emphasis: "WALMEX está en el plan gratuito",
  },
  {
    id: "kpis",
    route: "/sistema",
    phase: "resumen",
    target: ['[data-tour="kpis"]', ".tm-kpis"],
    expression: "happy",
    title: "Tu saldo del mercado",
    body: "Estas tarjetas resumen el día: el PPP de tu emisora, el consenso de los modelos, cuántas emisoras subieron o bajaron y la mayor alza.",
  },
  {
    id: "grafica",
    route: "/sistema",
    phase: "resumen",
    target: ['[data-tour="grafica"]', ".tm-row-main .tm-chart"],
    expression: "idle",
    title: "La serie histórica",
    body: "El PPP oficial sesión por sesión. Si una emisora no apareció en el boletín, la línea se corta: aquí no se inventan datos. Puedes acercarte arrastrando.",
    emphasis: "Cada punto viene de un boletín",
  },
  {
    id: "explica",
    route: "/sistema",
    phase: "resumen",
    target: ['[data-tour="explica"]', ".tm-explain"],
    expression: "happy",
    title: "Pídeme que te la explique",
    body: "Cada gráfica tiene este botón. Al pulsarlo te cuento qué muestra, cómo se lee y qué dicen los datos de hoy. Luego puedes preguntarme lo que quieras sobre ella.",
    emphasis: "«Prismi te lo explica»",
  },
  {
    id: "monitor",
    route: "/sistema",
    phase: "mercado",
    target: ['[data-tour="monitor"]', ".tm-table"],
    expression: "idle",
    title: "El monitor de mercado",
    body: "Las 15 emisoras del IPC con su PPP oficial y su variación. Haz clic en una fila para analizarla.",
    emphasis: "Sin imputaciones",
  },
  {
    id: "sello",
    route: "/sistema",
    phase: "mercado",
    target: ['[data-tour="sello"]'],
    expression: "happy",
    title: "El sello SHA-256",
    body: "Es la huella digital del boletín. Si alguien cambiara un solo número, la huella ya no coincidiría.",
    emphasis: "Datos verificables",
    optional: true,
  },
  {
    id: "modelos",
    route: "/sistema",
    phase: "senales",
    target: ['[data-tour="modelos"]'],
    expression: "thinking",
    title: "Los modelos",
    body: "Cada barra es la probabilidad de que el PPP suba en 5 sesiones según un modelo. La línea marca 50 %: si todos están del mismo lado, hay consenso.",
    emphasis: "Probabilidades, no recomendaciones",
    optional: true,
  },
  {
    id: "factor",
    route: "/sistema",
    phase: "senales",
    target: ['[data-tour="factor"]'],
    expression: "thinking",
    title: "¿Qué empuja la probabilidad?",
    body: "Esta cascada abre la caja del modelo: muestra cuánto suma o resta cada variable, como el retorno de la emisora frente al resto del panel.",
    optional: true,
  },
  {
    id: "trayectoria",
    route: "/sistema",
    phase: "seguimiento",
    target: ['[data-tour="trayectoria"]', '[data-tour="marcador"]'],
    expression: "surprised",
    title: "La prueba de fuego",
    body: "Seguimos cada señal sesión por sesión hasta t+5 y la comparamos con el PPP real. Los errores no se borran.",
    emphasis: "Las señales se auditan",
    optional: true,
  },
  {
    id: "marcador",
    route: "/sistema",
    phase: "seguimiento",
    target: ['[data-tour="marcador"]'],
    expression: "thinking",
    title: "El marcador",
    body: "Compara a los modelos con lo que realmente pasó. Con pocas señales resueltas la tasa todavía es inestable.",
    optional: true,
  },
  {
    id: "calidad",
    route: "/sistema",
    phase: "calidad",
    target: ['[data-tour="calidad"]'],
    expression: "idle",
    title: "Calidad de los modelos",
    body: "Si el modelo dice 55 %, ¿sube el 55 % de las veces? La calibración y las métricas fuera de muestra lo responden.",
    optional: true,
  },
  {
    id: "gobernanza",
    route: "/sistema",
    phase: "gobernanza",
    target: ['[data-tour="gobernanza"]'],
    expression: "happy",
    title: "¿De dónde salen los datos?",
    body: "El camino completo: de la BMV a S3 y Athena en AWS, cada día hábil a las 16:45.",
    optional: true,
  },
  {
    id: "final",
    route: "/sistema",
    phase: "resumen",
    target: null,
    dock: true,
    expression: "happy",
    pose: "cheer",
    title: "¡Listo, ya conoces tu terminal!",
    body: "Me quedo aquí en la esquina. Pulsa «Prismi te lo explica» en cualquier gráfica o hazme una pregunta.",
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
