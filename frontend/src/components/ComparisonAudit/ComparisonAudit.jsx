import React from "react";
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import { Clock, ShieldCheck, Database, Cloud, Terminal, CheckCircle2, ArrowLeft, Server, BarChart3, Scale } from "lucide-react";
import { Badge, Button } from "../UI";
import { MOCK_METRICAS_MODELOS } from "../../mocks/mockData";

const Plot = createPlotlyComponent(Plotly);

export function ComparisonAudit({ ticker = "WALMEX", senales = [], metricas = null, onBack, onOpenReport }) {
  const m = metricas || MOCK_METRICAS_MODELOS;
  const primera = senales[0] || {};
  const pppBase = primera.ppp_base || 50.39;
  const muestraEvaluacion = primera.muestra_evaluacion || "IN_SAMPLE_DISENO";
  const estadoResolucion = primera.estado_resolucion || "PENDIENTE_RECONCILIACION";

  const rawBins =
    m?.curvas_calibracion_reliability?.G2_V4_ADJ ||
    m?.modelos_test_15_emisoras?.G2_V4_ADJ?.reliability_bins ||
    MOCK_METRICAS_MODELOS.modelos_test_15_emisoras.G2_V4_ADJ.reliability_bins;
  const bins = rawBins.map((b) => ({
    prob_media: b.prob_media ?? b.p_media ?? 0.5,
    frecuencia_observada: b.frecuencia_observada ?? b.y_obs_media ?? 0.5,
  }));

  // Adaptar lista de modelos desde backend (`modelos_test`) o desde mock (`modelos_test_15_emisoras`)
  let filasModelos = [];
  if (Array.isArray(m?.modelos_test) && m.modelos_test.length > 0) {
    filasModelos = m.modelos_test.map((item) => ({
      key: item.id_modelo,
      label: item.nombre,
      accuracy_pct: item.exactitud_15_pct,
      wilson_low: Array.isArray(item.wilson_95_15_pct) ? item.wilson_95_15_pct[0] : 49.0,
      wilson_high: Array.isArray(item.wilson_95_15_pct) ? item.wilson_95_15_pct[1] : 54.0,
      bss_pct: item.bss_vs_climatologia_15_pct ?? 0.0,
      rank_ic: item.rank_ic_15 ?? 0.0,
      ece: item.ece_15 ?? 0.0,
    }));
  } else {
    const ordenMock = [
      { key: "G2_V4_F1_GAP", label: "G2_V4_F1_GAP (Campeón + gap_uh_ppp)" },
      { key: "G2_V4_VELOCIDAD_DM5", label: "G2_V4 (Agotamiento Corto DM5)" },
      { key: "G2_V5_ADAPTATIVO", label: "G2_V5 (Adaptativo Régimen/Sector)" },
      { key: "G2_V1_CALIBRADO", label: "G2_V1 (Calibrado Base)" },
      { key: "G2_V2_ZONA_NEUTRAL", label: "G2_V2 (Zona Neutral)" },
      { key: "G2_V3_ALTA_DISC", label: "G2_V3 (Alta Discriminación)" },
    ];
    filasModelos = ordenMock
      .map((row) => {
        const it = m?.modelos_test_15_emisoras?.[row.key];
        if (!it) return null;
        return {
          key: row.key,
          label: row.label,
          accuracy_pct: it.accuracy_pct,
          wilson_low: it.wilson_95_low_pct,
          wilson_high: it.wilson_95_high_pct,
          bss_pct: it.bss_pct,
          rank_ic: it.rank_ic_spearman_diario_mean,
          ece: it.ece,
        };
      })
      .filter(Boolean);
  }

  // Adaptar política ¼-Kelly desde backend (`asignacion_capital_fase5`) o mock (`politica_asignacion_capital`)
  const f5Backend = m?.asignacion_capital_fase5?.estrategias?.G2_V4_F1_GAP_KELLY_250D;
  const kelly = f5Backend
    ? {
        estrategia_principal: "G2_V4_F1_GAP_KELLY_250D",
        parametros: {
          hit_rate_breakeven_pct:
            m?.asignacion_capital_fase5?.parametros_politica?.punto_equilibrio_probabilidad_estimado_pct ?? 53.7,
        },
        desempeno_test_250d: {
          retorno_acumulado_neto_pct:
            f5Backend.retorno_acumulado_neto_20bps_pct ?? f5Backend.retorno_acumulado_neto_pct ?? 6.94,
          cagr_neto_pct: f5Backend.retorno_anualizado_neto_pct ?? f5Backend.cagr_neto_pct ?? 5.99,
          volatilidad_anual_pct:
            f5Backend.volatilidad_anualizada_pct ?? f5Backend.volatilidad_anual_pct ?? 5.73,
          sharpe_bruto: Number(f5Backend.sharpe_bruto ?? 1.42).toFixed(2),
          sharpe_neto: Number(f5Backend.sharpe_neto_20bps ?? f5Backend.sharpe_neto ?? 1.04).toFixed(2),
          max_drawdown_neto_pct: f5Backend.max_drawdown_neto_pct ?? -3.46,
          hit_rate_5d_trades_activos_pct:
            f5Backend.hit_rate_operaciones_5d_pct ?? f5Backend.hit_rate_5d_trades_activos_pct ?? 55.24,
          exposicion_media_pct: f5Backend.exposicion_media_pct ?? 28.01,
        },
        pesos_sugeridos_Recientes:
          m?.asignacion_capital_fase5?.ultimos_pesos_sugeridos_pct ||
          MOCK_METRICAS_MODELOS.politica_asignacion_capital.pesos_sugeridos_Recientes,
      }
    : m?.politica_asignacion_capital || MOCK_METRICAS_MODELOS.politica_asignacion_capital;

  const audBackend = m?.auditoria_prospectiva;
  const sep = audBackend
    ? {
        fecha_congelamiento: m?.fecha_congelamiento_oficial || "2026-11-06",
        in_sample_diseno_count: audBackend.conteo_por_muestra_evaluacion?.IN_SAMPLE_DISENO ?? 125,
        out_of_sample_pre_registrado_count:
          audBackend.conteo_por_muestra_evaluacion?.OUT_OF_SAMPLE_PRE_REGISTRADO ?? 0,
        resueltas_oficial_t5_count: audBackend.evaluacion_oficial_resuelta_t5?.total_senales_resueltas_t5 ?? 0,
        pendientes_reconciliacion_count:
          audBackend.evaluacion_pendiente_reconciliacion_t5?.total_senales_pendientes_t5 ?? 125,
      }
    : m?.separacion_muestral_prospectiva || MOCK_METRICAS_MODELOS.separacion_muestral_prospectiva;

  const neff = m?.tamano_efectivo_muestra || MOCK_METRICAS_MODELOS.tamano_efectivo_muestra;
  const seqF7 =
    m?.monitoreo_secuencial_fase7?.evaluacion_secuencial_test_15_emisoras?.G2_V4_F1_GAP ||
    MOCK_METRICAS_MODELOS.monitoreo_secuencial_fase7.evaluacion_secuencial_test_15_emisoras.G2_V4_F1_GAP;

  const stepsTimeline = [
    { paso: "t (Emisión)", fecha: "Sesión t", estado: "Vigente", detalle: `Señal generada al cierre BMV. PPP Base = $${Number(pppBase).toFixed(2)}.` },
    { paso: "t + 1", fecha: "Sesión t+1", estado: "En curso", detalle: "Evaluación preliminar de volatilidad intradiaria y spread." },
    { paso: "t + 2", fecha: "Sesión t+2", estado: "En espera", detalle: "Monitoreo del diferencial relativo acumulado vs panel." },
    { paso: "t + 3", fecha: "Sesión t+3", estado: "En espera", detalle: "Prueba de persistencia estadística en el spread." },
    { paso: "t + 4", fecha: "Sesión t+4", estado: "En espera", detalle: "Ventana de pre-liquidación cuantitativa." },
    { paso: "t + 5 (Liquidación)", fecha: "Horizonte t+5", estado: "Horizonte", detalle: `Cómputo formal del payoff ajustado por dividendos: Y_t = 1 si PPP_adj(t+5) > ${Number(pppBase).toFixed(2)}.` },
  ];

  return (
    <div className="comparison-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Botón Volver y Título */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" }}>
        <button
          onClick={onBack}
          style={{ background: "transparent", border: 0, cursor: "pointer", display: "flex", alignItems: "center", color: "var(--teal-dark)", fontWeight: "700", fontSize: "13px" }}
        >
          <ArrowLeft size={16} style={{ marginRight: 4 }} />
          Volver a Análisis
        </button>
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
          <Badge status={muestraEvaluacion} />
          <Badge status={estadoResolucion} />
        </div>
      </div>

      <div>
        <span className="eyebrow">MÓDULO 3 · AUDITORÍA TEMPORAL, CALIBRACIÓN Y ASIGNACIÓN DE CAPITAL</span>
        <h2 style={{ fontSize: "20px", margin: "4px 0 6px 0", color: "var(--navy)" }}>
          Ciclo de Maduración ($t$ a $t+5$) y Calidad Institucional: {ticker}
        </h2>
        <p style={{ fontSize: "13px", color: "var(--muted)", margin: 0 }}>
          Separación estricta entre muestra de diseño (<code style={{ fontSize: "11px" }}>&lt; {sep.fecha_congelamiento}</code>) y muestra prospectiva pre-registrada (<code style={{ fontSize: "11px" }}>&ge; {sep.fecha_congelamiento}</code>).
        </p>
      </div>

      {/* Grid del Ciclo de Vida Temporal */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "8px" }}>
        {stepsTimeline.map((s, idx) => {
          const isFirst = idx === 0;
          return (
            <div
              key={s.paso}
              style={{
                background: isFirst ? "#e6f6f9" : "#ffffff",
                border: isFirst ? "1.5px solid #079baa" : "1px solid var(--line)",
                borderRadius: "8px",
                padding: "10px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between"
              }}
            >
              <div>
                <strong style={{ fontSize: "12px", color: "var(--navy)", display: "block" }}>{s.paso}</strong>
                <span style={{ fontSize: "10px", color: "var(--muted)", fontFamily: "monospace" }}>{s.fecha}</span>
              </div>
              <p style={{ fontSize: "11px", color: "var(--muted)", margin: "8px 0 0 0", lineHeight: "1.3" }}>
                {s.detalle}
              </p>
            </div>
          );
        })}
      </div>

      {/* Separación Muestral Prospectiva */}
      <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "14px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
          <strong style={{ fontSize: "13px", color: "var(--navy)" }}>
            Gobernanza Muestral Prospectiva (Congelamiento SHA-256: {sep.fecha_congelamiento})
          </strong>
          <span style={{ fontSize: "11px", color: "var(--muted)", fontFamily: "monospace" }}>
            N_nominal = {neff.n_nominal_15_emisoras} · N_eff = {neff.n_eff_15_emisoras} (15 emisoras)
          </span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "10px" }}>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "var(--muted)", fontWeight: "700" }}>IN-SAMPLE DISEÑO</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "var(--navy)" }}>
              {sep.in_sample_diseno_count} señales
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>Previas a {sep.fecha_congelamiento}</span>
          </div>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "#059669", fontWeight: "700" }}>OUT-OF-SAMPLE PRE-REG.</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "#059669" }}>
              {sep.out_of_sample_pre_registrado_count} señales
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>Desde {sep.fecha_congelamiento}</span>
          </div>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "#079baa", fontWeight: "700" }}>RESUELTAS OFICIAL (t+5)</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "#079baa" }}>
              {sep.resueltas_oficial_t5_count} señales
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>Horizonte cumplido</span>
          </div>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "#d97706", fontWeight: "700" }}>EN MADURACIÓN (t+1..t+4)</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "#d97706" }}>
              {sep.pendientes_reconciliacion_count} señales
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>Sin tocar coeficientes</span>
          </div>
        </div>
      </div>

      {/* Calidad del Modelo: Curva de Calibración (Reliability Diagram) + Tabla Institucional */}
      <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "16px" }}>
        <h3 style={{ fontSize: "14px", color: "var(--navy)", margin: "0 0 10px 0", display: "flex", alignItems: "center", gap: "6px" }}>
          <BarChart3 size={18} style={{ color: "#079baa" }} />
          Calidad Institucional Fuera de Muestra (TEST: N = {neff.n_nominal_15_emisoras}, N_eff = {neff.n_eff_15_emisoras})
        </h3>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "14px", alignItems: "center", marginBottom: "14px" }}>
          <div style={{ height: "230px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0", padding: "4px" }}>
            <Plot
              data={[
                {
                  x: [0.40, 0.60],
                  y: [0.40, 0.60],
                  type: "scatter",
                  mode: "lines",
                  name: "Calibración Ideal (45°)",
                  line: { color: "#94a3b8", width: 1.5, dash: "dash" }
                },
                {
                  x: bins.map((b) => b.prob_media),
                  y: bins.map((b) => b.frecuencia_observada),
                  type: "scatter",
                  mode: "lines+markers",
                  name: "G2_V4_ADJ (ECE = 0.0123)",
                  line: { color: "#079baa", width: 2.5 },
                  marker: { color: "#062c50", size: 7 }
                }
              ]}
              layout={{
                autosize: true,
                margin: { l: 44, r: 16, t: 26, b: 36 },
                title: { text: "Diagrama de Confiabilidad (TEST)", font: { size: 11, color: "#062c50" } },
                paper_bgcolor: "transparent",
                plot_bgcolor: "transparent",
                showlegend: true,
                legend: { orientation: "h", x: 0, y: -0.22, font: { size: 10 } },
                xaxis: { title: "Prob. Predicha", tickfont: { size: 10 }, range: [0.41, 0.59], gridcolor: "#e2e8f0" },
                yaxis: { title: "Frec. Observada", tickfont: { size: 10 }, range: [0.41, 0.59], gridcolor: "#e2e8f0" }
              }}
              config={{ responsive: true, displayModeBar: false }}
              style={{ width: "100%", height: "100%" }}
            />
          </div>

          <div style={{ overflowX: "auto" }}>
            <table className="comparison-table" style={{ width: "100%", fontSize: "11px" }}>
              <thead>
                <tr>
                  <th>Modelo</th>
                  <th style={{ textAlign: "right" }}>Acc. (IC 95%)</th>
                  <th style={{ textAlign: "right" }}>BSS</th>
                  <th style={{ textAlign: "right" }}>Rank IC</th>
                  <th style={{ textAlign: "right" }}>ECE</th>
                </tr>
              </thead>
              <tbody>
                {filasModelos.map((item) => (
                  <tr key={item.key}>
                    <td><strong>{item.label}</strong></td>
                    <td style={{ textAlign: "right", fontFamily: "monospace" }}>
                      {Number(item.accuracy_pct).toFixed(2)}% <span style={{ color: "var(--muted)", fontSize: "10px" }}>[{Number(item.wilson_low).toFixed(1)}, {Number(item.wilson_high).toFixed(1)}]</span>
                    </td>
                    <td style={{ textAlign: "right", fontFamily: "monospace", color: Number(item.bss_pct) >= 0 ? "#059669" : "#dc2626", fontWeight: "700" }}>
                      {Number(item.bss_pct) >= 0 ? "+" : ""}{Number(item.bss_pct).toFixed(2)}%
                    </td>
                    <td style={{ textAlign: "right", fontFamily: "monospace" }}>
                      {Number(item.rank_ic ?? 0) >= 0 ? "+" : ""}{Number(item.rank_ic ?? 0).toFixed(4)}
                    </td>
                    <td style={{ textAlign: "right", fontFamily: "monospace" }}>
                      {Number(item.ece ?? 0).toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Asignación de Capital ¼-Kelly */}
      <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "16px" }}>
        <h3 style={{ fontSize: "14px", color: "var(--navy)", margin: "0 0 10px 0", display: "flex", alignItems: "center", gap: "6px" }}>
          <Scale size={18} style={{ color: "#10b981" }} />
          Política de Asignación de Capital ¼-Kelly Consciente de Costos ({kelly?.estrategia_principal})
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(135px, 1fr))", gap: "10px", marginBottom: "12px" }}>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "var(--muted)", fontWeight: "700" }}>RETORNO NETO (TEST)</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "#059669" }}>
              +{kelly?.desempeno_test_250d?.retorno_acumulado_neto_pct}%
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>CAGR +{kelly?.desempeno_test_250d?.cagr_neto_pct}% (20 bps RT)</span>
          </div>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "var(--muted)", fontWeight: "700" }}>SHARPE NETO / BRUTO</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "var(--navy)" }}>
              {kelly?.desempeno_test_250d?.sharpe_neto} / {kelly?.desempeno_test_250d?.sharpe_bruto}
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>Vol. anual {kelly?.desempeno_test_250d?.volatilidad_anual_pct}%</span>
          </div>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "var(--muted)", fontWeight: "700" }}>MAX DRAWDOWN NETO</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "#dc2626" }}>
              {kelly?.desempeno_test_250d?.max_drawdown_neto_pct}%
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>Exposición media {kelly?.desempeno_test_250d?.exposicion_media_pct}%</span>
          </div>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "var(--muted)", fontWeight: "700" }}>HIT RATE ACTIVO 5D</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "#079baa" }}>
              {kelly?.desempeno_test_250d?.hit_rate_5d_trades_activos_pct}%
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>Breakeven {kelly?.parametros?.hit_rate_breakeven_pct}%</span>
          </div>
        </div>

        <div style={{ fontSize: "11px", color: "var(--muted)", display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
          <strong style={{ color: "var(--navy)" }}>Pesos sugeridos vigentes ({kelly?.pesos_sugeridos_Recientes?.fecha || kelly?.pesos_sugeridos_Recientes?.fecha_corte || "2026-11-05"}):</strong>
          {["GMEXICO", "FEMSA", "WALMEX", "GFNORTE", "AMX", "EFECTIVO"].map((k) => (
            <span key={k} style={{ background: k === ticker ? "#e6f6f9" : "#f1f5f9", padding: "3px 8px", borderRadius: "6px", fontFamily: "monospace", fontWeight: k === ticker ? "800" : "600", color: k === ticker ? "#079baa" : "var(--navy)" }}>
              {k}: {Number(kelly?.pesos_sugeridos_Recientes?.[k] ?? 0).toFixed(2)}%
            </span>
          ))}
        </div>
      </div>

      {/* Monitoreo Secuencial Activo (CUSUM + SPRT de Wald - Fase 7) */}
      <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "16px" }}>
        <h3 style={{ fontSize: "14px", color: "var(--navy)", margin: "0 0 10px 0", display: "flex", alignItems: "center", gap: "6px" }}>
          <ShieldCheck size={18} style={{ color: "#079baa" }} />
          Monitoreo Secuencial Activo: CUSUM de Log-Score y SPRT de Wald (H₀: p=0.50 vs H₁: p=0.55)
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "10px" }}>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "var(--muted)", fontWeight: "700" }}>Δ LOG-SCORE VS CLIM.</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "#059669" }}>
              +{Number(seqF7?.cusum_logscore?.delta_log_score_acumulado_bits ?? 5.47).toFixed(2)} bits
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>+{Number(seqF7?.cusum_logscore?.delta_log_score_acumulado_nats ?? 3.79).toFixed(2)} nats acumulados</span>
          </div>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "var(--muted)", fontWeight: "700" }}>ESTADÍSTICO CUSUM (S_t)</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: seqF7?.cusum_logscore?.alarma_cusum_activa ? "#dc2626" : "#059669" }}>
              {Number(seqF7?.cusum_logscore?.cusum_actual_nats ?? 0.47).toFixed(3)} / 1.50
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>{seqF7?.cusum_logscore?.estado_cusum || "OPERACION_NORMAL_ESTABLE"}</span>
          </div>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "var(--muted)", fontWeight: "700" }}>SPRT WALD (LLR EFECTIVO)</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "var(--navy)" }}>
              +{Number(seqF7?.sprt_wald?.llr_efectivo ?? 0.1215).toFixed(3)}
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>B = -1.56 · A = +2.77 ({seqF7?.sprt_wald?.estado_sprt || "CONTINUAR_MUESTREO"})</span>
          </div>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <small style={{ fontSize: "10px", color: "var(--muted)", fontWeight: "700" }}>UMBRAL POTENCIA 80%</small>
            <div style={{ fontSize: "16px", fontWeight: "800", fontFamily: "monospace", color: "#079baa" }}>
              {seqF7?.sprt_wald?.n_independientes_requeridas_80pct ?? 617} indep.
            </div>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>OOS prospectivo: faltan {seqF7?.sprt_wald?.n_independientes_requeridas_80pct ?? 617} indep.</span>
          </div>
        </div>
      </div>

      {/* Gobernanza Cloud Data Lakehouse AWS */}
      <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "12px", padding: "16px" }}>
        <h3 style={{ fontSize: "14px", color: "var(--navy)", margin: "0 0 12px 0", display: "flex", alignItems: "center", gap: "6px" }}>
          <Cloud size={18} style={{ color: "#079baa" }} />
          Gobernanza Serverless del Data Lakehouse en AWS
        </h3>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "10px" }}>
          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: "11px", fontWeight: "700", color: "#079baa" }}>EVENTBRIDGE</span>
            <div style={{ fontSize: "12px", fontWeight: "700", fontFamily: "monospace", marginTop: "2px" }}>16:45 CDMX</div>
            <p style={{ fontSize: "10px", color: "var(--muted)", margin: "4px 0 0 0" }}>Disparo cron diario tras el cierre bursátil.</p>
          </div>

          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: "11px", fontWeight: "700", color: "#10b981" }}>AWS LAMBDA</span>
            <div style={{ fontSize: "12px", fontWeight: "700", fontFamily: "monospace", marginTop: "2px" }}>Float64 Parity</div>
            <p style={{ fontSize: "10px", color: "var(--muted)", margin: "4px 0 0 0" }}>Inferencia IRLS 5 modelos G2 con paridad &lt; 10⁻⁶.</p>
          </div>

          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: "11px", fontWeight: "700", color: "#d97706" }}>AMAZON S3</span>
            <div style={{ fontSize: "12px", fontWeight: "700", fontFamily: "monospace", marginTop: "2px" }}>Medallion Lake</div>
            <p style={{ fontSize: "10px", color: "var(--muted)", margin: "4px 0 0 0" }}>Bronze (HTML), Silver (CSV), Gold (Parquet + JSON v2).</p>
          </div>

          <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: "11px", fontWeight: "700", color: "#6366f1" }}>AMAZON ATHENA</span>
            <div style={{ fontSize: "12px", fontWeight: "700", fontFamily: "monospace", marginTop: "2px" }}>SQL Serverless</div>
            <p style={{ fontSize: "10px", color: "var(--muted)", margin: "4px 0 0 0" }}>Auditoría regulatoria e interoperabilidad.</p>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: "10px", marginTop: "4px" }}>
        <Button variant="primary" onClick={onOpenReport}>
          Imprimir Ficha Ejecutiva de Auditoría
        </Button>
      </div>
    </div>
  );
}
