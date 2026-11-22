import test from "node:test";
import assert from "node:assert/strict";
import { explicarEstadistica } from "./explicaciones.mjs";

const reporte = {
  cobertura_historico: { fecha_inicial: "2025-01-01", fecha_final: "2025-01-31", registros: 5,
    estados: { PPP_PUBLICADO_VERIFICADO: 4 } },
  cobertura_panel: { registros: 3 },
  estadisticas_historico_verificado: [{ agrupacion: "total", variable: "variacion_ppp_vs_anterior_pct", n_valido: 3, media: 0.5 }],
  frecuencias_direccion: [
    { agrupacion: "total", direccion: "alza", n: 2 }, { agrupacion: "total", direccion: "baja", n: 1 },
    { agrupacion: "total", direccion: "sin_cambio", n: 0 },
  ],
};

test("explica la muestra y las frecuencias reales", () => {
  const r = explicarEstadistica({ emisora: "WALMEX", reporte, apartado: "direccion" });
  assert.match(r.texto, /De 3 variaciones válidas: 2 fueron alzas, 1 bajas/);
  assert.match(r.contexto, /WALMEX/);
  assert.match(r.contexto, /2025-01-01/);
});

test("distingue correlación y predicción y conserva el método", () => {
  const r = explicarEstadistica({ emisora: "WALMEX", reporte, apartado: "correlacion", metodo: "spearman" });
  assert.match(r.texto, /método seleccionado es Spearman/);
  assert.match(r.texto, /no es causalidad ni predicción/);
  assert.match(r.contexto, /spearman/);
});

test("no inventa estadísticas con datos vacíos", () => {
  const vacio = { ...reporte, estadisticas_historico_verificado: [], frecuencias_direccion: [] };
  assert.match(explicarEstadistica({ emisora: "WALMEX", reporte: vacio, apartado: "direccion" }).texto, /No hay variaciones válidas/);
  assert.match(explicarEstadistica({ emisora: "WALMEX" }).texto, /No hay un reporte/);
});
