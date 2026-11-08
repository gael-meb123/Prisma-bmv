/**
 * Prisma BMV - Utilidades de Presentación y Diccionario Semántico Institucional
 */

export const DISCLAIMER = "Evaluación estadística e inferencia prospectiva oficial BMV; no constituye recomendación financiera ni asesoría de inversión individualizada.";

export const TICKERS_INFO = {
  WALMEX: { nombre: "Walmart de México y Centroamérica", serie: "*", sector: "Comercio y autoservicio", tier: "explorer" },
  GMEXICO: { nombre: "Grupo México", serie: "B", sector: "Minería y materiales", tier: "profesional" },
  GFNORTE: { nombre: "Grupo Financiero Banorte", serie: "O", sector: "Banca y finanzas", tier: "profesional" },
  AMX: { nombre: "América Móvil", serie: "B", sector: "Telecomunicaciones", tier: "profesional" },
  FEMSA: { nombre: "Fomento Económico Mexicano", serie: "UBD", sector: "Consumo y comercio", tier: "profesional" },
  CEMEX: { nombre: "Cemex", serie: "CPO", sector: "Cemento y materiales", tier: "profesional" },
  BIMBO: { nombre: "Grupo Bimbo", serie: "A", sector: "Industria alimentaria", tier: "profesional" },
  GAP: { nombre: "Grupo Aeroportuario del Pacífico", serie: "B", sector: "Infraestructura aeroportuaria", tier: "profesional" },
  PE_OLES: { nombre: "Industrias Peñoles", serie: "*", sector: "Minería y metales", tier: "profesional" },
  AC: { nombre: "Arca Continental", serie: "*", sector: "Bebidas y embotellado", tier: "profesional" },
  ASUR: { nombre: "Grupo Aeroportuario del Sureste", serie: "B", sector: "Infraestructura aeroportuaria", tier: "profesional" },
  GFINBUR: { nombre: "Grupo Financiero Inbursa", serie: "O", sector: "Servicios financieros", tier: "profesional" },
  VESTA: { nombre: "Corporación Inmobiliaria Vesta", serie: "*", sector: "Bienes raíces industriales", tier: "profesional" },
  LIVEPOL: { nombre: "El Puerto de Liverpool", serie: "C-1", sector: "Comercio departamental", tier: "profesional" },
  GRUMA: { nombre: "Gruma", serie: "B", sector: "Industria alimentaria", tier: "profesional" },
};

export const STATUS = {
  PPP_PUBLICADO_VERIFICADO: {
    label: "PPP Oficial Verificado",
    tone: "available",
    description: "Precio Promedio Ponderado extraído del boletín regulatorio de la BMV con hash SHA-256 verificado."
  },
  CONTINGENCIA_FUENTE_SECUNDARIA: {
    label: "Contingencia Secundaria",
    tone: "partial",
    description: "Cotización obtenida de fuente secundaria mientras la BMV publica el boletín RSS oficial; se reconcilia automáticamente."
  },
  NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA: {
    label: "Ausente en Boletín",
    tone: "missing",
    description: "La emisora no registró volumen suficiente en las tablas del boletín oficial. Cero imputación sintética."
  },
  CONSENSO_PANEL_G2_SUBIDA: {
    label: "Consenso Fuerte: Subida",
    tone: "available",
    description: "Unanimidad positiva (5/5 modelos G2 V1-V5): Alta probabilidad de apreciación acumulada en el horizonte a 5 sesiones (t+5)."
  },
  CONSENSO_PANEL_G2_NO_SUBIDA: {
    label: "Consenso: No Subida / Consolidación",
    tone: "missing",
    description: "Unanimidad neutral/bajista (5/5 modelos G2 V1-V5): Probabilidad inferior al 50%. Se anticipa consolidación técnica."
  },
  DIVERGENCIA_PANEL_G2: {
    label: "Divergencia entre Modelos G2",
    tone: "partial",
    description: "Divergencia entre variantes V1, V2, V3, V4 y V5. Se recomienda cautela o dimensionamiento fraccional ¼-Kelly."
  },
  IN_SAMPLE_DISENO: {
    label: "In-Sample Diseño (< 2026-11-06)",
    tone: "partial",
    description: "Señal emitida antes de la fecha de congelamiento formal (2026-11-06); contabilizada como muestra de diseño."
  },
  OUT_OF_SAMPLE_PRE_REGISTRADO: {
    label: "Out-of-Sample Pre-Registrado (≥ 2026-11-06)",
    tone: "available",
    description: "Señal prospectiva estrictamente fuera de muestra posterior al congelamiento SHA-256 de coeficientes."
  },
  PENDIENTE_RECONCILIACION: {
    label: "En Maduración (t+1 a t+4)",
    tone: "partial",
    description: "Señal activa en ventana de 5 sesiones bursátiles pendiente de liquidación oficial en t+5."
  },
  RESUELTA_OFICIAL_T5: {
    label: "Liquidada Oficial (t+5)",
    tone: "available",
    description: "Señal reconciliada contra el PPP oficial verificado de la 5ª sesión hábil posterior."
  }
};

export function formatMoney(val) {
  if (val == null || isNaN(val)) return "—";
  return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(val);
}

export function formatPct(val) {
  if (val == null || isNaN(val)) return "—";
  const formatted = val.toFixed(2);
  return val > 0 ? `+${formatted}%` : `${formatted}%`;
}

export function formatProb(val) {
  if (val == null || isNaN(val)) return "—";
  return `${(val * 100).toFixed(1)}%`;
}
