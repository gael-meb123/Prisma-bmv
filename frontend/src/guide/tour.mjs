// Recorrido guiado de Prisma BMV con Prismi, el billete superhéroe.
// Texto 100% estático: no llama a la API ni a ningún servicio.
// Se adapta automáticamente a los módulos activos (evaluación Gold vs compuerta estricta).

const DONE_KEYS = { public: "prisma.tour.public.done", terminal: "prisma.tour.terminal.done" };
const LEGACY_DONE_KEY = "prisma.tour.done";
const CHOICE_KEY = "prisma.guide.choice";

function defaultGoldEval() {
  try {
    return import.meta.env?.VITE_GOLD_EVALUACION === "true" || import.meta.env?.VITE_REQUIRE_REAL_API !== "true";
  } catch {
    return false;
  }
}

// --- Parte 1: vista general (Landing institucional) --------------------------
const PUBLIC_STEPS = [
  {
    id: "hola",
    route: "/",
    target: ['[data-tour="hero"]', ".bk-hero h1"],
    expression: "happy",
    pose: "wave",
    title: "¡Hola! Soy Prismi",
    body: "Soy el asistente cuantitativo de Prisma BMV. Te llevo volando por la plataforma para mostrarte el PPP oficial de la BMV, el monitor ampliado del IPC-35 y tu terminal en AWS.",
    emphasis: "Unos 2 minutos",
  },
  {
    id: "mercado-hoy",
    route: "/",
    target: ['[data-tour="mercado-hoy"]', "#mercado-hoy"],
    expression: "happy",
    title: "El pulso real de la sesión",
    body: "Aquí ves el resumen vivo del último boletín oficial BMV: cuántas emisoras publicaron PPP verificado, alzas, bajas y los movimientos más fuertes del día.",
    emphasis: "Datos reales de Amazon S3",
    optional: true,
  },
  {
    id: "ppp",
    route: "/",
    target: ['[data-tour="por-que-ppp"]', "#por-que"],
    expression: "idle",
    title: "Mi superpoder: el PPP oficial",
    body: "No uso el precio de cierre. Uso el Precio Promedio Ponderado que publica la BMV en su boletín diario: pondera todo el volumen de la sesión y refleja dónde se negoció realmente el mercado.",
    emphasis: "Dato oficial, cero imputación",
  },
  {
    id: "capacidades",
    route: "/",
    target: ['[data-tour="capacidades"]', "#como-funciona"],
    expression: "idle",
    title: "Del boletín a la auditoría",
    body: "Cada día hábil a las 16:45 CDMX se captura el boletín en AWS con huella SHA-256, se almacenan el panel base y los 35 componentes provisionales del IPC sin rellenar huecos, y se audita cada etapa.",
    emphasis: "Rigor antes que promesas",
  },
  {
    id: "planes",
    route: "/",
    target: ['[data-tour="planes"]', "#planes"],
    expression: "happy",
    title: "Planes calibrados en MXN",
    body: "Explorer es gratuito ($0 MXN) con monitor de 35 componentes provisionales y análisis completo de WALMEX. Professional ($399 MXN) y Enterprise ($3,490 MXN) desbloquean todo el panel y capacidades institucionales.",
    emphasis: "Empieza gratis con WALMEX",
  },
  {
    id: "seguridad",
    route: "/",
    target: ['[data-tour="seguridad"]', "#seguridad"],
    expression: "idle",
    title: "Trazabilidad verificable",
    body: "Cada boletín conserva su huella SHA-256 inmutable en S3 y tu acceso está protegido con Amazon Cognito, verificación de correo y MFA opcional.",
    emphasis: "Identidad Cognito + DynamoDB",
    optional: true,
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
  hint: "Haz clic en «Ingresar»",
};

// Puente entre partes cuando SÍ hay sesión: el botón que abre la terminal.
const ENTER_STEP = {
  id: "entrar",
  route: "/",
  target: ['[data-tour="cta-sistema"]', '[data-tour="cta-sistema-header"]', 'a[href="#/sistema"]'],
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
  body: "Esta es tu terminal cuantitativa en AWS. Te enseño el menú, el monitor IPC-35, tus gráficas, la estadística con observación secundaria Yahoo y la gobernanza en vivo.",
  emphasis: "Unos 2 minutos",
};

const MODEL_STEPS = [
  {
    id: "consenso",
    route: "/sistema",
    phase: "consenso",
    target: ['[data-tour="consenso"]', ".consenso-lista"],
    expression: "thinking",
    title: "Consenso de modelos G2",
    body: "Aquí comparas de un vistazo los cinco modelos G2 (V1 a V5) sobre las emisoras de tu plan en el archivo histórico Gold: coincidencia en subida, no subida o divergencia.",
    emphasis: "Evaluación histórica Gold · sin recomendaciones",
    optional: true,
  },
  {
    id: "modelos",
    route: "/sistema",
    phase: "senales",
    target: ['[data-tour="modelos"]'],
    expression: "thinking",
    title: "Probabilidades por modelo",
    body: "Cada barra es la probabilidad de que el PPP suba en 5 sesiones según cada modelo. La línea punteada marca 50 %: entre más lejos, mayor convicción estadística.",
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
    body: "Esta cascada abre la caja del modelo: muestra cuánto suma o resta cada variable al log-odds, destacando el retorno relativo frente al resto del panel.",
    optional: true,
  },
  {
    id: "trayectoria",
    route: "/sistema",
    phase: "seguimiento",
    target: ['[data-tour="trayectoria"]', '[data-tour="marcador"]'],
    expression: "surprised",
    title: "La prueba de fuego (t+5)",
    body: "Seguimos cada señal sesión por sesión desde t0 hasta t+5 contra el PPP verificado. Los huecos no se interpolan y los errores no se borran.",
    emphasis: "Auditoría prospectiva transparente",
    optional: true,
  },
  {
    id: "marcador",
    route: "/sistema",
    phase: "seguimiento",
    target: ['[data-tour="marcador"]'],
    expression: "thinking",
    title: "El marcador por modelo",
    body: "Compara aciertos parciales, resoluciones en t+5 y Brier score (menor es mejor) para las emisoras de tu plan.",
    optional: true,
  },
  {
    id: "calidad",
    route: "/sistema",
    phase: "calidad",
    target: ['[data-tour="calidad"]'],
    expression: "idle",
    title: "Calidad y calibración",
    body: "El diagrama de confiabilidad y las métricas fuera de muestra (BSS, Rank IC, ECE y ¼-Kelly) muestran qué tan calibradas están las probabilidades.",
    optional: true,
  },
];

function buildTerminalSteps(goldEval) {
  return [
    {
      id: "menu",
      route: "/sistema",
      phase: "resumen",
      target: ['[data-tour="menu"]', ".tm-nav"],
      expression: "idle",
      title: "Tu menú de navegación",
      body: goldEval
        ? "Desde aquí accedes a Resumen, Mercado (15 base e IPC-35), Consenso, Señales, Seguimiento t+5, Calidad, Análisis estadístico y Datos y gobernanza en AWS."
        : "Desde aquí accedes a Resumen, Mercado (15 base e IPC-35), Análisis estadístico con observación secundaria Yahoo y Datos y gobernanza en AWS. Los módulos de señales permanecen protegidos hasta cerrar la ventana 21/21.",
      emphasis: "Todo a un clic",
    },
    {
      id: "selector",
      route: "/sistema",
      phase: "resumen",
      target: ['[data-tour="selector-emisora"]', ".tm-top-controls"],
      expression: "idle",
      title: "Elige emisora y sesión",
      body: "Aquí cambias la emisora del panel base y la fecha del boletín oficial. Las gráficas se actualizan al instante según los permisos de tu plan.",
      emphasis: "WALMEX está en el plan gratuito",
    },
    {
      id: "kpis",
      route: "/sistema",
      phase: "resumen",
      target: ['[data-tour="kpis"]', ".tm-kpis"],
      expression: "happy",
      title: "Tu saldo del mercado",
      body: "Estas tarjetas resumen la sesión seleccionada: el PPP oficial de tu emisora, el balance de alzas y bajas y los movimientos más pronunciados del día.",
    },
    {
      id: "grafica",
      route: "/sistema",
      phase: "resumen",
      target: ['[data-tour="grafica"]', ".tm-row-main .tm-chart"],
      expression: "idle",
      title: "La serie histórica del PPP",
      body: "Muestra el PPP oficial sesión por sesión desde S3. Si una emisora no apareció en el boletín, la línea se corta en lugar de rellenar datos.",
      emphasis: "Cada punto viene de un boletín",
    },
    {
      id: "explica",
      route: "/sistema",
      phase: "resumen",
      target: ['[data-tour="explica"]', ".tm-explain"],
      expression: "happy",
      title: "Pídeme que te la explique",
      body: "Cada gráfica tiene este botón. Al pulsarlo te cuento qué muestra con las cifras reales del día y puedes hacerme preguntas de seguimiento en el chat.",
      emphasis: "«Explicar» con Prismi",
      optional: true,
    },
    {
      id: "monitor",
      route: "/sistema",
      phase: "mercado",
      target: ['[data-tour="monitor"]', ".tm-table"],
      expression: "idle",
      title: "El monitor de mercado",
      body: "Consulta las cotizaciones oficiales del panel base (15) o cambia a IPC provisional (35) con sectores BMV provisionales y huecos transparentes sin imputación.",
      emphasis: "Base 15 + IPC provisional (35)",
    },
    {
      id: "universo-ipc35",
      route: "/sistema",
      phase: "mercado",
      target: ['[data-tour="universo-ipc35"]'],
      expression: "happy",
      title: "Expansión IPC provisional (35)",
      body: "Con este selector alternas entre las 15 emisoras base y los 35 componentes provisionales del IPC con lectura directa del boletín Bronze.",
      optional: true,
    },
    {
      id: "sello",
      route: "/sistema",
      phase: "mercado",
      target: ['[data-tour="sello"]'],
      expression: "happy",
      title: "El sello SHA-256",
      body: "Es la huella criptográfica del boletín oficial. Si cambiara un solo carácter del archivo, la huella ya no coincidiría.",
      emphasis: "Integridad verificable",
      optional: true,
    },
    ...(goldEval ? MODEL_STEPS : []),
    {
      id: "estadistica",
      route: "/sistema",
      phase: "estadistica",
      target: ['[data-tour="estadistica"]', ".estadistica-filtros"],
      expression: "thinking",
      title: "Análisis estadístico",
      body: "Explora medidas descriptivas, distribución y cobertura tanto del panel base (15) como del almacenamiento versionado IPC-35 provisional, sin imputar faltantes.",
      optional: true,
    },
    {
      id: "yahoo-secundaria",
      route: "/sistema",
      phase: "estadistica",
      target: ['[data-tour="yahoo-secundaria"]'],
      expression: "idle",
      title: "Observación secundaria Yahoo (.MX)",
      body: "Aquí consultas cierres diarios reportados y archivados en S3 para los 35 símbolos .MX, estrictamente separados del PPP oficial BMV y sin entrar a modelos.",
      emphasis: "Separación estricta de fuentes",
      optional: true,
    },
    {
      id: "gobernanza",
      route: "/sistema",
      phase: "gobernanza",
      target: ['[data-tour="gobernanza"]'],
      expression: "happy",
      title: "Datos y gobernanza en AWS",
      body: "El flujo vivo del lakehouse: EventBridge (DisparadorDiarioBMV), recolector seguro en Lambda, avance de la ventana limpia 21/21, hashes SHA-256 y compuertas operativas.",
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
      body: "Me quedo aquí en la esquina. Pulsa «Explicar» en cualquier gráfica o haz clic en mí para preguntarme sobre el PPP, el IPC-35, la gobernanza o tus planes.",
      emphasis: "Prisma BMV no es asesoría de inversión",
    },
  ];
}

export function buildSteps(part = "full", { goldEval = defaultGoldEval() } = {}) {
  const terminalSteps = buildTerminalSteps(goldEval);
  if (part === "public") return [...PUBLIC_STEPS, LOGIN_STEP];
  if (part === "terminal") return [TERMINAL_WELCOME, ...terminalSteps];
  return [...PUBLIC_STEPS, ENTER_STEP, ...terminalSteps];
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
