import test from "node:test";
import assert from "node:assert/strict";
import { describirModelos, estadoModeloHistorico, modelosHistoricosSinSenal, nombreModelo, STATUS } from "./presentation.mjs";

test("no atribuye operación o conciliación automática a estados de contingencia", () => {
  assert.match(STATUS.NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA.description, /no acredita ausencia de operación/);
  assert.match(STATUS.CONTINGENCIA_FUENTE_SECUNDARIA.description, /pausada/);
  assert.match(STATUS.PPP_OBSERVADO_MAPEO_PROVISIONAL.description, /sin señales/);
  assert.match(STATUS.NO_ENCONTRADO_EN_TABLAS_BOLETIN.description, /no se imputa/);
  assert.match(STATUS.BOLETIN_BRONZE_NO_DISPONIBLE.description, /sin precio/);
});

test("presenta nombres claros sin modificar los identificadores internos", () => {
  assert.equal(nombreModelo("G2_V4_ADJ"), "G2-V4 · Ajustado por dividendos");
  assert.equal(nombreModelo("G2_V4_F1_GAP"), "G2-V4 · Ajustado con señal de cierre");
  assert.equal(nombreModelo("OTRO_MODELO", "Otro modelo"), "Otro modelo");
});

test("identifica las cinco variantes del panel de la ficha técnica", () => {
  const modelos = [
    ["G2_V1_POOLED_REL3_CALIBRADO", "G2-V1 · Calibrado"],
    ["G2_V2_POOLED_REL3_ZONA_NEUTRAL", "G2-V2 · Zona neutral"],
    ["G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO", "G2-V3 · Alta discriminación"],
    ["G2_V4_POOLED_DM5_REL_CORTO_PLAZO", "G2-V4 · Agotamiento corto"],
    ["G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL", "G2-V5 · Adaptativo por régimen"],
  ];
  for (const [id, nombre] of modelos) assert.equal(nombreModelo(id), nombre);
});

test("sustituye los identificadores conocidos dentro de una descripción", () => {
  assert.equal(
    describirModelos("G2_V4_ADJ y G2_V4_F1_GAP están en evaluación."),
    "G2-V4 · Ajustado por dividendos y G2-V4 · Ajustado con señal de cierre están en evaluación.",
  );
  assert.equal(describirModelos(null), null);
});

test("distingue variantes históricas y roles sin confundir identificadores", () => {
  assert.deepEqual(estadoModeloHistorico("G2_V1_ADJ", "SHADOW"), ["Evaluación histórica TEST", "Variante ajustada", "Shadow"]);
  assert.deepEqual(estadoModeloHistorico("G2_V6A_JERARQUICO", "SHADOW_V6"), ["Evaluación histórica TEST", "Shadow"]);
  const metricas = { modelos_test: [{ id_modelo: "G2_V1_ADJ" }, { id_modelo: "G2_V4" }] };
  assert.deepEqual(modelosHistoricosSinSenal(metricas, [{ modelo: "G2_V4" }, { modelo: "G2_V1_POOLED_REL3_CALIBRADO" }]), [{ id_modelo: "G2_V1_ADJ" }]);
  assert.deepEqual(modelosHistoricosSinSenal(null, []), []);
});
