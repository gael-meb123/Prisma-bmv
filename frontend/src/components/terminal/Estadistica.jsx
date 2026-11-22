import React, { useEffect, useState } from "react";
import { BarChart3, CalendarDays, Database, TrendingUp } from "lucide-react";
import { api } from "../../services/api.mjs";
import { ChartCard, Estado, ExplainButton } from "./ChartCard";
import { explicarEstadistica } from "../../guide/explicaciones.mjs";
import { CajaEstadistica, HistogramaEstadistico } from "./charts";
import "./estadistica.css";
import { ObservacionSecundaria } from "./ObservacionSecundaria";

const etiquetas = {
  ppp_bmv_mxn: "PPP (MXN)", variacion_ppp_vs_anterior_pct: "Variación PPP (%)",
  ret_1_adj: "Rendimiento 1 sesión", ret_5_adj: "Rendimiento 5 sesiones",
  ret_10_adj: "Rendimiento 10 sesiones", ret_20_adj: "Rendimiento 20 sesiones",
  volatilidad_5_adj: "Volatilidad 5 sesiones", volatilidad_20_adj: "Volatilidad 20 sesiones",
  distancia_media_5_adj: "Distancia a media 5", distancia_media_20_adj: "Distancia a media 20",
};
const numero = (v, d = 3) => v == null || !Number.isFinite(v) ? "—" : v.toLocaleString("es-MX", { maximumFractionDigits: d });
const nombre = (v) => etiquetas[v] || v;
const CANDIDATOS_IPC35 = [
  "VOLAR", "KOF", "GCARSO", "ALPEK", "LAB", "OMA", "GENTERA", "MEGA", "ALSEA", "ORBIA",
  "CHDRAUI", "Q", "BOLSA", "KIMBER", "BBAJIO", "LACOMER", "R", "GCC", "SIGMAF", "PINFRA",
];
const estadoNombre = (s) => ({
  PPP_PUBLICADO_VERIFICADO: "PPP verificado",
  PPP_OBSERVADO_MAPEO_PROVISIONAL: "PPP observado (provisional)",
  NO_PUBLICADO_EN_BOLETIN_RSS_DEL_DIA: "No publicado",
  NO_ENCONTRADO_EN_TABLAS_BOLETIN: "No publicado en tablas RSS",
  BOLETIN_NO_DISPONIBLE_HTTP: "Boletín no disponible",
  SIN_ESTADO: "Sin estado",
})[s] || s.replaceAll("_", " ").toLowerCase();

function Indicador({ label, value, sub, icon: Icon }) {
  return <div className="bk-card tm-kpi"><span className="tm-kpi-icon"><Icon size={18} /></span>
    <small>{label}</small><strong className="bk-mono">{value}</strong><span>{sub}</span></div>;
}

