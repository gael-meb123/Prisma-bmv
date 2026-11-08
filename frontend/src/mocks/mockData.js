/**
 * Prisma BMV - Datos Mock Oficiales para Desarrollo Frontend Aislado
 * Permite a los desarrolladores de React trabajar sin depender de que el backend esté encendido.
 */

export const MOCK_FECHAS = ["2026-11-05", "2026-11-04", "2026-11-03", "2026-10-30", "2026-10-29", "2026-10-28"];

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
  { id: "WALMEX_V1", emisora: "WALMEX", modelo: "G2_V1_POOLED_REL3_CALIBRADO", ppp_base: 50.39, prob: 0.4808, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 2.12, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "WALMEX_V2", emisora: "WALMEX", modelo: "G2_V2_POOLED_REL3_ZONA_NEUTRAL", ppp_base: 50.39, prob: 0.4795, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 2.12, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "WALMEX_V3", emisora: "WALMEX", modelo: "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO", ppp_base: 50.39, prob: 0.4874, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 2.12, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "WALMEX_V4", emisora: "WALMEX", modelo: "G2_V4_POOLED_REL3_MAS_VELOCIDAD_CORTA_DM5", ppp_base: 50.39, prob: 0.4820, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 2.12, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "WALMEX_V5", emisora: "WALMEX", modelo: "G2_V5_ADAPTATIVO_REGIMEN_Y_SECTOR", ppp_base: 50.39, prob: 0.4808, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 2.12, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },

  { id: "GMEXICO_V1", emisora: "GMEXICO", modelo: "G2_V1_POOLED_REL3_CALIBRADO", ppp_base: 224.31, prob: 0.5635, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -13.06, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "GMEXICO_V2", emisora: "GMEXICO", modelo: "G2_V2_POOLED_REL3_ZONA_NEUTRAL", ppp_base: 224.31, prob: 0.5651, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -13.06, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "GMEXICO_V3", emisora: "GMEXICO", modelo: "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO", ppp_base: 224.31, prob: 0.5492, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -13.06, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "GMEXICO_V4", emisora: "GMEXICO", modelo: "G2_V4_POOLED_REL3_MAS_VELOCIDAD_CORTA_DM5", ppp_base: 224.31, prob: 0.5672, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -13.06, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "GMEXICO_V5", emisora: "GMEXICO", modelo: "G2_V5_ADAPTATIVO_REGIMEN_Y_SECTOR", ppp_base: 224.31, prob: 0.5672, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -13.06, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },

  { id: "GFNORTE_V1", emisora: "GFNORTE", modelo: "G2_V1_POOLED_REL3_CALIBRADO", ppp_base: 209.04, prob: 0.4954, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: -1.45, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "GFNORTE_V2", emisora: "GFNORTE", modelo: "G2_V2_POOLED_REL3_ZONA_NEUTRAL", ppp_base: 209.04, prob: 0.4940, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: -1.45, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "GFNORTE_V3", emisora: "GFNORTE", modelo: "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO", ppp_base: 209.04, prob: 0.4965, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: -1.45, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "GFNORTE_V4", emisora: "GFNORTE", modelo: "G2_V4_POOLED_REL3_MAS_VELOCIDAD_CORTA_DM5", ppp_base: 209.04, prob: 0.4958, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: -1.45, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "GFNORTE_V5", emisora: "GFNORTE", modelo: "G2_V5_ADAPTATIVO_REGIMEN_Y_SECTOR", ppp_base: 209.04, prob: 0.4954, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: -1.45, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },

  { id: "AMX_V1", emisora: "AMX", modelo: "G2_V1_POOLED_REL3_CALIBRADO", ppp_base: 23.05, prob: 0.4044, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 6.84, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "AMX_V2", emisora: "AMX", modelo: "G2_V2_POOLED_REL3_ZONA_NEUTRAL", ppp_base: 23.05, prob: 0.3996, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 6.84, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "AMX_V3", emisora: "AMX", modelo: "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO", ppp_base: 23.05, prob: 0.4432, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 6.84, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "AMX_V4", emisora: "AMX", modelo: "G2_V4_POOLED_REL3_MAS_VELOCIDAD_CORTA_DM5", ppp_base: 23.05, prob: 0.4018, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 6.84, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "AMX_V5", emisora: "AMX", modelo: "G2_V5_ADAPTATIVO_REGIMEN_Y_SECTOR", ppp_base: 23.05, prob: 0.4220, pred: "NO_SUBIDA", consenso: "CONSENSO_PANEL_G2_NO_SUBIDA", ret_rel: 6.84, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },

  { id: "FEMSA_V1", emisora: "FEMSA", modelo: "G2_V1_POOLED_REL3_CALIBRADO", ppp_base: 236.49, prob: 0.5112, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -2.18, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "FEMSA_V2", emisora: "FEMSA", modelo: "G2_V2_POOLED_REL3_ZONA_NEUTRAL", ppp_base: 236.49, prob: 0.5125, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -2.18, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "FEMSA_V3", emisora: "FEMSA", modelo: "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO", ppp_base: 236.49, prob: 0.5094, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -2.18, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "FEMSA_V4", emisora: "FEMSA", modelo: "G2_V4_POOLED_REL3_MAS_VELOCIDAD_CORTA_DM5", ppp_base: 236.49, prob: 0.5292, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -2.18, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" },
  { id: "FEMSA_V5", emisora: "FEMSA", modelo: "G2_V5_ADAPTATIVO_REGIMEN_Y_SECTOR", ppp_base: 236.49, prob: 0.5112, pred: "SUBIDA", consenso: "CONSENSO_PANEL_G2_SUBIDA", ret_rel: -2.18, muestra_evaluacion: "IN_SAMPLE_DISENO", estado_resolucion: "PENDIENTE_RECONCILIACION" }
];

