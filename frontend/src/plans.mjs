/**
 * Prisma BMV - Definición de Planes y Matriz de Control de Acceso Institucional
 *
 * Escalera calibrada en MXN/USD para el mercado mexicano con cobertura provisional
 * de los 35 componentes del IPC y compuerta estricta de validación para señales G2.
 */

const BASE_15 = [
  "WALMEX", "GMEXICO", "GFNORTE", "AMX", "FEMSA", "CEMEX", "BIMBO", "GAP",
  "PE&OLES", "AC", "ASUR", "GFINBUR", "VESTA", "LIVEPOL", "GRUMA",
];

export const PLANS = [
  {
    id: "explorer",
    name: "Explorer",
    audience: "Plan Gratuito",
    cost: "$0 MXN al mes",
    price: { amount: "$0", detail: "MXN al mes · Acceso Libre" },
    summary: "Monitor BMV de 35 componentes IPC (vista provisional), serie histórica y estadística de WALMEX con integridad SHA-256.",
    includes: [
      "Monitor diario del panel base (15) e IPC provisional (35) sin imputaciones",
      "Cotizaciones ponderadas (PPP) oficiales del boletín BMV",
      "Serie histórica y estadística descriptiva de WALMEX",
      "Observación secundaria Yahoo Finance separada del PPP BMV",
      "Verificación de integridad SHA-256 y panel de gobernanza AWS en vivo",
      "Asistente cuantitativo Prismi con guardrails institucionales"
    ],
    allowedTickers: ["WALMEX"],
    canCompare: false,
    canExportPdf: false,
    maxQueriesPerDay: 5
  },
  {
    id: "professional",
    name: "Professional",
    audience: "Inversionistas y Analistas Cuantitativos",
    cost: "$399 MXN al mes (~$20 USD)",
    price: { amount: "$399", detail: "MXN al mes (~$20 USD)" },
    summary: "Cobertura completa del panel base (15) y universo IPC-35 provisional en estadística, series y módulos G2 al cerrar validación.",
    includes: [
      "Acceso completo a las 15 emisoras base y 35 componentes provisionales del IPC",
      "Series históricas verificadas y estadística descriptiva ampliada",
      "Observación secundaria Yahoo Finance (.MX) en los 35 componentes",
      "Acceso prioritario a señales G2, consenso y seguimiento t+5 al cerrar compuerta 21/21",
      "Panel de gobernanza en vivo y trazabilidad SHA-256 por sesión",
      "Asistente cuantitativo Prismi con consultas ampliadas"
    ],
    allowedTickers: BASE_15,
    canCompare: true,
    canExportPdf: true,
    maxQueriesPerDay: 100
  },
  {
    id: "enterprise",
    name: "Enterprise",
    audience: "Mesas de Dinero, Fondos y Equipos",
    cost: "$3,490 MXN al mes (~$175 USD)",
    price: { amount: "$3,490", detail: "MXN al mes (~$175 USD)" },
    summary: "Para equipos institucionales que requieren trazabilidad completa, administración multiusuario en AWS y acceso analítico ampliado.",
    includes: [
      "Todas las capacidades del Plan Professional",
      "Administración centralizada de usuarios y roles sobre Cognito + DynamoDB",
      "Acceso a arquitectura Lakehouse S3 (Bronze / Silver / Evidencias SHA-256)",
      "Consultas ampliadas sobre API REST y bitácoras auditables",
      "Soporte institucional prioritario y seguimiento de compuertas operativas"
    ],
    allowedTickers: BASE_15,
    canCompare: true,
    canExportPdf: true,
    maxQueriesPerDay: null
  }
];

export const PLAN_IDS = PLANS.map((plan) => plan.id);

export function planById(id) {
  return PLANS.find((plan) => plan.id === id) || PLANS[0];
}

export function canAccessTicker(role, ticker) {
  const plan = planById(role);
  return plan.allowedTickers.includes(ticker);
}

export function canCompareTickers(role) {
  const plan = planById(role);
  return Boolean(plan.canCompare);
}

export function canExportReport(role) {
  const plan = planById(role);
  return Boolean(plan.canExportPdf);
}