export function Estadistica({ ctx }) {
  const { emisora, permitido, onPlanGate, account } = ctx;
  const [universo, setUniverso] = useState("base_15");
  const [candidato, setCandidato] = useState("VOLAR");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [filtro, setFiltro] = useState({ desde: "", hasta: "" });
  const [metodo, setMetodo] = useState("pearson");
  const [estado, setEstado] = useState({ loading: true, data: null, error: "" });
  const esIpc35 = universo === "ipc35_provisional";
  const emisoraActiva = esIpc35 ? candidato : emisora;
  const permitidoActivo = esIpc35 ? true : permitido;
  const conSesion = Boolean(account.session);
  const usuarioId = account.user?.id;

  useEffect(() => {
    if (!permitidoActivo || !conSesion) {
      setEstado({ loading: false, data: null, error: "" });
      return undefined;
    }
    const ctrl = new AbortController();
    setEstado({ loading: true, data: null, error: "" });
    api.terminal.estadistica(emisoraActiva, filtro.desde, filtro.hasta, ctrl.signal, esIpc35 ? "ipc35_provisional" : null)
      .then((data) => {
        if (!ctrl.signal.aborted) setEstado({ loading: false, data, error: data ? "" : "No se pudo conectar con el servidor de estadísticas." });
      })
      .catch((error) => {
        if (!ctrl.signal.aborted) setEstado({
          loading: false,
          data: null,
          error: error.status === 404
            ? "La ruta de estadísticas no está disponible en el servidor. Reinicia el backend con la versión actual del proyecto."
            : error.message || "No se pudo cargar el análisis.",
        });
      });
    return () => ctrl.abort();
  }, [emisoraActiva, permitidoActivo, conSesion, usuarioId, filtro, esIpc35]);

  if (!permitidoActivo) return <div className="bk-card"><Estado locked titulo={`${emisora} no está incluida en tu plan`}>
    <button className="bk-btn bk-btn-primary" onClick={() => onPlanGate(emisora)}>Ver planes</button></Estado></div>;
  if (!account.session) return <div className="bk-card"><Estado titulo="Inicia sesión" texto="Necesitas una sesión para consultar este análisis." /></div>;

  const r = estado.data;
  const h = r?.cobertura_historico;
  const p = r?.cobertura_panel;
  const estadisticas = r ? [...r.estadisticas_historico_verificado, ...r.estadisticas_panel_verificado].filter((x) => x.agrupacion === "total") : [];
  const direcciones = r?.frecuencias_direccion.filter((x) => x.agrupacion === "total") || [];
  const variables = [...new Set((r?.correlaciones_panel || []).map((x) => x.variable_1))];
  const pares = new Map((r?.correlaciones_panel || []).map((x) => [`${x.variable_1}|${x.variable_2}`, x]));
  const valores = (r?.serie_historica_verificada || []).map((x) => x.variacion_ppp_vs_anterior_pct).filter((v) => v != null && Number.isFinite(v));
  const validacion = desde && hasta && desde > hasta;

  return <>
    <div data-tour="estadistica" className="bk-card bk-card-pad estadistica-filtros">
      <div><span className="bk-eyebrow">{esIpc35 ? "IPC PROVISIONAL (35)" : "DATOS HISTÓRICOS"} · {emisoraActiva}</span>
        <h3>Estadística descriptiva</h3><p>Explora la distribución, calidad y relaciones de los datos disponibles para esta emisora.</p></div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
        <div role="group" aria-label="Universo estadístico" style={{ display: "inline-flex", gap: 6 }}>
          <button type="button" className={`bk-btn bk-btn-sm ${!esIpc35 ? "bk-btn-primary" : "bk-btn-outline"}`} aria-pressed={!esIpc35} onClick={() => setUniverso("base_15")}>Panel base (15)</button>
          <button type="button" className={`bk-btn bk-btn-sm ${esIpc35 ? "bk-btn-primary" : "bk-btn-outline"}`} aria-pressed={esIpc35} onClick={() => setUniverso("ipc35_provisional")}>IPC provisional (35)</button>
        </div>
        {esIpc35 && (
          <label style={{ display: "inline-flex", gap: 6, alignItems: "center", fontSize: 13 }}>
            Candidato IPC-35
            <select aria-label="Candidato IPC-35" value={candidato} onChange={(e) => setCandidato(e.target.value)}>
              {CANDIDATOS_IPC35.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        )}
      </div>
      <form onSubmit={(e) => { e.preventDefault(); if (!validacion && (desde !== filtro.desde || hasta !== filtro.hasta || estado.error)) setFiltro({ desde, hasta }); }}>
        <label>Desde<input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
        <label>Hasta<input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
        <button type="submit" className="bk-btn bk-btn-primary">Aplicar periodo</button>
      </form>
      {validacion && <p role="alert" className="estadistica-error">La fecha inicial no puede ser posterior a la final.</p>}
        <p>El filtro de sesión superior no modifica este periodo. Las fuentes histórica y de indicadores tienen coberturas distintas.</p>
        {r?.metodologia?.advertencia && <p role="status">{r.metodologia.advertencia}</p>}
        {r?.metodologia?.intervalo_consultado && <p>Intervalo consultado: {r.metodologia.intervalo_consultado.desde} a {r.metodologia.intervalo_consultado.hasta}.
          Máximo 366 días por consulta; para otros periodos cambia las fechas.</p>}
      <p>El rendimiento a 20 sesiones describe el cambio histórico en ese intervalo; no es una predicción para las próximas 20 sesiones.</p>
      {r && <ExplainButton label="Prismi explica este análisis" explicar={() => explicarEstadistica({ emisora: emisoraActiva, reporte: r })} />}
    </div>
    {estado.loading && <div className="bk-card"><Estado loading titulo="Calculando estadísticas" /></div>}
    {!estado.loading && estado.error && <div className="bk-card"><Estado titulo="Análisis no disponible" texto={estado.error} /></div>}
    {r && <>
      <div className="tm-kpis">
        <Indicador label="Registros históricos" value={numero(h.registros, 0)} sub="Incluye todos los estados" icon={Database} />
        <Indicador label={esIpc35 ? "PPP observados (provisional)" : "PPP verificados"} value={numero((esIpc35 ? h.estados.PPP_OBSERVADO_MAPEO_PROVISIONAL : h.estados.PPP_PUBLICADO_VERIFICADO) || 0, 0)} sub={esIpc35 ? "Filas observadas en Bronze (sin señales)" : "Filas con estado verificado"} icon={BarChart3} />
        <Indicador label="Panel de indicadores" value={p ? numero(p.registros, 0) : "—"} sub={p ? "Registros antes de excluir estados" : "Panel no disponible"} icon={TrendingUp} />
        <Indicador label="Periodo histórico" value={h.fecha_inicial || "—"} sub={h.fecha_final ? `Hasta ${h.fecha_final}` : "Sin observaciones"} icon={CalendarDays} />
      </div>
      <div className="estadistica-grid">
        <ChartCard title="Calidad y cobertura" subtitle="Estados de captura de la serie histórica seleccionada" explicar={() => explicarEstadistica({ emisora, reporte: r, apartado: "calidad" })}>
          <div className="estadistica-lista">{Object.entries(h.estados).length ? Object.entries(h.estados).map(([s, n]) =>
            <div key={s}><span>{estadoNombre(s)}</span><strong>{numero(n, 0)}</strong></div>) : <p>Sin registros para este periodo.</p>}</div>
          <p className="estadistica-nota">Panel: {p ? `${p.fecha_inicial || "—"} a ${p.fecha_final || "—"}` : "no disponible"}.</p>
          <div className="estadistica-lista">{Object.entries(p?.estados || {}).map(([s, n]) =>
            <div key={s}><span>Panel · {estadoNombre(s)}</span><strong>{numero(n, 0)}</strong></div>)}</div>
          <p className="estadistica-nota">Los valores faltantes no se rellenan; solo se analizan filas con PPP verificado.</p>
        </ChartCard>
        <ChartCard title="Dirección de la variación" subtitle="Frecuencias sobre variaciones válidas y verificadas" explicar={() => explicarEstadistica({ emisora, reporte: r, apartado: "direccion" })}>
          <div className="estadistica-lista">{direcciones.map((d) => <div key={d.direccion}>
            <span>{{ alza: "Alza", baja: "Baja", sin_cambio: "Sin cambio" }[d.direccion]}</span>
            <strong>{numero(d.n, 0)} · {d.porcentaje == null ? "—" : `${numero(d.porcentaje, 1)}%`}</strong></div>)}</div>
        </ChartCard>
      </div>
      <ChartCard title="Medidas descriptivas" subtitle="PPP y variación histórica; indicadores del panel ajustado. Filas verificadas, sin imputación." explicar={() => explicarEstadistica({ emisora, reporte: r, apartado: "medidas" })}>
        <div className="estadistica-tabla"><table><thead><tr><th>Variable</th><th>N válido</th><th>Faltantes</th><th>Media</th><th>Mediana</th><th>Mínimo</th><th>Máximo</th><th>Desv. estándar</th><th>Q1</th><th>Q3</th><th>RIC</th><th>Asimetría</th><th>Exceso curtosis</th></tr></thead>
          <tbody>{estadisticas.map((x) => <tr key={x.variable}><th scope="row">{nombre(x.variable)}</th>
            {[x.n_valido, x.faltantes, x.media, x.mediana, x.minimo, x.maximo, x.desviacion_estandar_muestral, x.q1, x.q3, x.rango_intercuartilico, x.asimetria, x.exceso_curtosis].map((v, i) => <td key={i}>{numero(v)}</td>)}</tr>)}</tbody></table></div>
        <p className="estadistica-nota">Rendimientos, volatilidades y distancias del panel en escala decimal; variación histórica en porcentaje. Desviación muestral y exceso de curtosis de Fisher.</p>
      </ChartCard>
      <div className="estadistica-grid">
        <ChartCard title="Distribución de variaciones" subtitle={`Histograma · N = ${numero(valores.length, 0)}`} explicar={() => explicarEstadistica({ emisora, reporte: r, apartado: "histograma" })}>
          {valores.length ? <HistogramaEstadistico intervalos={r.distribucion_variacion_pct.histograma} /> : <Estado titulo="Sin datos válidos" />}
        </ChartCard>
        <ChartCard title="Dispersión de variaciones" subtitle="Diagrama de caja · valores extremos visibles" explicar={() => explicarEstadistica({ emisora, reporte: r, apartado: "caja" })}>
          {valores.length ? <CajaEstadistica valores={valores} /> : <Estado titulo="Sin datos válidos" />}
        </ChartCard>
      </div>
      <ChartCard title="Correlaciones exploratorias" subtitle="Pares completos en el periodo de cobertura del panel; pasa sobre cada valor para ver su N." explicar={() => explicarEstadistica({ emisora, reporte: r, apartado: "correlacion", metodo })}>
        <label className="estadistica-selector">Método <select value={metodo} onChange={(e) => setMetodo(e.target.value)}><option value="pearson">Pearson</option><option value="spearman">Spearman</option></select></label>
        <div className="estadistica-tabla"><table><thead><tr><th>Variable</th>{variables.map((v) => <th key={v}>{nombre(v)}</th>)}</tr></thead>
          <tbody>{variables.map((a) => <tr key={a}><th scope="row">{nombre(a)}</th>{variables.map((b) => {
            const par = pares.get(`${a}|${b}`);
            return <td key={b} title={`N de pares válidos: ${par?.n_pares ?? 0}`}>{numero(par?.[metodo])}</td>;
          })}</tr>)}</tbody></table></div>
        <p className="estadistica-nota">Las correlaciones son exploratorias y no implican causalidad. Las observaciones financieras pueden depender unas de otras.</p>
        <p className="estadistica-nota">Pearson mide asociación lineal y Spearman compara el orden de los valores. No son predicciones: cada celda relaciona dos variables históricas.</p>
      </ChartCard>
      <div className="bk-card bk-card-pad"><strong>Fuentes y limitaciones</strong>
        {r.metodologia?.procedencia_filas && <ul>{Object.entries(r.metodologia.procedencia_filas).map(([fuente, n]) =>
          <li key={fuente}>{fuente === "CAPTURA_HASH_VERIFICADO" ? "Captura con hash comprobado" : "Instantánea: estado declarado"}: {n} filas</li>)}</ul>}
        {r.metodologia?.sha256_instantanea && <details><summary>Huella de la instantánea consultada</summary>
          <code style={{ overflowWrap: "anywhere" }}>{r.metodologia.sha256_instantanea}</code>
          <p>{r.metodologia.alcance_verificacion}</p></details>}
        {r.metodologia?.ajustes_corporativos === "NO_VALIDADOS" && <p>Los ajustes corporativos aún no están validados. Estas medidas no habilitan predicciones.</p>}
        <p className="estadistica-nota">{r.metodologia?.advertencia || "Serie histórica de PPP y panel de variables ajustadas del proyecto. El estado de la fecha actual no garantiza la cobertura de toda la ventana de cada indicador."} Los periodos sin datos se muestran vacíos, no como cero.</p></div>
    </>}
    <ObservacionSecundaria
      emisora={emisoraActiva}
      universo={esIpc35 ? "ipc35_provisional" : null}
      habilitada={import.meta.env.VITE_YAHOO_OBSERVACIONES === "true"}
    />
  </>;
}
