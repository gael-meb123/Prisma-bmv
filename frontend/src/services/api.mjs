/**
 * Prisma BMV - Cliente de API Institucional con Fallback Automático a Mocks
 * Basado en la arquitectura resiliente de request() de Proyecto-geo.
 *
 * Cambios Fase 3:
 *  - Token JWT de Supabase en cada petición autenticada.
 *  - 401 → cierra sesión y redirige a #/acceso.
 *  - 403 → lanza APIError con el mensaje del backend (plan insuficiente).
 *  - Endpoints de mercado siguen sin auth (públicos).
 *  - Nuevos: me(), admin.*
 */

import { supabase } from "../lib/supabase.mjs";
import {
  MOCK_FECHAS,
  MOCK_MERCADO_RESUMEN,
  MOCK_SENALES_PANEL,
  MOCK_SERIE_WALMEX,
  MOCK_METRICAS_MODELOS
} from "../mocks/mockData.js";

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : "http://localhost:8000/api";

export class APIError extends Error {
  constructor(message, code, status) {
    super(message);
    this.name = "APIError";
    this.code = code;
    this.status = status;
  }
}

/**
 * @param {string} path - ruta relativa a API_BASE (ej. "/mercado/fechas")
 * @param {object} opts
 * @param {object}  [opts.body]      - cuerpo JSON (cambia método a POST)
 * @param {string}  [opts.method]    - método HTTP explícito (PATCH, DELETE, etc.)
 * @param {AbortSignal} [opts.signal]
 * @param {number}  [opts.timeoutMs] - timeout en ms (default 8000)
 * @param {boolean} [opts.auth]      - adjuntar token (default true)
 */
export async function request(path, { body, method, signal, timeoutMs = 8000, auth = true } = {}) {
  const timeout = AbortSignal.timeout(timeoutMs);
  const combinedSignal = signal ? AbortSignal.any([signal, timeout]) : timeout;

  try {
    const headers = { "Content-Type": "application/json" };
    let tieneToken = false;

    if (auth) {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
        tieneToken = true;
      }
    }

    // Sin sesión, las rutas protegidas ni se piden: se devuelve null y el
    // llamador usa su respaldo (mocks o respuesta local). Solo /mercado/* y /metricas/modelos son públicos.
    const esPublica = path.startsWith("/mercado/") || path.startsWith("/metricas/modelos");
    if (!tieneToken && !esPublica) return null;

    const httpMethod = method || (body ? "POST" : "GET");

    const res = await fetch(`${API_BASE}${path}`, {
      method: httpMethod,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: combinedSignal,
    });

    if (res.status === 401) {
      // Visitante sin cuenta: no es un error, se usan los mocks
      if (!tieneToken) return null;
      // Tenía sesión y el token fue rechazado: cerrar sesión
      await supabase.auth.signOut();
      window.location.hash = "/acceso";
      throw new APIError("Sesión vencida. Inicia sesión de nuevo.", "AUTH_EXPIRED", 401);
    }

    if (res.status === 403) {
      const data = await res.json().catch(() => ({}));
      throw new APIError(
        data.detail || "No tienes permiso para acceder a este recurso.",
        "FORBIDDEN",
        403
      );
    }

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new APIError(data.detail || `Error ${res.status}`, "API_ERROR", res.status);
    }

    return await res.json();
  } catch (error) {
    if (signal?.aborted) throw error;
    // Re-lanzar errores de auth/permisos (no usar mock para esos)
    if (error instanceof APIError) throw error;
    // Si el backend no está encendido, fallback local inmediato
    return null;
  }
}

