import React, { useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  ArrowDownRight,
  BrainCircuit,
  Cloud,
  Database,
  FileText,
  Gauge,
  Map as MapIcon,
  Search,
  ShieldCheck,
  Timer,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { Badge } from "../UI";
import { TerminalChartPlotly } from "../ComparisonAudit/TerminalChartPlotly";
import { ComparisonAudit } from "../ComparisonAudit/ComparisonAudit";
import { WelcomeArt } from "../Illustrations";
import { ChartCard, Estado, ExplainButton } from "./ChartCard";
import { CostosInversion } from "./CostosInversion";
import {
  CalibracionChart,
  ContribucionesChart,
  GobernanzaSankey,
  MarcadorChart,
  ProbabilidadesChart,
  SectoresChart,
  TrayectoriaChart,
} from "./charts";
import {
  explicarCalibracion,
  explicarFactor,
  explicarGobernanza,
  explicarMarcador,
  explicarMonitor,
  explicarProbabilidades,
  explicarSectores,
  explicarSerie,
  explicarTrayectoria,
  textoConsenso,
} from "../../guide/explicaciones.mjs";
import { startTour } from "../../guide/tour.mjs";
import { describirModelos, estadoModeloHistorico, formatMoney, formatPct, modelosHistoricosSinSenal, nombreModelo } from "../../utils/presentation.mjs";

const prob = (p) => (p == null ? "—" : `${(p * 100).toFixed(1)}%`);

function Kpi({ label, value, sub, icon: Icon, tone }) {
  return (
    <div className="bk-card tm-kpi">
      {Icon && <span className="tm-kpi-icon"><Icon size={18} /></span>}
      <small>{label}</small>
      <strong className={`bk-mono ${tone === "up" ? "bk-up" : tone === "down" ? "bk-down" : ""}`}>{value}</strong>
      {sub && <span>{sub}</span>}
    </div>
  );
}

function tonoDe(v) {
  if (v == null) return undefined;
  return v > 0 ? "up" : v < 0 ? "down" : undefined;
}

function Bloqueado({ emisora, onPlanGate }) {
  return (
    <div className="bk-card">
      <Estado locked titulo={`${emisora} no está incluida en tu plan`} texto="El plan Explorer incluye el análisis completo de WALMEX. Los planes de pago abren las 15 emisoras del IPC.">
        <button type="button" className="bk-btn bk-btn-primary" onClick={() => onPlanGate(emisora)}>
          Ver planes <ArrowRight size={16} />
        </button>
      </Estado>
    </div>
  );
}

function consensoChip(etiqueta) {
  if (!etiqueta) return <span className="bk-chip bk-chip-navy">Sin señal</span>;
  if (etiqueta.includes("NO_SUBIDA")) return <span className="bk-chip bk-chip-down"><TrendingDown size={13} /> Consenso: no subida</span>;
  if (etiqueta.includes("SUBIDA")) return <span className="bk-chip bk-chip-up"><TrendingUp size={13} /> Consenso: subida</span>;
  return <span className="bk-chip bk-chip-warn">Divergencia</span>;
}

/* ============================================================================
   RESUMEN
   ============================================================================ */
export function Resumen({ ctx }) {
  const { account, emisora, datos, permitido, irA, onSelectTicker, onPlanGate } = ctx;
  const mercado = datos.mercado.data;
  const cot = mercado?.cotizaciones || [];
  const k = mercado?.kpis || {};
  const actual = cot.find((c) => c.emisora === emisora);
  const senal = datos.senal.data;
  const serie = datos.serie.data;
  const nombre = account.user?.name?.split(" ")[0] || "";
  const movimientos = [...cot]
    .filter((c) => c.variacion_pct != null)
    .sort((a, b) => Math.abs(b.variacion_pct) - Math.abs(a.variacion_pct))
    .slice(0, 6);

  return (
    <>
      <section className="tm-welcome">
        <WelcomeArt />
        <div style={{ position: "relative", zIndex: 1 }}>
          <h2>Hola{nombre ? `, ${nombre}` : ""}. Este es tu resumen del mercado.</h2>
          <p>
            Plan {account.plan.name} · sesión {mercado?.fecha || "—"} · {k.total_verificadas ?? "—"} de {k.total_emisoras ?? "—"} filas
            con PPP marcado como verificado; cobertura parcial.
          </p>
        </div>
        <div className="tm-welcome-actions">
          <button type="button" className="bk-btn bk-btn-primary bk-btn-sm" onClick={() => irA("senales")}>
            Ver señales de {emisora} <ArrowRight size={15} />
          </button>
          {import.meta.env.VITE_REQUIRE_REAL_API !== "true" && <button type="button" className="bk-btn bk-btn-light bk-btn-sm" onClick={() => startTour("terminal")}>
            <MapIcon size={15} /> Recorrido guiado
          </button>}
        </div>
      </section>

      <div className="tm-kpis" data-tour="kpis">
        <Kpi
          label={`PPP ${emisora}`}
          value={actual?.ppp_bmv_mxn != null ? formatMoney(actual.ppp_bmv_mxn) : "Sin dato"}
          sub={actual?.variacion_pct != null ? `${formatPct(actual.variacion_pct)} vs. sesión anterior` : "Variación no disponible"}
          icon={Wallet}
          tone={tonoDe(actual?.variacion_pct)}
        />
        <div className="bk-card tm-kpi">
          <span className="tm-kpi-icon"><BrainCircuit size={18} /></span>
          <small>Consenso de modelos</small>
          <div style={{ marginTop: 4 }}>{permitido ? (senal ? consensoChip(senal.consensos?.G2) : <span className="bk-chip bk-chip-navy">No disponible</span>) : <span className="bk-chip bk-chip-navy">Fuera de tu plan</span>}</div>
          <span>{senal?.fecha ? `Señal del ${senal.fecha} · horizonte t+5` : "—"}</span>
        </div>
        <Kpi
          label="Alzas · bajas"
          value={`${k.conteo_alzas ?? "—"} · ${k.conteo_bajas ?? "—"}`}
          sub={`${k.total_ausentes ?? "—"} sin PPP verificado (no se rellenan)`}
          icon={Gauge}
        />
        <Kpi
          label="Mayor alza"
          value={k.top_alza_ticker ? `${k.top_alza_ticker} ${formatPct(k.top_alza_pct)}` : "—"}
          sub={k.top_baja_ticker ? `Mayor baja: ${k.top_baja_ticker} ${formatPct(k.top_baja_pct)}` : ""}
          icon={TrendingUp}
          tone="up"
        />
      </div>

      <div className="tm-row tm-row-main">
        <section className="bk-card tm-chart" data-tour="grafica" style={{ overflow: "hidden" }}>
          {!permitido ? (
            <Bloqueado emisora={emisora} onPlanGate={onPlanGate} />
          ) : serie?.puntos ? (
            <TerminalChartPlotly
              serie={serie.puntos}
              ticker={emisora}
              sector={serie.sector}
              height={360}
              action={
                <ExplainButton
                  tour="explica"
                  label="Explicar"
                  explicar={() => explicarSerie({ emisora, sector: serie.sector, puntos: serie.puntos })}
                />
              }
            />
          ) : (
            <Estado loading={datos.serie.loading} titulo="Sin serie disponible" texto={datos.serie.error?.message} />
          )}
        </section>

        <ChartCard
          title="Movimientos del día"
          subtitle="Las emisoras que más se movieron en el PPP oficial"
          explicar={() => explicarMonitor({ fecha: mercado?.fecha, cotizaciones: cot })}
        >
          <div className="tm-list" style={{ margin: "0 -14px" }}>
            {movimientos.map((c) => {
              const up = c.variacion_pct >= 0;
              return (
                <button
                  key={c.emisora}
                  type="button"
                  className="tm-list-item"
                  style={{ background: "none", border: 0, borderTop: "1px solid var(--bk-line-soft)", width: "100%", textAlign: "left", cursor: "pointer" }}
                  onClick={() => onSelectTicker(c.emisora)}
                >
                  <span className="tm-list-icon" style={{ background: up ? "var(--bk-up-bg)" : "var(--bk-down-bg)", color: up ? "var(--bk-up)" : "var(--bk-down)" }}>
                    {up ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}
                  </span>
                  <span className="tm-list-main">
                    <strong>{c.emisora}</strong>
                    <span>{c.sector}</span>
                  </span>
                  <span className="tm-list-value bk-mono">
                    {formatMoney(c.ppp_bmv_mxn)}
                    <small className={up ? "bk-up" : "bk-down"}>{formatPct(c.variacion_pct)}</small>
                  </span>
                </button>
              );
            })}
            {!movimientos.length && <Estado loading={datos.mercado.loading} titulo="Sin movimientos" />}
          </div>
        </ChartCard>
      </div>

      <div className="tm-row tm-row-half">
        <ChartCard
          title="Variación media por sector"
          subtitle="Solo emisoras con PPP verificado"
          explicar={datos.sectores.data ? () => explicarSectores(datos.sectores.data) : null}
          tour="sectores"
        >
          {datos.sectores.data?.sectores?.some((s) => s.variacion_media_pct != null)
            ? <SectoresChart sectores={datos.sectores.data.sectores} />
            : <Estado loading={datos.sectores.loading} titulo="Variaciones por sector no disponibles"
                texto={datos.sectores.error?.message || "La fuente disponible no contiene variaciones verificadas para este corte."} />}
        </ChartCard>
        <ChartCard
          title={`Probabilidad por modelo · ${emisora}`}
          subtitle="Que el PPP suba en 5 sesiones; la línea marca 50 %"
          explicar={senal ? () => explicarProbabilidades({ emisora, ...senal, modelos: senal.modelos.map((m) => ({ ...m, nombre: nombreModelo(m.modelo, m.nombre) })) }) : null}
          actions={
            <button type="button" className="bk-btn bk-btn-ghost bk-btn-sm" onClick={() => irA("senales")}>
              Detalle <ArrowRight size={14} />
            </button>
          }
        >
          {!permitido ? (
            <Bloqueado emisora={emisora} onPlanGate={onPlanGate} />
          ) : senal?.modelos?.length ? (
            <ProbabilidadesChart modelos={senal.modelos} />
          ) : (
            <Estado loading={datos.senal.loading} titulo="Sin señal para esta sesión" />
          )}
        </ChartCard>
      </div>
    </>
  );
}

/* ============================================================================
   MERCADO
   ============================================================================ */
export function Mercado({ ctx }) {
  const { emisora, datos, irA, onSelectTicker, onShowEvidence, puedeVer, universoMercado = "base_15", setUniversoMercado } = ctx;
  const mercado = datos.mercado.data;
  const cot = mercado?.cotizaciones || [];
  const catalogoIpc = mercado?.catalogo_ipc || null;
  const esIpc35 = universoMercado === "ipc35_provisional";
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState("Todos");
  const [filtroOrigen, setFiltroOrigen] = useState("todos");
  const [avisoProvisional, setAvisoProvisional] = useState(null);
  const sectores = ["Todos", ...new Set(cot.map((c) => c.sector).filter(Boolean))];
  const filtradas = cot.filter((c) => {
    const q = query.toLowerCase();
    const okQ = !q
      || c.emisora.toLowerCase().includes(q)
      || (c.serie || "").toLowerCase().includes(q)
      || (c.sector || "").toLowerCase().includes(q)
      || (c.alias_blackrock || "").toLowerCase().includes(q);
    const okSector = sector === "Todos" || c.sector === sector;
    const okOrigen = !esIpc35
      || filtroOrigen === "todos"
      || (filtroOrigen === "base_15" && c.origen_catalogo === "ACTUAL_15")
      || (filtroOrigen === "candidato_20" && c.origen_catalogo === "CANDIDATO_20")
      || (filtroOrigen === "con_ppp" && c.ppp_bmv_mxn != null)
      || (filtroOrigen === "huecos" && c.ppp_bmv_mxn == null);
    return okQ && okSector && okOrigen;
  });
  const sha = mercado?.kpis?.sha256_boletin || "";
  const actual = cot.find((c) => c.emisora === emisora);

  function cambiarUniverso(nuevo) {
    if (!setUniversoMercado) return;
    setAvisoProvisional(null);
    setSector("Todos");
    setFiltroOrigen("todos");
    setUniversoMercado(nuevo);
  }

  function abrirFila(c) {
    if (c.origen_catalogo === "CANDIDATO_20") {
      setAvisoProvisional(c);
      return;
    }
    setAvisoProvisional(null);
    if (onSelectTicker(c.emisora)) irA("resumen");
  }

  return (
    <>
      <ChartCard
        title={`Capturas de mercado · sesión ${mercado?.fecha || "—"}`}
        subtitle={esIpc35
          ? "Vista ampliada con 35 componentes provisionales (NAFTRAC 2026-11-17). Los huecos no se imputan y las señales siguen bloqueadas."
          : "Los PPP marcados como verificados proceden de la fuente registrada. Los valores de contingencia no se muestran."}
        explicar={() => explicarMonitor({ fecha: mercado?.fecha, cotizaciones: cot })}
        tour="monitor"
      >
        <div className="tm-filters" style={{ padding: "4px 6px 14px", flexWrap: "wrap", gap: 8 }}>
          {setUniversoMercado && (
            <div role="group" aria-label="Universo de mercado" style={{ display: "inline-flex", gap: 6 }}>
              <button
                type="button"
                className={`bk-btn bk-btn-sm ${!esIpc35 ? "bk-btn-primary" : "bk-btn-outline"}`}
                aria-pressed={!esIpc35}
                onClick={() => cambiarUniverso("base_15")}
              >
                Panel base (15)
              </button>
              <button
                type="button"
                className={`bk-btn bk-btn-sm ${esIpc35 ? "bk-btn-primary" : "bk-btn-outline"}`}
                aria-pressed={esIpc35}
                onClick={() => cambiarUniverso("ipc35_provisional")}
              >
                IPC provisional (35)
              </button>
            </div>
          )}
          <label className="tm-search">
            <Search size={16} />
            <input type="search" placeholder="Buscar emisora, serie o sector" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Buscar emisora o sector" />
          </label>
          <select value={sector} onChange={(e) => setSector(e.target.value)} aria-label="Filtrar por sector">
            {sectores.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          {esIpc35 && (
            <select value={filtroOrigen} onChange={(e) => setFiltroOrigen(e.target.value)} aria-label="Filtrar cobertura provisional">
              <option value="todos">Todos ({cot.length})</option>
              <option value="base_15">Base ({mercado?.kpis?.total_base_15 ?? 15})</option>
              <option value="candidato_20">Candidatos provisionales ({mercado?.kpis?.total_candidatos_20 ?? 20})</option>
              <option value="con_ppp">Solo con PPP observado</option>
              <option value="huecos">Solo huecos / sin dato</option>
            </select>
          )}
        </div>
        {esIpc35 && catalogoIpc && (
          <div className="bk-alert bk-alert-info" role="status" style={{ margin: "0 6px 14px", fontSize: 13, lineHeight: 1.5 }}>
            <div>
              <strong>Catálogo provisional ({catalogoIpc.version} · {catalogoIpc.estado_composicion}):</strong>{" "}
              Base 15 con PPP verificado: <strong>{mercado?.kpis?.total_verificadas ?? 0}</strong> ·
              Candidatos 20 con PPP observado en Bronze: <strong>{mercado?.kpis?.total_provisionales_con_ppp ?? 0}</strong> ·
              Huecos sin dato: <strong>{mercado?.kpis?.total_ausentes ?? 0}</strong> ·
              Señales: <strong>bloqueadas</strong>.
            </div>
            <div style={{ marginTop: 4 }}>
              {catalogoIpc.bronze_disponible
                ? `Boletín Bronze leído (SHA-256 ${catalogoIpc.sha256_bronze?.slice(0, 12)}…). `
                : "Sin boletín Bronze en esta sesión (ej. fechas con contingencia o previas a 2026-10-20): los 20 candidatos quedan sin precio. Selecciona una sesión con boletín Bronze (2026-10-20 a 2026-11-17) para consultar observaciones PPP provisionales. "}
              Alias pendientes de evidencia oficial: {(catalogoIpc.alias_pendientes || []).join(", ")}.
            </div>
          </div>
        )}
        {avisoProvisional && (
          <div className="bk-alert bk-alert-info" role="status" style={{ margin: "0 6px 14px", fontSize: 13 }}>
            <strong>{avisoProvisional.emisora} {avisoProvisional.serie}</strong> (alias BlackRock: <code>{avisoProvisional.alias_blackrock || "—"}</code>) es un componente provisional de solo lectura en Mercado. No habilita series históricas, estadística ni señales hasta validar composición oficial, alias e historial.
          </div>
        )}
        <div className="tm-table-wrap">
          <table className="tm-table">
            <thead>
              <tr>
                <th>Emisora</th>
                <th>Sector</th>
                <th className="num">PPP oficial</th>
                <th className="num">Anterior</th>
                <th className="num">Variación</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map((c) => {
                const ok = c.ppp_bmv_mxn != null;
                const esCandidato = c.origen_catalogo === "CANDIDATO_20";
                return (
                  <tr
                    key={`${c.emisora}-${c.serie}`}
                    className={`is-clickable ${!esCandidato && c.emisora === emisora ? "is-selected" : ""}`}
                    data-tour={c.emisora === "WALMEX" ? "emisora-walmex" : undefined}
                    onClick={() => abrirFila(c)}
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        abrirFila(c);
                      }
                    }}
                  >
                    <td>
                      <span className="tm-table-ticker">
                        <span className="tm-ticker-badge">{c.emisora.slice(0, 4)}</span>
                        <span>
                          <strong style={{ color: "var(--bk-navy)" }}>{c.emisora}</strong>{" "}
                          <span className="bk-muted" style={{ fontSize: 12 }}>{c.serie}</span>
                          {esCandidato
                            ? <span className="bk-chip bk-chip-warn" style={{ marginLeft: 6, padding: "1px 7px", fontSize: 10.5 }}>Provisional · Sin señales</span>
                            : !puedeVer(c.emisora) && <span className="bk-chip bk-chip-navy" style={{ marginLeft: 6, padding: "1px 7px", fontSize: 10.5 }}>Pro</span>}
                        </span>
                      </span>
                    </td>
                    <td className="bk-muted">{c.sector}</td>
                    <td className="num"><strong>{ok ? formatMoney(c.ppp_bmv_mxn) : "—"}</strong></td>
                    <td className="num bk-muted">{c.anterior_bmv_mxn != null ? formatMoney(c.anterior_bmv_mxn) : "—"}</td>
                    <td className={`num ${c.variacion_pct > 0 ? "bk-up" : c.variacion_pct < 0 ? "bk-down" : ""}`}>
                      <strong>{c.variacion_pct != null ? formatPct(c.variacion_pct) : "—"}</strong>
                    </td>
                    <td><Badge status={c.estado_captura} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!filtradas.length && <Estado loading={datos.mercado.loading} titulo={datos.mercado.error ? "Mercado no disponible" : "Sin coincidencias"}
            texto={datos.mercado.error?.message || "Prueba con otro texto o sector."} />}
        </div>
        {mercado?.fuente && <p className="bk-muted" style={{ fontSize: 12 }}>
          Fuente: {mercado.fuente.tipo === "silver_diario_s3" ? "Silver diario" : "instantánea reciente"} ·
          actualización: {mercado.fuente.actualizada || "no disponible"} · {mercado.fuente.cobertura}
          {catalogoIpc?.sha256_bronze ? ` · Bronze SHA-256: ${catalogoIpc.sha256_bronze.slice(0, 12)}…` : ""}
        </p>}
      </ChartCard>

      <div className="tm-row">
        <ChartCard
          title="Variación media por sector"
          subtitle="Verde: subió · rojo: bajó"
          explicar={datos.sectores.data ? () => explicarSectores(datos.sectores.data) : null}
        >
          {datos.sectores.data?.sectores?.some((s) => s.variacion_media_pct != null)
            ? <SectoresChart sectores={datos.sectores.data.sectores} />
            : <Estado loading={datos.sectores.loading} titulo="Variaciones por sector no disponibles"
                texto={datos.sectores.error?.message || "La fuente disponible no contiene variaciones verificadas para este corte."} />}
        </ChartCard>
        <section className="bk-card bk-card-pad" data-tour="sello" style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap", alignSelf: "start" }}>
          <span className="tm-list-icon" style={{ background: "var(--bk-teal-50)", color: "var(--bk-teal-600)", width: 48, height: 48 }}>
            <ShieldCheck size={24} />
          </span>
          <div style={{ flex: 1, minWidth: 200 }}>
            <strong style={{ color: "var(--bk-navy)" }}>Huella de la fuente</strong>
            <p className="bk-mono" style={{ margin: "4px 0 0", fontSize: 12, wordBreak: "break-all" }}>{sha || "Huella no disponible para esta sesión"}</p>
          </div>
          <button
            type="button"
            className="bk-btn bk-btn-outline bk-btn-sm"
            onClick={() =>
              onShowEvidence({
                ticker: emisora,
                serie: actual?.serie || "*",
                ppp: actual?.ppp_bmv_mxn,
                sha256: sha,
                url: mercado?.kpis?.url_fuente,
              })
            }
          >
            Ver evidencia
          </button>
        </section>
      </div>
    </>
  );
}

/* ============================================================================
   SEÑALES
   ============================================================================ */
export function Senales({ ctx }) {
  const { emisora, datos, permitido, onPlanGate, irA, onOpenReport } = ctx;
  if (!permitido) return <Bloqueado emisora={emisora} onPlanGate={onPlanGate} />;
  const senal = datos.senal.data;
  if (!senal) return (
    <>
      <div className="bk-card"><Estado loading={datos.senal.loading} titulo="Sin señal" texto={datos.senal.error?.message} /></div>
      <CostosInversion key={emisora} emisora={emisora} />
    </>
  );
  const g2 = senal.modelos.filter((m) => m.generacion === "G2");
  const arriba = g2.filter((m) => m.probabilidad >= 0.5).length;
  const factor = senal.factor;
  const metricas = datos.metricas.data;
  const historicosSinSenal = modelosHistoricosSinSenal(metricas, senal.modelos);
  const kelly =
    metricas?.asignacion_capital_fase5?.ultimos_pesos_sugeridos_pct?.[emisora] ??
    metricas?.politica_asignacion_capital?.pesos_sugeridos_Recientes?.[emisora];

  return (
    <>
      {senal.aviso_evaluacion && (
        <div className="bk-alert bk-alert-info" role="status" style={{ fontSize: 13 }}>
          <strong>Evaluación histórica Gold:</strong> {senal.aviso_evaluacion}
        </div>
      )}
      <div className="tm-kpis">
        <div className="bk-card tm-kpi">
          <span className="tm-kpi-icon"><BrainCircuit size={18} /></span>
          <small>Consenso G2</small>
          <div style={{ marginTop: 4 }}>{consensoChip(senal.consensos?.G2)}</div>
          <span>{arriba} de {g2.length} modelos sobre 50 % · {textoConsenso(senal.consensos?.G2)}</span>
        </div>
        <Kpi label="PPP base (t)" value={formatMoney(factor?.ppp_base)} sub={`Señal del ${senal.fecha}`} icon={Wallet} />
        <Kpi
          label="Retorno relativo al panel"
          value={factor?.ret_rel_pp != null ? `${factor.ret_rel_pp >= 0 ? "+" : ""}${factor.ret_rel_pp.toFixed(2)} pp` : "—"}
          sub={factor?.z_rel != null ? `${factor.z_rel >= 0 ? "+" : ""}${factor.z_rel.toFixed(2)} σ frente a su historia` : "10 sesiones vs. media del panel"}
          icon={Gauge}
          tone={tonoDe(factor?.ret_rel_pp)}
        />
        <Kpi
          label="Peso ¼-Kelly sugerido"
          value={kelly != null ? `${Number(kelly).toFixed(2)}%` : "0.00%"}
          sub="Política de asignación (métricas institucionales)"
          icon={Database}
        />
      </div>

      <div className="tm-row tm-row-half">
        <ChartCard
          title="Probabilidad de subida por modelo"
          subtitle={`${emisora} · señal ${senal.fecha} · horizonte de 5 sesiones`}
          explicar={() => explicarProbabilidades({ emisora, ...senal, modelos: senal.modelos.map((m) => ({ ...m, nombre: nombreModelo(m.modelo, m.nombre) })) })}
          tour="modelos"
        >
          <ProbabilidadesChart modelos={senal.modelos} />
          <div className="tm-list">
            {senal.modelos.map((m) => <div className="tm-list-item" key={`${m.generacion}-${m.modelo}`}>
              <span className="tm-list-main"><strong>{nombreModelo(m.modelo, m.nombre)}</strong>
                <span>{m.modelo} · {m.valida ? "Señal registrada" : "Señal anulada"}</span></span>
            </div>)}
          </div>
        </ChartCard>
        <ChartCard
          title="¿Qué empuja la probabilidad?"
          subtitle={factor?.contribuciones && Object.keys(factor.contribuciones).length ? `Descomposición de ${nombreModelo(factor.modelo, factor.nombre)}` : "Factor clave: retorno relativo al panel"}
          explicar={() => explicarFactor({ emisora, factor })}
          tour="factor"
          foot={factor?.lectura ? <span>{factor.lectura}</span> : null}
        >
          {factor?.contribuciones && Object.keys(factor.contribuciones).length ? (
            <ContribucionesChart contribuciones={factor.contribuciones} />
          ) : (
            <Estado titulo="Sin descomposición" texto={factor?.lectura || "No hay señal G2 para esta fecha."} />
          )}
        </ChartCard>
      </div>

      {historicosSinSenal.length > 0 && <section className="bk-card bk-card-pad">
        <details>
          <summary><strong>Modelos con evaluación histórica sin señal registrada ({historicosSinSenal.length})</strong></summary>
          <p className="bk-muted" style={{ fontSize: 12 }}>Comparación por identificador técnico exacto para {emisora}, señal del {senal.fecha || "—"}. Las variantes históricas no se consideran equivalentes a otras versiones por tener un nombre parecido.</p>
          <div className="tm-list">
            {historicosSinSenal.map((m) => <div className="tm-list-item" key={m.id_modelo}>
              <span className="tm-list-main"><strong>{nombreModelo(m.id_modelo, m.nombre)}</strong>
                <span>{m.id_modelo} · {estadoModeloHistorico(m.id_modelo, m.rol).join(" · ")}</span></span>
              <span className="bk-chip bk-chip-navy">Sin señal disponible</span>
            </div>)}
          </div>
        </details>
      </section>}

      <CostosInversion key={emisora} emisora={emisora} />

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }} data-tour="acciones">
        <button type="button" className="bk-btn bk-btn-navy" onClick={() => irA("seguimiento")}>
          <Timer size={16} /> Ver seguimiento t+1 a t+5
        </button>
        <button type="button" className="bk-btn bk-btn-outline" onClick={onOpenReport}>
          <FileText size={16} /> Ficha ejecutiva
        </button>
      </div>
    </>
  );
}

