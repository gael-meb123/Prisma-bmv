import { useEffect, useState } from "react";
import { api } from "../services/api.mjs";

// Estado del mercado para la barra superior. Se pide una sola vez por carga de página.
let cache = null;
let enCurso = null;

function cargar() {
  if (cache) return Promise.resolve(cache);
  if (!enCurso) {
    enCurso = api
      .getMercado(undefined)
      .then((m) => {
        const k = m?.kpis || {};
        cache = {
          fecha: m?.fecha || k.fecha || "—",
          verificadas: k.total_verificadas ?? "—",
          total: k.total_emisoras ?? 15,
          mercado: m,
        };
        return cache;
      })
      .catch(() => null)
      .finally(() => {
        enCurso = null;
      });
  }
  return enCurso;
}

export function useMarketStatus() {
  const [status, setStatus] = useState(cache);
  useEffect(() => {
    let vivo = true;
    cargar().then((s) => vivo && s && setStatus(s));
    return () => {
      vivo = false;
    };
  }, []);
  return status;
}
