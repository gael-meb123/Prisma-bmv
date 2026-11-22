"use strict";

const API = "https://j42hw8l6rl.execute-api.us-east-1.amazonaws.com";
const fecha = document.getElementById("fecha");
const estado = document.getElementById("estado");
const resultado = document.getElementById("resultado");
const tabla = document.getElementById("cotizaciones");
let solicitud = 0;

function celda(fila, contenido) {
  const elemento = document.createElement("td");
  elemento.textContent = contenido;
  fila.appendChild(elemento);
}

function etiquetaEstado(valor) {
  if (valor === "PPP_PUBLICADO_VERIFICADO") return "Marcado como verificado";
  if (valor === "CONTINGENCIA_FUENTE_SECUNDARIA") return "Contingencia secundaria";
  return "No verificado o no disponible";
}

function numero(valor, sufijo = "") {
  return typeof valor === "number" && Number.isFinite(valor)
    ? valor.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + sufijo
    : "—";
}

async function consultar(ruta) {
  const respuesta = await fetch(API + ruta, { signal: AbortSignal.timeout(15000), cache: "no-store" });
  if (!respuesta.ok) throw new Error("API no disponible");
  return respuesta.json();
}

async function cargarResumen(valor) {
  const actual = ++solicitud;
  resultado.hidden = true;
  estado.textContent = "Consultando el resumen…";
  try {
    const datos = await consultar("/api/mercado/resumen?fecha=" + encodeURIComponent(valor));
    if (actual !== solicitud) return;
    if (datos.fecha !== valor || !datos.kpis || !Array.isArray(datos.cotizaciones)) throw new Error("Respuesta inválida");
    tabla.replaceChildren();
    for (const cotizacion of datos.cotizaciones) {
      const fila = document.createElement("tr");
      const verificado = cotizacion.estado_captura === "PPP_PUBLICADO_VERIFICADO";
      celda(fila, cotizacion.emisora || "—");
      celda(fila, cotizacion.serie || "—");
      celda(fila, etiquetaEstado(cotizacion.estado_captura));
      celda(fila, verificado ? numero(cotizacion.ppp_bmv_mxn) : "—");
      celda(fila, verificado ? numero(cotizacion.variacion_pct, " %") : "—");
      tabla.appendChild(fila);
    }
    document.getElementById("filas").textContent = datos.kpis.total_emisoras ?? "—";
    document.getElementById("verificadas").textContent = datos.kpis.total_verificadas ?? "—";
    document.getElementById("sin-ppp").textContent = datos.kpis.total_ausentes ?? "—";
    document.getElementById("fuente").textContent = "Fuente: instantánea S3; última modificación informada: " + (datos.fuente?.actualizada || "no disponible") + ".";
    estado.textContent = "Sesión " + datos.fecha + ".";
    resultado.hidden = false;
  } catch {
    if (actual === solicitud) estado.textContent = "No fue posible consultar los datos reales. Intenta de nuevo; no se mostrarán datos de ejemplo.";
  }
}

async function cargarFechas() {
  const actual = ++solicitud;
  resultado.hidden = true;
  fecha.disabled = true;
  estado.textContent = "Consultando las fechas disponibles…";
  try {
    const fechas = await consultar("/api/mercado/fechas");
    if (actual !== solicitud) return;
    if (!Array.isArray(fechas) || !fechas.length || !fechas.every((f) => /^\d{4}-\d{2}-\d{2}$/.test(f))) throw new Error("Fechas inválidas");
    const anterior = fecha.value;
    fecha.replaceChildren(...fechas.map((f) => new Option(f, f)));
    if (fechas.includes(anterior)) fecha.value = anterior;
    fecha.disabled = false;
    await cargarResumen(fecha.value);
  } catch {
    if (actual === solicitud) estado.textContent = "No fue posible consultar las fechas. Intenta de nuevo; no se mostrarán datos de ejemplo.";
  }
}

fecha.addEventListener("change", () => cargarResumen(fecha.value));
document.getElementById("recargar").addEventListener("click", cargarFechas);
cargarFechas();
