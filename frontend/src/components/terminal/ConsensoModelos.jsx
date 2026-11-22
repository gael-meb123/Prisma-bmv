import React, { useEffect, useState } from "react";
import { ArrowRight, BrainCircuit, Info } from "lucide-react";
import { api } from "../../services/api.mjs";
import { ChartCard, Estado } from "./ChartCard";
import { nombreModelo } from "../../utils/presentation.mjs";
import "./consenso-modelos.css";

const estados = {
  subida: { titulo: "Coincidencia en subida", clase: "bk-chip-up" },
  no_subida: { titulo: "Coincidencia en no subida", clase: "bk-chip-down" },
  divergencia: { titulo: "Modelos en desacuerdo", clase: "bk-chip-warn" },
  incompleto: { titulo: "Cobertura incompleta", clase: "bk-chip-navy" },
  sin_datos: { titulo: "Sin señal en esta sesión", clase: "bk-chip-navy" },
};
const porcentaje = (p) => `${(p * 100).toFixed(1)} %`;

function explicarConsenso(datos) {
  const filas = datos.emisoras || [];
  const contar = (estado) => filas.filter((f) => f.estado === estado).length;
  return {
    titulo: "Consenso de modelos G2",
    texto: [
      `En la sesión ${datos.fecha_sesion}, el panel revisa las señales de las emisoras incluidas en tu plan para un horizonte de cinco sesiones. Compara cinco modelos G2 operativos, usando sus clases registradas.`,
      `En esta consulta hay ${contar("subida")} emisoras con coincidencia en subida, ${contar("no_subida")} en no subida y ${contar("divergencia")} con desacuerdo. Otras ${contar("incompleto")} tienen cobertura incompleta y ${contar("sin_datos")} no tienen señal en la sesión.`,
      "Se exige que estén los cinco modelos con la misma fecha objetivo. La probabilidad individual corresponde a cada modelo; no se suman ni convierten en una probabilidad de consenso.",
      "Coincidir no significa que el resultado sea seguro ni que la operación sea rentable. Los modelos pueden usar información similar y equivocarse al mismo tiempo. No hay una evaluación histórica del consenso en esta pantalla.",
    ].join("\n\n"),
    contexto: `Consenso G2, sesión ${datos.fecha_sesion}, horizonte cinco sesiones. ${contar("subida")} con coincidencia en subida, ${contar("no_subida")} en no subida, ${contar("divergencia")} con divergencia, ${contar("incompleto")} incompletas y ${contar("sin_datos")} sin señal. No es una recomendación.`,
    sugerencias: ["¿Qué significa que los modelos coincidan?", "¿Qué es una probabilidad de subida?", "¿Qué significa t+5?"],
    expresion: "thinking",
  };
}

