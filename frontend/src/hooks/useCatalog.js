import { useState, useEffect } from "react";
import { api } from "../services/api.mjs";

export function useCatalog() {
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
      const targetFecha = fecha || (Array.isArray(fList) && fList.length > 0 ? fList[0] : "2026-11-05");
      const [mData, sData, serData, metData] = await Promise.all([
        api.getMercado(targetFecha),
        api.getSenales(targetFecha),
        api.getSerie("WALMEX"),
        api.getMetricasModelos()
      ]);
      setFechas(fList);
      setMercado(mData);
      setSenales(sData);
      setSerie(serData);
      setMetricas(metData);
    } catch (err) {
      setError("No se pudo conectar con el catálogo de mercado.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

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
