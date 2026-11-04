/**
 * Prisma BMV - Datos Mock Oficiales para Desarrollo Frontend Aislado
 * Permite a los desarrolladores de React trabajar sin depender de que el backend esté encendido.
 */

export const MOCK_FECHAS = ["2026-10-30", "2026-10-29", "2026-10-28"];

export const MOCK_MERCADO_RESUMEN = {
  fecha: "2026-10-30",
  kpis: {
    fecha: "2026-10-30",
    total_emisoras: 15,
    total_verificadas: 10,
    total_ausentes: 5,
    conteo_alzas: 7,
    conteo_bajas: 3,
    top_alza_ticker: "BIMBO",
    top_alza_pct: 4.22,
    top_baja_ticker: "GMEXICO",
    top_baja_pct: -4.01,
    sha256_boletin: "ea246a3f72a1e7b50dadf028e3e5995926a214508eb7648a9ebed29fa1ff19ea",
    url_fuente: "https://www.bmv.com.mx/docs-pub/rss/boletin20261030.html"
  },
  cotizaciones: [
    { emisora: "BIMBO", serie: "A", sector: "Industria alimentaria", ppp_bmv_mxn: 66.39, anterior_bmv_mxn: 63.70, variacion_pct: 4.22, estado_captura: "PPP_PUBLICADO_VERIFICADO" },
    { emisora: "WALMEX", serie: "*", sector: "Comercio y autoservicio", ppp_bmv_mxn: 50.39, anterior_bmv_mxn: 48.77, variacion_pct: 3.32, estado_captura: "PPP_PUBLICADO_VERIFICADO" },
    { emisora: "GRUMA", serie: "B", sector: "Industria alimentaria", ppp_bmv_mxn: 242.71, anterior_bmv_mxn: 238.30, variacion_pct: 1.85, estado_captura: "PPP_PUBLICADO_VERIFICADO" },
    { emisora: "GAP", serie: "B", sector: "Infraestructura aeroportuaria", ppp_bmv_mxn: 434.25, anterior_bmv_mxn: 426.86, variacion_pct: 1.73, estado_captura: "PPP_PUBLICADO_VERIFICADO" },
    { emisora: "AC", serie: "*", sector: "Bebidas y consumo", ppp_bmv_mxn: 221.43, anterior_bmv_mxn: 218.20, variacion_pct: 1.48, estado_captura: "PPP_PUBLICADO_VERIFICADO" },
    { emisora: "AMX", serie: "B", sector: "Telecomunicaciones", ppp_bmv_mxn: 23.05, anterior_bmv_mxn: 22.73, variacion_pct: 1.41, estado_captura: "PPP_PUBLICADO_VERIFICADO" },
    { emisora: "FEMSA", serie: "UBD", sector: "Consumo y comercio", ppp_bmv_mxn: 236.49, anterior_bmv_mxn: 234.12, variacion_pct: 1.01, estado_captura: "PPP_PUBLICADO_VERIFICADO" },
    { emisora: "GFNORTE", serie: "O", sector: "Banca y servicios financieros", ppp_bmv_mxn: 209.04, anterior_bmv_mxn: 210.99, variacion_pct: -0.92, estado_captura: "PPP_PUBLICADO_VERIFICADO" },
    { emisora: "PE&OLES", serie: "*", sector: "Mineria y metales", ppp_bmv_mxn: 762.30, anterior_bmv_mxn: 789.37, variacion_pct: -3.43, estado_captura: "PPP_PUBLICADO_VERIFICADO" },
    { emisora: "GMEXICO", serie: "B", sector: "Mineria y materiales", ppp_bmv_mxn: 224.31, anterior_bmv_mxn: 233.68, variacion_pct: -4.01, estado_captura: "PPP_PUBLICADO_VERIFICADO" },
    { emisora: "ASUR", serie: "B", sector: "Infraestructura aeroportuaria", ppp_bmv_mxn: null, anterior_bmv_mxn: null, variacion_pct: null, estado_captura: "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA" },
    { emisora: "CEMEX", serie: "CPO", sector: "Cemento y construccion", ppp_bmv_mxn: null, anterior_bmv_mxn: null, variacion_pct: null, estado_captura: "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA" },
    { emisora: "GFINBUR", serie: "O", sector: "Servicios financieros", ppp_bmv_mxn: null, anterior_bmv_mxn: null, variacion_pct: null, estado_captura: "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA" },
    { emisora: "LIVEPOL", serie: "C-1", sector: "Comercio departamental", ppp_bmv_mxn: null, anterior_bmv_mxn: null, variacion_pct: null, estado_captura: "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA" },
    { emisora: "VESTA", serie: "*", sector: "Inmuebles industriales", ppp_bmv_mxn: null, anterior_bmv_mxn: null, variacion_pct: null, estado_captura: "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA" }
  ]
};