export function ConsensoModelos({ ctx }) {
  const { account, fecha, irA, onSelectTicker } = ctx;
  const [estado, setEstado] = useState({ data: null, loading: true, error: "" });
  const conSesion = Boolean(account.session);
  const usuarioId = account.user?.id;
  const plan = account.role;

  useEffect(() => {
    if (!conSesion) {
      setEstado({ data: null, loading: false, error: "" });
      return undefined;
    }
    const ctrl = new AbortController();
    setEstado({ data: null, loading: true, error: "" });
    api.terminal.consenso(fecha, ctrl.signal)
      .then((data) => {
        if (!ctrl.signal.aborted) setEstado({ data, loading: false, error: data ? "" : "No se pudo conectar con el servidor." });
      })
      .catch((error) => {
        if (!ctrl.signal.aborted) setEstado({ data: null, loading: false, error: error.status === 404
          ? "La ruta de consenso no está disponible. Reinicia el backend con la versión actual."
          : error.message || "No se pudo cargar el consenso." });
      });
    return () => ctrl.abort();
  }, [fecha, conSesion, usuarioId, plan]);

  if (!conSesion) return <div className="bk-card"><Estado titulo="Inicia sesión" texto="Necesitas una sesión para consultar las señales de tu plan." /></div>;
  if (estado.loading) return <div className="bk-card"><Estado loading titulo="Cargando consenso" /></div>;
  if (estado.error) return <div className="bk-card"><Estado titulo="Consenso no disponible" texto={estado.error} /></div>;
  const datos = estado.data;
  if (!datos) return null;
  const orden = { subida: 0, no_subida: 1, divergencia: 2, incompleto: 3, sin_datos: 4 };
  const filas = [...datos.emisoras].sort((a, b) => orden[a.estado] - orden[b.estado] || a.emisora.localeCompare(b.emisora));

  return <>
    {datos.aviso_evaluacion && (
      <div className="bk-alert bk-alert-info" role="status" style={{ fontSize: 13 }}>
        <strong>Evaluación histórica Gold:</strong> {datos.aviso_evaluacion}
      </div>
    )}
    <section className="bk-card bk-card-pad consenso-intro">
      <div><span className="bk-eyebrow">SEÑALES G2 · {datos.fecha_sesion}</span>
        <h3>Coincidencia entre modelos</h3>
        <p>Consulta las emisoras de tu plan donde los cinco modelos G2 coinciden o discrepan sobre la dirección del PPP a cinco sesiones.</p></div>
      <div className="consenso-aviso"><Info size={18} /><span>La coincidencia no garantiza el resultado ni la rentabilidad. Los modelos pueden compartir información y equivocarse juntos. Esto no es una recomendación de inversión.</span></div>
      <p>Se utiliza exactamente la sesión seleccionada arriba. No se reemplazan señales ausentes por otras fechas. La evaluación histórica específica del consenso no está disponible en este módulo.</p>
      <details><summary>Modelos que participan en este consenso ({datos.modelos_esperados.length})</summary>
        <ul className="consenso-participantes">{datos.modelos_esperados.map((m) => <li key={m.id}>
          <strong>{nombreModelo(m.id, m.nombre)}</strong> · <code>{m.id}</code>
        </li>)}</ul>
        <p>Solo G2 V1–V5 registrados; no incluye G1, variantes de evaluación ni candidatos shadow.</p>
      </details>
    </section>
    <ChartCard title="Emisoras y señales" subtitle="Modelos G2 operativos · la probabilidad mostrada es de subida para cada modelo"
      tour="consenso"
      explicar={() => explicarConsenso(datos)}>
      <div className="consenso-lista">
        {filas.map((fila) => {
          const info = estados[fila.estado] || estados.incompleto;
          return <article className="consenso-item" key={fila.emisora}>
            <div className="consenso-item-head">
              <div><strong className="consenso-ticker">{fila.emisora}</strong>
                <span className={`bk-chip ${info.clase}`}>{info.titulo}</span></div>
              {fila.estado !== "sin_datos" && <button type="button" className="bk-btn bk-btn-ghost bk-btn-sm" onClick={() => {
                if (onSelectTicker(fila.emisora)) irA("senales");
              }}>Ver señales <ArrowRight size={14} /></button>}
            </div>
            <p className="consenso-meta">Señal: {fila.fecha_senal || "—"} · Objetivo t+5: {fila.fecha_objetivo || "—"} · Modelos con datos válidos: {fila.modelos_validos} de {fila.modelos_esperados}</p>
            {fila.razon_incompleto && <p className="consenso-meta">{fila.razon_incompleto}</p>}
            {fila.modelos.length > 0 && <div className="consenso-modelos">
              {fila.modelos.map((m, i) => <div className="consenso-modelo" key={`${m.id}-${i}`}>
                <span><BrainCircuit size={15} /> {nombreModelo(m.id, m.nombre)}</span>
                <strong>{porcentaje(m.probabilidad)}</strong>
                <small>{m.id} · Señal registrada · Clase: {m.clase === 1 ? "subida" : "no subida"}</small>
              </div>)}
            </div>}
          </article>;
        })}
        {!filas.length && <Estado titulo="Sin emisoras disponibles" texto="No hay emisoras habilitadas para tu plan." />}
      </div>
    </ChartCard>
  </>;
}
