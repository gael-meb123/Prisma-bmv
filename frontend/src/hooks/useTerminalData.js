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
    setEstado({ data: null, loading: true, error: null });
    cargar(ctrl.signal)
      .then((data) => !ctrl.signal.aborted && setEstado({ data, loading: false, error: null }))
      .catch((error) => !ctrl.signal.aborted && setEstado({ data: null, loading: false, error }));
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, activo]);
  return estado;
}

export function useTerminalData({ emisora, fecha, fechaSenal, permitido, conSesion, seccion, universoMercado = "base_15" }) {
  const real = import.meta.env.VITE_REQUIRE_REAL_API === "true";
  const es = (...secciones) => secciones.includes(seccion);
  const universoActivo = seccion === "mercado" && universoMercado === "ipc35_provisional" ? "ipc35_provisional" : null;
  const fechas = useRecurso((s) => api.getFechas(s), []);
  const mercado = useRecurso((s) => api.getMercado(fecha, s, universoActivo), [fecha, universoActivo], es("resumen", "mercado"));
  const sectores = useRecurso((s) => api.terminal.sectores(fecha, s), [fecha], es("resumen", "mercado"));
  const gobernanza = useRecurso((s) => api.terminal.gobernanza(s), [], es("gobernanza"));
  const metricas = useRecurso((s) => api.getMetricasModelos(s), [], es("senales", "calidad") && !real);
  const serie = useRecurso((s) => api.terminal.serie(emisora, s), [emisora], es("resumen") && permitido && conSesion);
  const senal = useRecurso((s) => api.terminal.senal(emisora, fecha, s), [emisora, fecha], es("senales") && permitido && conSesion);
  const seguimiento = useRecurso((s) => api.terminal.seguimiento(emisora, fechaSenal, s), [emisora, fechaSenal], es("seguimiento") && permitido && conSesion);
  const marcador = useRecurso((s) => api.terminal.marcador(s), [], es("seguimiento") && conSesion);
  return { fechas, mercado, sectores, gobernanza, metricas, serie, senal, seguimiento, marcador };
}
