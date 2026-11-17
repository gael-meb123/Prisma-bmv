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

// Token de la sesión activa. Lo fija useAccount en cada cambio de sesión (login, refresh, logout).
// Leerlo de aquí evita llamar a supabase.auth.getSession() en cada petición: varias llamadas
// concurrentes compiten por el mismo candado de Supabase y pueden dejar peticiones colgadas.
let tokenSesion = null;
export function setAuthToken(token) {
  tokenSesion = token || null;
}

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
      let token = tokenSesion;
      if (!token) {
        const { data: { session } } = await supabase.auth.getSession();
        token = session?.access_token || null;
      }
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
        tieneToken = true;
      }
    }

    // Sin sesión, las rutas protegidas ni se piden: se devuelve null y el
    // llamador usa su respaldo (mocks o respuesta local). Solo /mercado/* y /metricas/modelos son públicos.
    const esPublica =
      path.startsWith("/mercado/") ||
      path.startsWith("/metricas/modelos") ||
      path.startsWith("/terminal/sectores") ||
      path.startsWith("/terminal/gobernanza");
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

  async getMercado(fecha = null, signal) {
    const data = await request(`/mercado/resumen${fecha ? `?fecha=${fecha}` : ""}`, { signal, auth: false });
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

  // --- Chat Prismi ---
  // Con sesión: motor del backend (mismas reglas que la terminal: alcance, sin asesoría,
  // contexto con los datos del día y, si la hay, la gráfica que se está viendo).
  // Sin sesión o sin backend: respuestas locales sin cifras de mercado (para no inventar datos).
  async chatPrismi(pregunta, historial = [], signal, { hasSession = true, contexto = null } = {}) {
    const p = pregunta.toLowerCase();

    // Preguntas sobre la cuenta: se responden aquí, con o sin sesión.
    if (/sesi[oó]n|registr|cuenta|login|contrase|acceder|entrar|inscrib/.test(p)) {
      return hasSession
        ? "Ya tienes la sesión iniciada. Para salir usa «Salir» en el menú lateral de la terminal; tu plan lo ves y lo cambias en tu tarjeta de usuario o en «Planes»."
        : "Para entrar a la terminal usa «Ingresar» arriba a la derecha. Si aún no tienes cuenta, elige «Abrir cuenta»: es gratis y empiezas con el plan Explorer (WALMEX completo y el monitor de las 15 emisoras).";
    }

    if (hasSession) {
      const hist = historial
        .filter((m) => m && m.text)
        .slice(-6)
        .map((m) => ({ role: m.sender === "user" ? "user" : "assistant", content: m.text }));
      const data = await request("/terminal/prismi", {
        body: { pregunta, historial: hist, contexto_grafica: contexto || null },
        signal,
        timeoutMs: 25000,
      }).catch(() => null);
      if (data && data.respuesta) return data.respuesta;
    }

    if (/receta|futbol|cocina|politica|clima/.test(p)) {
      return "Mi alcance se limita a Prisma BMV: el PPP oficial, las 15 emisoras que monitoreamos, los modelos y el funcionamiento de la plataforma.";
    }
    if (p.includes("ppp")) {
      return "El PPP (Precio Promedio Ponderado) es el precio oficial que publica la BMV ponderando el volumen de todas las operaciones de la sesión. A diferencia del último hecho, que puede moverse con pocas operaciones al cierre, refleja dónde se negoció realmente el volumen del día.";
    }
    if (p.includes("g2") || p.includes("modelo")) {
      return "El panel G2 usa regresiones logísticas agrupadas sobre WALMEX, GMEXICO, GFNORTE, AMX y el resto del IPC. Cada modelo estima la probabilidad de que el PPP dentro de 5 sesiones supere al de hoy; si todos coinciden, hay consenso.";
    }
    if (!hasSession) {
      return "Sin sesión solo puedo darte respuestas generales. Inicia sesión (o abre tu cuenta gratis) y te respondo con los datos del día y te explico cada gráfica de la terminal.";
    }
    return "Ahora no pude consultar los datos del día. Puedo explicarte el PPP, los modelos G2, el seguimiento t+1 a t+5 o la política de cero imputación.";
  },

  // --- Terminal: gráficas (sector y gobernanza son públicas; el resto respeta el plan) ---
  terminal: {
    sectores(fecha, signal) {
      return request(`/terminal/sectores${fecha ? `?fecha=${fecha}` : ""}`, { signal, auth: false });
    },
    gobernanza(signal) {
      return request("/terminal/gobernanza", { signal, auth: false });
    },
    serie(emisora, signal) {
      return request(`/terminal/serie?emisora=${encodeURIComponent(emisora)}`, { signal });
    },
    senal(emisora, fecha, signal) {
      const f = fecha ? `&fecha=${fecha}` : "";
      return request(`/terminal/senal?emisora=${encodeURIComponent(emisora)}${f}`, { signal });
    },
    seguimiento(emisora, fechaSenal, signal) {
      const f = fechaSenal ? `&fecha_senal=${fechaSenal}` : "";
      return request(`/terminal/seguimiento?emisora=${encodeURIComponent(emisora)}${f}`, { signal });
    },
    marcador(signal) {
      return request("/terminal/marcador", { signal });
    },
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