export const api = {
  // --- Perfil verificado (nuevo) ---
  async me(signal) {
    return request("/me", { signal });
  },

  // --- Monitor de mercado (público) ---
  async getFechas(signal) {
    const data = await request("/mercado/fechas", { signal, auth: false });
    return data || MOCK_FECHAS;
  },

  async getMercado(fecha = "2026-10-30", signal) {
    const data = await request(`/mercado/resumen?fecha=${fecha}`, { signal, auth: false });
    return data || MOCK_MERCADO_RESUMEN;
  },

  // --- Métricas Institucionales y Asignación de Capital ¼-Kelly (público) ---
  async getMetricasModelos(signal) {
    const data = await request("/metricas/modelos", { signal, auth: false });
    return data || MOCK_METRICAS_MODELOS;
  },

  // --- Señales Panel G2 (requiere sesión, filtrado por plan en backend) ---
  async getSenales(fecha = "2026-11-05", ticker = null, signal) {
    const query = ticker ? `?fecha=${fecha}&emisora=${ticker}` : `?fecha=${fecha}`;
    const data = await request(`/senales/panel${query}`, { signal });
    const adaptar = (s) => ({
      id: s.id_senal_g2,
      emisora: s.emisora,
      modelo: s.modelo_g2,
      prob: s.probabilidad_subida,
      pred: s.prediccion_etiqueta,
      consenso: s.estado_consenso_g2,
      ppp_base: s.ppp_base_t,
      ret_rel: s.ret_10_rel_panel,
      sector: s.sector,
      muestra_evaluacion: s.muestra_evaluacion || "IN_SAMPLE_DISENO",
      estado_resolucion: s.estado_resolucion || "PENDIENTE_RECONCILIACION",
      sesiones_transcurridas: s.sesiones_transcurridas ?? 0,
      retorno_parcial_pct: s.retorno_parcial_pct ?? null,
      acierto_parcial_en_curso: s.acierto_parcial_en_curso ?? null,
    });

    if (data && data.senales) return data.senales.map(adaptar);
    if (ticker) {
      return MOCK_SENALES_PANEL.filter((s) => s.emisora === ticker);
    }
    return MOCK_SENALES_PANEL;
  },

  // --- Serie temporal (requiere sesión) ---
  async getSerie(ticker = "WALMEX", signal) {
    const data = await request(`/serie/${ticker.toLowerCase()}`, { signal });
    return data || MOCK_SERIE_WALMEX;
  },

  // --- Chat Prismi (requiere sesión) ---
  async chatPrismi(pregunta, historial = [], signal, { hasSession = true } = {}) {
    const p = pregunta.toLowerCase();

    // Preguntas sobre la cuenta: se responden aquí, con o sin sesión.
    if (/sesi[oó]n|registr|cuenta|login|contrase|acceder|entrar|inscrib/.test(p)) {
      return hasSession
        ? "Ya tienes la sesión iniciada. Para salir usa «Salir» arriba a la derecha; tu plan lo ves y lo cambias en «Planes»."
        : "Para entrar a la terminal usa «Iniciar sesión» arriba a la derecha. Si aún no tienes cuenta, elige «Regístrate» en ese formulario: es gratis y empiezas con el plan Explorer (WALMEX completo y el monitor de las 15 emisoras).";
    }

    const data = await request("/chat/prismi", { body: { pregunta, historial }, signal });
    if (data && data.respuesta) return data.respuesta;

    // Respuestas analíticas deterministas locales si el backend no está encendido
    // (o si no hay sesión: el backend responde 401 y se usa este respaldo).
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
    if (!hasSession) {
      return "Sin sesión solo puedo darte respuestas básicas. Inicia sesión (o regístrate gratis) y te respondo con los datos del panel G2.";
    }
    return "¡Hola! Soy Prismi, la gráfica bailarina de Prisma BMV. 🕯️💃 Puedo resolver dudas sobre las 15 emisoras del IPC, los modelos del panel G2 y las señales vigentes.";
  },

  // --- Admin (requiere rol admin) ---
  admin: {
    async listarUsuarios(signal) {
      return request("/admin/usuarios", { signal });
    },
    async crearUsuario({ nombre, email, password, rol, plan }, signal) {
      return request("/admin/usuarios", {
        body: { nombre, email, password, rol, plan },
        signal,
      });
    },
    async actualizarUsuario(uid, cambios, signal) {
      return request(`/admin/usuarios/${uid}`, {
        method: "PATCH",
        body: cambios,
        signal,
      });
    },
  },
};