export const MOCK_METRICAS_MODELOS = {
  fecha_congelamiento_oficial: "2026-11-06",
  modelo_campeon_vigente: "G2_V4_F1_GAP",
  tamano_efectivo_muestra: {
    n_nominal_15_emisoras: 1557,
    n_eff_15_emisoras: 623.2,
    n_nominal_4_foco: 1142,
    n_eff_4_foco: 461.3,
    factor_autocorrelacion_h5: 2.5
  },
  separacion_muestral_prospectiva: {
    fecha_congelamiento: "2026-11-06",
    total_senales_emitidas: 700,
    in_sample_diseno_count: 700,
    out_of_sample_pre_registrado_count: 0,
    resueltas_oficial_t5_count: 450,
    pendientes_reconciliacion_count: 250,
    en_curso_parcial_count: 200
  },
  modelos_test_15_emisoras: {
    G2_V1_CALIBRADO: { n: 1557, accuracy_pct: 51.38, wilson_95_low_pct: 48.90, wilson_95_high_pct: 53.86, brier: 0.249895, bss_pct: 0.3924, ece: 0.01494, cox_slope_beta: 0.3917, ic_pearson_diario_mean: 0.0085, rank_ic_spearman_diario_mean: 0.0156 },
    G2_V2_ZONA_NEUTRAL: { n: 1557, accuracy_pct: 51.38, wilson_95_low_pct: 48.90, wilson_95_high_pct: 53.86, brier: 0.250002, bss_pct: 0.3497, ece: 0.01451, cox_slope_beta: 0.3351, ic_pearson_diario_mean: 0.0085, rank_ic_spearman_diario_mean: 0.0156 },
    G2_V3_ALTA_DISC: { n: 1557, accuracy_pct: 50.87, wilson_95_low_pct: 48.38, wilson_95_high_pct: 53.35, brier: 0.250082, bss_pct: 0.3178, ece: 0.01598, cox_slope_beta: 0.3189, ic_pearson_diario_mean: 0.0089, rank_ic_spearman_diario_mean: 0.0029 },
    G2_V4_VELOCIDAD_DM5: { n: 1557, accuracy_pct: 51.70, wilson_95_low_pct: 49.22, wilson_95_high_pct: 54.18, brier: 0.249668, bss_pct: 0.4830, ece: 0.01233, cox_slope_beta: 0.5334, ic_pearson_diario_mean: 0.0157, rank_ic_spearman_diario_mean: 0.0153 },
    G2_V5_ADAPTATIVO: { n: 1557, accuracy_pct: 51.70, wilson_95_low_pct: 49.22, wilson_95_high_pct: 54.18, brier: 0.249621, bss_pct: 0.5017, ece: 0.01696, cox_slope_beta: 0.5204, ic_pearson_diario_mean: 0.0235, rank_ic_spearman_diario_mean: 0.0126 },
    G2_V4_ADJ: {
      n: 1557,
      accuracy_pct: 51.70,
      wilson_95_low_pct: 49.22,
      wilson_95_high_pct: 54.18,
      brier: 0.249668,
      bss_pct: 0.4830,
      ece: 0.01233,
      cox_slope_beta: 0.5334,
      ic_pearson_diario_mean: 0.0157,
      rank_ic_spearman_diario_mean: 0.0153,
      reliability_bins: [
        { bin: "[0.00,0.45)", n: 93, prob_media: 0.4317, frecuencia_observada: 0.4409 },
        { bin: "[0.45,0.48)", n: 263, prob_media: 0.4676, frecuencia_observada: 0.4905 },
        { bin: "[0.48,0.50)", n: 451, prob_media: 0.4910, frecuencia_observada: 0.4678 },
        { bin: "[0.50,0.52)", n: 432, prob_media: 0.5091, frecuencia_observada: 0.5116 },
        { bin: "[0.52,0.55)", n: 229, prob_media: 0.5326, frecuencia_observada: 0.5197 },
        { bin: "[0.55,1.00]", n: 89, prob_media: 0.5680, frecuencia_observada: 0.5506 }
      ]
    },
    G2_V4_F1_GAP: {
      n: 1557,
      accuracy_pct: 52.60,
      wilson_95_low_pct: 50.12,
      wilson_95_high_pct: 55.07,
      brier: 0.249627,
      bss_pct: 0.4991,
      ece: 0.02096,
      cox_slope_beta: 0.4835,
      ic_pearson_diario_mean: 0.0185,
      rank_ic_spearman_diario_mean: 0.0202
    }
  },
  politica_asignacion_capital: {
    estrategia_principal: "G2_V4_F1_GAP_KELLY_250D",
    parametros: {
      kelly_fraction: 0.25,
      umbral_abstencion_prob: 0.52,
      cap_emisora_pct: 25.0,
      cap_exposicion_bruta_pct: 75.0,
      costo_round_trip_bps: 20.0,
      hit_rate_breakeven_pct: 53.70
    },
    desempeno_test_250d: {
      retorno_acumulado_neto_pct: 6.94,
      retorno_acumulado_bruto_pct: 9.74,
      cagr_neto_pct: 5.99,
      volatilidad_anual_pct: 5.73,
      sharpe_bruto: 1.42,
      sharpe_neto: 1.04,
      max_drawdown_neto_pct: -3.46,
      hit_rate_5d_trades_activos_pct: 55.24,
      exposicion_media_pct: 26.25
    },
    pesos_sugeridos_Recientes: {
      fecha: "2026-11-05",
      AMX: 0.0,
      FEMSA: 22.98,
      GFNORTE: 0.0,
      GMEXICO: 25.0,
      WALMEX: 0.0,
      EFECTIVO: 52.02
    }
  },
  monitoreo_secuencial_fase7: {
    especificacion_matematica: {
      cusum_page: { k_holgura_nats: 0.001, h_umbral_alarma_nats: 1.5 },
      sprt_wald: { p0: 0.5, p1: 0.55, alpha: 0.05, beta: 0.2, n_independientes_requeridas_80pct: 617, frontera_superior_A: 2.772589, frontera_inferior_B: -1.558145 }
    },
    evaluacion_secuencial_test_15_emisoras: {
      G2_V4_F1_GAP: {
        cusum_logscore: {
          delta_log_score_acumulado_nats: 3.7908,
          delta_log_score_acumulado_bits: 5.469,
          cusum_actual_nats: 0.4679,
          cusum_max_historico_nats: 1.1107,
          alarma_cusum_activa: false,
          estado_cusum: "OPERACION_NORMAL_ESTABLE"
        },
        sprt_wald: {
          n_nominal: 1557,
          n_efectivo: 624.22,
          tasa_acierto_pct: 52.6,
          llr_nominal: 0.303,
          llr_efectivo: 0.1215,
          estado_sprt: "CONTINUAR_MUESTREO",
          n_independientes_requeridas_80pct: 617,
          senales_efectivas_faltantes_80pct: 0.0
        }
      }
    }
  }
};

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
