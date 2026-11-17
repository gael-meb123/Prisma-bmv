import { useEffect, useState } from "react";
import { api } from "../services/api.mjs";

/**
 * Carga lo que necesita la terminal. Cada bloque se pide por separado para que una
 * gráfica lenta o bloqueada por plan no detenga al resto.
 *  - estado de cada bloque: { data, loading, error }  (error.status 403 = fuera del plan)
 */
function useRecurso(cargar, deps, activo = true) {
  const [estado, setEstado] = useState({ data: null, loading: activo, error: null });
  useEffect(() => {
    if (!activo) {
      setEstado({ data: null, loading: false, error: null });
      return undefined;
    }
    const ctrl = new AbortController();
    setEstado((s) => ({ data: s.data, loading: true, error: null }));
    cargar(ctrl.signal)
      .then((data) => !ctrl.signal.aborted && setEstado({ data, loading: false, error: null }))
      .catch((error) => !ctrl.signal.aborted && setEstado({ data: null, loading: false, error }));
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, activo]);
  return estado;
}

export function useTerminalData({ emisora, fecha, fechaSenal, permitido, conSesion }) {
  const fechas = useRecurso((s) => api.getFechas(s), []);
  const mercado = useRecurso((s) => api.getMercado(fecha, s), [fecha]);
  const sectores = useRecurso((s) => api.terminal.sectores(fecha, s), [fecha]);
  const gobernanza = useRecurso((s) => api.terminal.gobernanza(s), []);
  const metricas = useRecurso((s) => api.getMetricasModelos(s), []);
  const serie = useRecurso((s) => api.terminal.serie(emisora, s), [emisora], permitido && conSesion);
  const senal = useRecurso((s) => api.terminal.senal(emisora, fecha, s), [emisora, fecha], permitido && conSesion);
  const seguimiento = useRecurso((s) => api.terminal.seguimiento(emisora, fechaSenal, s), [emisora, fechaSenal], permitido && conSesion);
  const marcador = useRecurso((s) => api.terminal.marcador(s), [], conSesion);
  return { fechas, mercado, sectores, gobernanza, metricas, serie, senal, seguimiento, marcador };
}
