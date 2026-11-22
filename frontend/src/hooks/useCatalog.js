import { useState, useEffect } from "react";
import { api } from "../services/api.mjs";

export function useCatalog(activo = true) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [fechas, setFechas] = useState([]);
  const [mercado, setMercado] = useState(null);
  const [senales, setSenales] = useState([]);
  const [serie, setSerie] = useState([]);
  const [metricas, setMetricas] = useState(null);

  async function load(fecha = null) {
    setLoading(true);
    setError(null);
    try {
      const fList = await api.getFechas();
      const targetFecha = fecha || (Array.isArray(fList) && fList.length > 0 ? fList[0] : null);
      if (!targetFecha) throw new Error("Sin fechas disponibles.");
      const results = await Promise.allSettled([
        api.getMercado(targetFecha),
        api.getSenales(targetFecha),
        api.getSerie("WALMEX"),
        api.getMetricasModelos()
      ]);
      setFechas(fList);
      setMercado(results[0].status === "fulfilled" ? results[0].value : null);
      setSenales(results[1].status === "fulfilled" ? results[1].value : []);
      setSerie(results[2].status === "fulfilled" ? results[2].value : []);
      setMetricas(results[3].status === "fulfilled" ? results[3].value : null);
      if (results.some((r) => r.status === "rejected")) setError("Algunos recursos no están disponibles.");
    } catch (err) {
      setMercado(null);
      setSenales([]);
      setSerie([]);
      setMetricas(null);
      setError("No se pudo conectar con el catálogo de mercado.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (activo) load();
    else setLoading(false);
  }, [activo]);

  return {
    loading,
    error,
    fechas,
    mercado,
    senales,
    serie,
    metricas,
    refresh: load
  };
}
