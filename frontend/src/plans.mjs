/**
 * Prisma BMV - Definición de Planes y Matriz de Control de Acceso (Freemium)
 * Basado en la arquitectura formal de suscripciones de Proyecto-geo.
 */

export const PLANS = [
  {
    id: "explorer",
    name: "Explorer",
    audience: "Plan Gratuito",
    cost: "Sin costo",
    price: { amount: "$0", detail: "USD al mes · Acceso Libre" },
    summary: "Monitoreo oficial del mercado BMV y modelo prospectivo para la emisora líder (WALMEX).",
    includes: [
      "Monitoreo en vivo de las 15 emisoras del IPC",
      "Cotizaciones ponderadas (PPP) oficiales de la BMV",
      "Acceso completo a inferencia IA de WALMEX",
      "Verificación de integridad SHA-256 del boletín",
      "Asistente cuantitativo Prismi (consultas estándar)"
    ],
    allowedTickers: ["WALMEX"],
    canCompare: false,
    canExportPdf: false,
    maxQueriesPerDay: 5
  },
  {
    id: "profesional",
    name: "Professional",
    audience: "Inversionistas Cuantitativos",
    cost: "$49 USD al mes",
    price: { amount: "$49", detail: "USD al mes · por analista" },
    summary: "Desbloquea el panel G2 multi-modelo completo, consenso simultáneo y gráficas interactivas.",
    includes: [
      "Cobertura completa del panel (WALMEX, GMEXICO, GFNORTE, AMX)",
      "Matriz de consenso de los 3 modelos G2 (V1, V2 y V3)",
      "Gráficas interactivas avanzadas en Plotly.js",
      "Seguimiento temporal de maduración de la señal (t+1 a t+5)",
      "Comparación simultánea A/B de emisoras del panel",
      "Ficha de auditoría financiera exportable e imprimible"
    ],
    allowedTickers: ["WALMEX", "GMEXICO", "GFNORTE", "AMX", "FEMSA", "CEMEX", "BIMBO", "GAP", "PE&OLES", "AC", "ASUR", "GFINBUR", "VESTA", "LIVEPOL", "GRUMA"],
    canCompare: true,
    canExportPdf: true,
    maxQueriesPerDay: 100
  },
  {
    id: "enterprise",
    name: "Enterprise",
    audience: "Mesas de Dinero y Fondos",
    cost: "$199 USD al mes",
    price: { amount: "$199", detail: "USD al mes · equipo institucional" },
    summary: "Para mesas institucionales que requieren integración directa, latencia mínima y auditoría serverless.",
    includes: [
      "Todas las capacidades del Plan Professional",
      "API REST institucional de inferencia con latencia < 50ms",
      "Acceso directo a tablas Amazon Athena y S3 Gold Parquet",
      "Consultas y ejecuciones de modelo ilimitadas",
      "Soporte cuantitativo 24/7 y SLA garantizado de 99.9%"
    ],
    allowedTickers: ["WALMEX", "GMEXICO", "GFNORTE", "AMX", "FEMSA", "CEMEX", "BIMBO", "GAP", "PE&OLES", "AC", "ASUR", "GFINBUR", "VESTA", "LIVEPOL", "GRUMA"],
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
