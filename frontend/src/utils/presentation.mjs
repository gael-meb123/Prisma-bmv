/**
 * Prisma BMV - Utilidades de Presentación y Diccionario Semántico Institucional
 */

export const DISCLAIMER = "Evaluación estadística e inferencia prospectiva oficial BMV; no constituye recomendación financiera ni asesoría de inversión individualizada.";

const NOMBRES_MODELOS = {
  G2_V4_ADJ: "G2-V4 · Ajustado por dividendos",
  G2_V4_F1_GAP: "G2-V4 · Ajustado con señal de cierre",
  G2_V1_ADJ: "G2-V1 · Calibrado ajustado",
  G2_V2_ADJ: "G2-V2 · Zona neutral ajustado",
  G2_V3_ADJ: "G2-V3 · Alta discriminación ajustado",
  G2_V4: "G2-V4 · Corto plazo sin ajuste",
  G2_V5_ADJ: "G2-V5 · Adaptativo ajustado",
  G2_V6A_JERARQUICO: "G2-V6A · Logística jerárquica",
  G2_V6B_DESCOMPUESTO: "G2-V6B · Mercado y exceso",
  G2_V6C_RIDGE_CONTINUO: "G2-V6C · Ridge continuo",
  G2_LGBM_CHALLENGER: "G2 · LightGBM challenger",
  CLIMATOLOGIA_ADJ: "Referencia · Climatología ajustada",
  G2_V1_POOLED_REL3_CALIBRADO: "G2-V1 · Calibrado",
  G2_V2_POOLED_REL3_ZONA_NEUTRAL: "G2-V2 · Zona neutral",
  G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO: "G2-V3 · Alta discriminación",
  G2_V4_POOLED_DM5_REL_CORTO_PLAZO: "G2-V4 · Agotamiento corto",
  G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL: "G2-V5 · Adaptativo por régimen",
  V1_CONTROL_LOGREG: "G1-V1 · Logística base",
  V2R_RETADOR_LINEAL_AJUSTE_DIVIDENDOS: "G1-V2R · Ajuste por dividendos",
  V3_RETADOR_SELECCIONADO_RF: "G1-V3 · Random Forest",
  V2_RETADOR_HIBRIDO_BOLETIN: "G1-V2 · Híbrido boletín",
};

export function nombreModelo(id, alternativa = id) {
  return NOMBRES_MODELOS[id] || alternativa;
}

export function estadoModeloHistorico(id, rol = "") {
  const etiquetas = ["Evaluación histórica TEST"];
  if (id?.endsWith("_ADJ") || id === "G2_V4_F1_GAP") etiquetas.push("Variante ajustada");
  if (rol.startsWith("SHADOW")) etiquetas.push("Shadow");
  if (rol === "BENCHMARK") etiquetas.push("Referencia");
  return etiquetas;
}

export function modelosHistoricosSinSenal(metricas, modelos = []) {
  if (!Array.isArray(metricas?.modelos_test)) return [];
  const registrados = new Set(modelos.map((m) => m.modelo));
  return metricas.modelos_test.filter((m) => m.id_modelo && !registrados.has(m.id_modelo));
}

export function describirModelos(texto) {
  if (!texto) return texto;
  return texto.replace(/\bG2_V4_F1_GAP\b|\bG2_V4_ADJ\b/g, (id) => nombreModelo(id));
}

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
    label: "Marcado como PPP verificado",
    tone: "available",
    description: "La fuente registra un PPP como verificado; la evidencia y la cobertura se deben revisar por corte."
  },
  CONTINGENCIA_FUENTE_SECUNDARIA: {
    label: "Contingencia Secundaria",
    tone: "partial",
    description: "Dato de fuente secundaria; no es PPP oficial. La conciliación automática está pausada."
  },
  NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA: {
    label: "Sin dato en la captura",
    tone: "missing",
    description: "No se cuenta con un dato válido en esta captura. El estado no acredita ausencia de operación."
  },
  NO_PUBLICADO_EN_BOLETIN_RSS_DEL_DIA: {
    label: "Sin dato en boletín RSS",
    tone: "missing",
    description: "El par no aparece en las tablas parciales del boletín RSS de esta sesión; no se imputa precio."
  },
  NO_ENCONTRADO_EN_TABLAS_BOLETIN: {
    label: "No publicado en tablas RSS",
    tone: "missing",
    description: "El par no aparece en las tablas de cotizaciones reconocidas del boletín; no se imputa precio."
  },
  PPP_OBSERVADO_MAPEO_PROVISIONAL: {
    label: "PPP observado (provisional)",
    tone: "partial",
    description: "PPP extraído del boletín Bronze para un candidato provisional; composición y alias pendientes de confirmación oficial y sin señales."
  },
  BOLETIN_BRONZE_NO_DISPONIBLE: {
    label: "Sin boletín Bronze en sesión",
    tone: "missing",
    description: "No existe boletín oficial Bronze archivado para este corte; los candidatos provisionales quedan sin precio."
  },
  CONFLICTO_O_FILA_INVALIDA: {
    label: "Conflicto / revisión",
    tone: "missing",
    description: "Fila ambigua o inválida en el boletín; bloqueada sin imputación."
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
