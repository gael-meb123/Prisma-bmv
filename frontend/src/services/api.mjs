/**
 * Prisma BMV - Cliente de API Institucional con Fallback Automático a Mocks
 * Basado en la arquitectura resiliente de request() de Proyecto-geo.
 */

import { MOCK_FECHAS, MOCK_MERCADO_RESUMEN, MOCK_SENALES_PANEL, MOCK_SERIE_WALMEX } from "../mocks/mockData.js";

const API_BASE = "http://localhost:8000/api";

export class APIError extends Error {
  constructor(message, code, status) {
    super(message);
    this.name = "APIError";
    this.code = code;
    this.status = status;
  }
}

export async function request(path, { body, signal, timeoutMs = 8000 } = {}) {
  const timeout = AbortSignal.timeout(timeoutMs);
  const combinedSignal = signal ? AbortSignal.any([signal, timeout]) : timeout;

  try {
    const headers = body ? { "Content-Type": "application/json" } : {};
    const res = await fetch(`${API_BASE}${path}`, {
      method: body ? "POST" : "GET",
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: combinedSignal,
    });
    if (!res.ok) throw new Error();
    return await res.json();
  } catch (error) {
    if (signal?.aborted) throw error;
    // Si el backend no está encendido, fallback local inmediato
    return null;
  }
}

export const api = {
  async getFechas(signal) {
    const data = await request("/mercado/fechas", { signal });
    return data || MOCK_FECHAS;
  },

  async getMercado(fecha = "2026-10-30", signal) {
    const data = await request(`/mercado/resumen?fecha=${fecha}`, { signal });
    return data || MOCK_MERCADO_RESUMEN;
  },

  async getSenales(fecha = "2026-10-30", ticker = null, signal) {
    const query = ticker ? `?fecha=${fecha}&emisora=${ticker}` : `?fecha=${fecha}`;
    const data = await request(`/senales/panel${query}`, { signal });
    if (data && data.senales) return data.senales;
    if (ticker) {
      return MOCK_SENALES_PANEL.filter((s) => s.emisora === ticker);
    }
    return MOCK_SENALES_PANEL;
  },

  async getSerie(ticker = "WALMEX", signal) {
    const data = await request(`/serie/${ticker.toLowerCase()}`, { signal });
    return data || MOCK_SERIE_WALMEX;
  },

  async chatPrismi(pregunta, historial = [], signal) {
    const data = await request("/chat/prismi", { body: { pregunta, historial }, signal });
    if (data && data.respuesta) return data.respuesta;

    // Respuestas analíticas deterministas locales si el backend no está encendido
    const p = pregunta.toLowerCase();
    if (p.includes("receta") || p.includes("futbol") || p.includes("cocina") || p.includes("politica")) {
      return "Disculpa, como asistente cuantitativo de Prisma BMV, mi conocimiento está estrictamente restringido a los modelos matemáticos, cotizaciones oficiales y funcionamiento de nuestra plataforma. No tengo información sobre temas externos.";
    }
    if (p.includes("ppp")) {
      return "El PPP (Precio Promedio Ponderado) oficial de la BMV es el precio ponderado por volumen transaccionado en la sesión, inmune a distorsiones de subastas de cierre.";
    }
    if (p.includes("walmex")) {
      return "WALMEX cotizó en $50.39 (+3.32% en la sesión, +4.11% acumulado). Los modelos anticipan una fase de consolidación técnica tras cruzar los 50 pesos.";
    }
    if (p.includes("gmexico")) {
      return "GMEXICO ($224.31) presenta un fuerte consenso alcista (54.9% - 56.5%) por rezago relativo extremo (-13.06%), proyectando rebote estadístico en t+5.";
    }
    if (p.includes("g2") || p.includes("modelo")) {
      return "El Panel G2 utiliza regresión logística agrupada (Pooled Logit) optimizada mediante el algoritmo Newton-Raphson IRLS puro, exigiendo convergencia en 3 variantes simultáneas.";
    }
    return "¡Hola! Soy Prismi, la gráfica bailarina de Prisma BMV. 🕯️💃 Puedo resolver dudas sobre las 15 emisoras del IPC, los modelos del panel G2 y las señales vigentes.";
  }
};