export const MOCK_SENALES_PANEL = [
  { id: "WALMEX_V1", emisora: "WALMEX", modelo: "G2_V1_POOLED_REL3_CALIBRADO", ppp_base: 50.39, prob: 0.4808, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 2.12 },
  { id: "WALMEX_V2", emisora: "WALMEX", modelo: "G2_V2_POOLED_REL3_ZONA_NEUTRAL", ppp_base: 50.39, prob: 0.4795, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 2.12 },
  { id: "WALMEX_V3", emisora: "WALMEX", modelo: "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO", ppp_base: 50.39, prob: 0.4874, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 2.12 },
  
  { id: "GMEXICO_V1", emisora: "GMEXICO", modelo: "G2_V1_POOLED_REL3_CALIBRADO", ppp_base: 224.31, prob: 0.5635, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -13.06 },
  { id: "GMEXICO_V2", emisora: "GMEXICO", modelo: "G2_V2_POOLED_REL3_ZONA_NEUTRAL", ppp_base: 224.31, prob: 0.5651, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -13.06 },
  { id: "GMEXICO_V3", emisora: "GMEXICO", modelo: "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO", ppp_base: 224.31, prob: 0.5492, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -13.06 },

  { id: "GFNORTE_V1", emisora: "GFNORTE", modelo: "G2_V1_POOLED_REL3_CALIBRADO", ppp_base: 209.04, prob: 0.4954, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: -1.45 },
  { id: "GFNORTE_V2", emisora: "GFNORTE", modelo: "G2_V2_POOLED_REL3_ZONA_NEUTRAL", ppp_base: 209.04, prob: 0.4940, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: -1.45 },
  { id: "GFNORTE_V3", emisora: "GFNORTE", modelo: "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO", ppp_base: 209.04, prob: 0.4965, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: -1.45 },

  { id: "AMX_V1", emisora: "AMX", modelo: "G2_V1_POOLED_REL3_CALIBRADO", ppp_base: 23.05, prob: 0.4044, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 6.84 },
  { id: "AMX_V2", emisora: "AMX", modelo: "G2_V2_POOLED_REL3_ZONA_NEUTRAL", ppp_base: 23.05, prob: 0.3996, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 6.84 },
  { id: "AMX_V3", emisora: "AMX", modelo: "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO", ppp_base: 23.05, prob: 0.4432, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 6.84 }
];

export const MOCK_SERIE_WALMEX = [
  { fecha: "2026-09-08", ppp: 47.10 },
  { fecha: "2026-09-15", ppp: 47.85 },
  { fecha: "2026-09-22", ppp: 48.20 },
  { fecha: "2026-09-29", ppp: 47.90 },
  { fecha: "2026-10-06", ppp: 48.35 },
  { fecha: "2026-10-13", ppp: 47.70 },
  { fecha: "2026-10-20", ppp: 48.05 },
  { fecha: "2026-10-27", ppp: 48.15 },
  { fecha: "2026-10-28", ppp: 48.40 },
  { fecha: "2026-10-29", ppp: 48.77 },
  { fecha: "2026-10-30", ppp: 50.39 }
];