/* ============================================================================
   SEGUIMIENTO
   ============================================================================ */
export function Seguimiento({ ctx }) {
  const { emisora, datos, permitido, onPlanGate, setFechaSenal } = ctx;
  if (!permitido) return <Bloqueado emisora={emisora} onPlanGate={onPlanGate} />;
  const seg = datos.seguimiento.data;
  const marc = datos.marcador.data;
  const r = seg?.resumen;

  return (
    <>
      {!seg || !r ? (
        <div className="bk-card"><Estado loading={datos.seguimiento.loading} titulo="Seguimiento no disponible" texto={datos.seguimiento.error?.message || "No hay información disponible para este corte."} /></div>
      ) : (
        <>
          {seg.aviso_evaluacion && (
            <div className="bk-alert bk-alert-info" role="status" style={{ fontSize: 13 }}>
              <strong>Evaluación histórica Gold:</strong> {seg.aviso_evaluacion}
            </div>
          )}
          <div className="tm-kpis">
            <div className="bk-card tm-kpi">
              <span className="tm-kpi-icon"><Timer size={18} /></span>
              <small>Señal</small>
              <select
                className="bk-select"
                style={{ paddingLeft: 12, minHeight: 38, fontWeight: 800, color: "var(--bk-navy)" }}
                value={seg.fecha_senal}
                onChange={(e) => setFechaSenal(e.target.value)}
                aria-label="Fecha de la señal"
              >
                {seg.fechas.map((f) => (
                  <option key={f} value={f}>Emitida el {f}</option>
                ))}
              </select>
              <span>Objetivo t+5: {r.fecha_objetivo}</span>
            </div>
            <Kpi label="PPP base t0" value={formatMoney(r.ppp_base)} sub={`Estado: ${r.estado.replaceAll("_", " ").toLowerCase()}`} icon={Wallet} />
            <Kpi
              label="Retorno acumulado"
              value={formatPct(r.retorno_parcial_pct)}
              sub={/^\d{4}-\d{2}-\d{2}$/.test(r.fecha_parcial) ? `al ${r.fecha_parcial}` : "sin sesiones posteriores aún"}
              icon={TrendingUp}
              tone={tonoDe(r.retorno_parcial_pct)}
            />
            <Kpi label="Modelos acertando" value={r.modelos_con_precio ? `${r.modelos_acertando} de ${r.modelos_con_precio}` : "—"} sub="Con el último PPP disponible" icon={Gauge} />
          </div>

          <div className="bk-card">
            <div className="tm-chart-head">
              <div>
                <h3>Línea de tiempo de la señal</h3>
                <p>Cada casilla es una sesión hábil de la BMV</p>
              </div>
            </div>
            <div className="tm-timeline">
              {seg.trayectoria.map((t) => (
                <div
                  key={t.paso}
                  className={`tm-tl-step ${t.estado === "OBSERVADO" ? "is-obs" : t.estado === "HUECO_DOCUMENTADO" ? "is-gap" : "is-future"}`}
                >
                  <small>{t.paso} · {t.fecha}</small>
                  <strong className="bk-mono">{t.ppp != null ? formatMoney(t.ppp) : t.estado === "FUTURO" ? "Pendiente" : "Sin PPP"}</strong>
                  <span className={t.retorno_pct > 0 ? "bk-up" : t.retorno_pct < 0 ? "bk-down" : "bk-muted"}>
                    {t.paso === "t0" ? "Base" : t.retorno_pct != null ? formatPct(t.retorno_pct) : t.estado === "FUTURO" ? "por venir" : "no se rellena"}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="tm-row tm-row-main">
            <ChartCard
              title="Trayectoria del PPP desde t0"
              subtitle="Retorno contra el PPP base; las sesiones sin PPP no se interpolan"
              explicar={() => explicarTrayectoria({ emisora, ...seg })}
              tour="trayectoria"
            >
              <TrayectoriaChart trayectoria={seg.trayectoria} emisora={emisora} />
            </ChartCard>
            <ChartCard title="¿Cómo va cada modelo?" subtitle="Dirección pronosticada contra el PPP más reciente">
              <div className="tm-list" style={{ margin: "0 -14px" }}>
                {seg.modelos.map((m) => {
                  let chip = <span className="bk-chip bk-chip-navy">Sin precio aún</span>;
                  if (m.resuelta_t5) chip = m.acierto_t5 ? <span className="bk-chip bk-chip-up">Acertó en t+5</span> : <span className="bk-chip bk-chip-down">Falló en t+5</span>;
                  else if (m.acierto_parcial === true) chip = <span className="bk-chip bk-chip-up">Va acertando</span>;
                  else if (m.acierto_parcial === false) chip = <span className="bk-chip bk-chip-down">Va fallando</span>;
                  return (
                    <div key={m.modelo} className="tm-list-item">
                      <span className="tm-list-main">
                        <strong>{nombreModelo(m.modelo, m.nombre)}</strong>
                        <span>{m.modelo} · Señal registrada · P(subida) {prob(m.probabilidad)} → {m.prediccion === "SUBIDA" ? "subida" : "no subida"}</span>
                      </span>
                      {chip}
                    </div>
                  );
                })}
              </div>
            </ChartCard>
          </div>
        </>
      )}

      <ChartCard
        title="Marcador por modelo"
        subtitle={marc ? `Seguimiento prospectivo de señales registradas de las emisoras de tu plan · corte ${marc.fecha_corte}; separado del TEST histórico` : "Seguimiento prospectivo · aciertos parciales y en t+5"}
        explicar={marc?.modelos?.length ? () => explicarMarcador({ ...marc, modelos: marc.modelos.map((m) => ({ ...m, nombre: nombreModelo(m.id_modelo, m.nombre) })) }) : null}
        tour="marcador"
        foot={<span>Con pocas señales resueltas la tasa es inestable: la métrica que cuenta es la resolución en t+5 y su Brier score (menor es mejor).</span>}
      >
        {marc?.modelos?.length ? (
          <div className="tm-row tm-row-half" style={{ alignItems: "start" }}>
            <MarcadorChart modelos={marc.modelos} />
            <div className="tm-table-wrap">
              <table className="tm-table">
                <thead>
                  <tr>
                    <th>Modelo</th>
                    <th className="num">Parcial</th>
                    <th className="num">t+5</th>
                    <th className="num">Brier</th>
                  </tr>
                </thead>
                <tbody>
                  {marc.modelos.map((m) => (
                    <tr key={m.modelo}>
                      <td><strong style={{ color: "var(--bk-navy)" }}>{nombreModelo(m.id_modelo, m.nombre)}</strong><br /><small>{m.id_modelo || m.modelo} · Seguimiento de señales registradas</small></td>
                      <td className="num">{m.tasa_parcial_pct?.toFixed(1)}% <span className="bk-muted">({m.aciertos_parciales}/{m.en_seguimiento})</span></td>
                      <td className="num">{m.aciertos_t5}/{m.resueltas_t5}</td>
                      <td className="num">{m.brier_t5 != null ? m.brier_t5.toFixed(4) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <Estado loading={datos.marcador.loading} titulo="Marcador no disponible" texto={datos.marcador.error?.message} />
        )}
      </ChartCard>
    </>
  );
}

/* ============================================================================
   CALIDAD (métricas institucionales del modelo campeón)
   ============================================================================ */
function binsDe(m) {
  const raw =
    m?.curvas_calibracion_reliability?.G2_V4_ADJ ||
    m?.modelos_test_15_emisoras?.G2_V4_ADJ?.reliability_bins ||
    [];
  return raw.map((b) => ({ prob_media: b.prob_media ?? b.p_media, frecuencia_observada: b.frecuencia_observada ?? b.y_obs_media, n: b.n ?? null }))
    .filter((b) => Number.isFinite(b.prob_media) && Number.isFinite(b.frecuencia_observada));
}

function filasDe(m) {
  if (Array.isArray(m?.modelos_test)) {
    return m.modelos_test.map((it) => ({ label: nombreModelo(it.id_modelo, it.nombre), accuracy_pct: it.exactitud_15_pct, bss_pct: it.bss_vs_climatologia_15_pct ?? 0, ece: it.ece_15 ?? 0 }));
  }
  return [];
}

export function Calidad({ ctx }) {
  const { emisora, datos, senalesTicker, irA, onOpenReport } = ctx;
  const m = datos.metricas.data;
  const goldEval = import.meta.env.VITE_GOLD_EVALUACION === "true";
  if (import.meta.env.VITE_REQUIRE_REAL_API === "true" && !goldEval) {
    return <Estado titulo="Auditoría no disponible" texto="Esta sección está temporalmente deshabilitada mientras se verifica la procedencia de todas sus métricas." />;
  }
  if (!m) {
    return <div className="bk-card"><Estado loading={datos.metricas.loading} titulo="Métricas no disponibles" texto={datos.metricas.error?.message || "Cargando métricas institucionales desde S3."} /></div>;
  }
  const bins = binsDe(m);
  const campeon = nombreModelo(m?.decision_arquitectura?.campeon_oficial || "G2_V4_ADJ");
  return (
    <>
      {m.aviso_evaluacion && (
        <div className="bk-alert bk-alert-info" role="status" style={{ fontSize: 13 }}>
          <strong>Evaluación histórica Gold:</strong> {m.aviso_evaluacion}
        </div>
      )}
      <div className="tm-row tm-row-main">
        <ChartCard
          title={`Calibración del modelo campeón (${campeon})`}
          subtitle="Si dice 55 %, ¿sube el 55 % de las veces? Ideal: sobre la diagonal. El tamaño del punto indica cuántas observaciones tiene."
          explicar={() => explicarCalibracion({ etiqueta: campeon, bins, filas: filasDe(m) })}
          tour="calidad"
        >
          <CalibracionChart bins={bins} etiqueta={campeon} />
        </ChartCard>
        <div className="bk-card bk-card-pad" style={{ display: "grid", gap: 10, alignContent: "start" }}>
          <span className="bk-eyebrow" style={{ marginBottom: 0 }}>Decisión de arquitectura</span>
          <strong style={{ color: "var(--bk-navy)", fontSize: 18 }}>Campeón: {campeon}</strong>
          {m?.decision_arquitectura?.subcampeon_shadow_operativo && (
            <span className="bk-chip bk-chip-navy" style={{ justifySelf: "start" }}>En observación: {nombreModelo(m.decision_arquitectura.subcampeon_shadow_operativo)}</span>
          )}
          <p style={{ margin: 0, fontSize: 13.5 }}>{describirModelos(m?.decision_arquitectura?.justificacion) || "Métricas institucionales fuera de muestra del panel de 15 emisoras."}</p>
          <p className="bk-muted" style={{ margin: 0, fontSize: 12 }}>Congelamiento oficial: {m?.fecha_congelamiento_oficial || "—"}</p>
        </div>
      </div>
      <div className="bk-card bk-card-pad tm-calidad">
        <ComparisonAudit
          ocultarCalibracion
          ticker={emisora}
          senales={senalesTicker}
          metricas={m}
          onBack={() => irA("senales")}
          onOpenReport={onOpenReport}
        />
      </div>
    </>
  );
}

/* ============================================================================
   GOBERNANZA
   ============================================================================ */
export function Gobernanza({ ctx }) {
  const { datos } = ctx;
  const g = datos.gobernanza.data;
  const op = g?.estado_operativo || null;
  const v = op?.ventana_limpia || {};
  const integ = op?.integridad || {};
  const comp = op?.compuertas || {};
  const piezas = op
    ? [
        [
          Timer,
          "EventBridge Scheduler",
          `${op.scheduler?.estado || "ENABLED"} · 16:45 CDMX`,
          `${op.scheduler?.nombre || "DisparadorDiarioBMV"} (${op.scheduler?.expresion || "cron(45 16 ? * MON-FRI *)"})`,
        ],
        [
          ShieldCheck,
          "Ventana limpia BMV",
          v.sesiones_consecutivas != null ? `${v.sesiones_consecutivas}/${v.meta || 21} sesiones` : "En seguimiento",
          `Última captura: ${v.ultima_fecha_capturada || "—"} · Faltan ${v.faltan ?? "—"} para cerrar compuerta.`,
        ],
        [
          Database,
          "Integridad S3 (SHA-256)",
          `${integ.capturas_seguras_totales ?? "—"} capturas · ${integ.cortes_ipc35_provisionales ?? "—"} cortes IPC-35`,
          integ.sha256_bronze
            ? `Bronze SHA-256: ${integ.sha256_bronze.slice(0, 16)}… · Cero imputación.`
            : "Manifiestos inmutables IfNoneMatch='*'.",
        ],
        [
          Cloud,
          "Compuertas e Identidad",
          `Señales: ${comp.emision_senales || "NO_HABILITADA"}`,
          `Yahoo: ${comp.yahoo_observaciones?.estado_permiso || "—"} (${comp.yahoo_observaciones?.habilitada_api ? "API activa" : "inactiva"}) · ${op.identidad || "Cognito + DynamoDB"}.`,
        ],
      ]
    : [
        [Timer, "EventBridge", "16:45 CDMX", "Dispara la ingesta de lunes a viernes tras el cierre."],
        [BrainCircuit, "AWS Lambda", "recolector-seguro", "Descarga el boletín BMV con validación estricta y escribe en S3."],
        [Database, "Amazon S3", "Bronze · Silver · Evidencias", "Almacenamiento versionado e inmutable con verificación SHA-256."],
        [Cloud, "Identidad AWS", "Cognito + DynamoDB", "Control de acceso y roles verificados en servidor."],
      ];
  return (
    <>
      <ChartCard
        title="Flujo de datos y gobernanza en AWS"
        subtitle="Estado vivo del lakehouse S3, compuertas operativas y trazabilidad SHA-256"
        explicar={g ? () => explicarGobernanza(g) : null}
        tour="gobernanza"
      >
        {g ? <GobernanzaSankey nodos={g.nodos} enlaces={g.enlaces} /> : <Estado loading={datos.gobernanza.loading} titulo={datos.gobernanza.error ? "Gobernanza no disponible" : "Cargando gobernanza"} texto={datos.gobernanza.error?.message} />}
      </ChartCard>
      <div className="tm-kpis">
        {piezas.map(([Icon, titulo, valor, texto]) => (
          <div key={titulo} className="bk-card tm-kpi">
            <span className="tm-kpi-icon"><Icon size={18} /></span>
            <small>{titulo}</small>
            <strong style={{ fontSize: 16 }}>{valor}</strong>
            <span>{texto}</span>
          </div>
        ))}
      </div>
      {op && (
        <section className="bk-card bk-card-pad" style={{ display: "grid", gap: 10 }}>
          <strong style={{ color: "var(--bk-navy)" }}>Estado detallado de compuertas operativas</strong>
          <div className="estadistica-lista" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
            <div><span>Emisión de señales G2</span><strong>{comp.emision_senales || "NO_HABILITADA"}</strong></div>
            <div><span>Observación secundaria Yahoo</span><strong>{comp.yahoo_observaciones?.estado_permiso || "—"} · {comp.yahoo_observaciones?.habilitada_api ? "Activa (separada)" : "Bloqueada"}</strong></div>
            <div><span>Catálogo IPC-35</span><strong>{comp.ipc_35?.estado_composicion || "PROVISIONAL_NO_OFICIAL"} ({comp.ipc_35?.componentes || 35})</strong></div>
            <div><span>Calendario BMV 2027</span><strong>{comp.calendario_bmv_2027?.estado || "PENDIENTE_FUENTE_OFICIAL"}</strong></div>
          </div>
          {integ.sha256_bronze && (
            <p className="bk-mono bk-muted" style={{ margin: 0, fontSize: 12, overflowWrap: "anywhere" }}>
              Último boletín Bronze ({v.ultima_fecha_capturada || "—"}) · SHA-256: {integ.sha256_bronze}
            </p>
          )}
        </section>
      )}
    </>
  );
}
