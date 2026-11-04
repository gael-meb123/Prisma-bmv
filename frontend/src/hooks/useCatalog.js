import { useState, useEffect } from "react";
import { api } from "../services/api.mjs";

export function useCatalog() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [fechas, setFechas] = useState([]);
  const [mercado, setMercado] = useState(null);
  const [senales, setSenales] = useState([]);
  const [serie, setSerie] = useState([]);

  async function load(fecha = "2026-10-30") {
    setLoading(true);
    setError(null);
    try {
      const [fList, mData, sData, serData] = await Promise.all([
        api.getFechas(),
        api.getMercado(fecha),
        api.getSenales(fecha),
        api.getSerie("WALMEX")
      ]);
      setFechas(fList);
      setMercado(mData);
      setSenales(sData);
      setSerie(serData);
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
    refresh: load
  };
}
