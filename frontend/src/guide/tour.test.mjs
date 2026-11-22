import test from "node:test";
import assert from "node:assert/strict";
import { buildSteps } from "./tour.mjs";

test("recorrido publico cubre landing restaurada, mercado hoy, planes y acceso", () => {
  const ids = buildSteps("public", { goldEval: false }).map((s) => s.id);
  assert.deepEqual(ids, ["hola", "mercado-hoy", "ppp", "capacidades", "planes", "seguridad", "acceso"]);
});

test("recorrido terminal en modo estricto omite modulos Gold bloqueados e incluye IPC-35, Estadistica, Yahoo y Gobernanza", () => {
  const ids = buildSteps("terminal", { goldEval: false }).map((s) => s.id);
  assert.ok(ids.includes("universo-ipc35"));
  assert.ok(ids.includes("estadistica"));
  assert.ok(ids.includes("yahoo-secundaria"));
  assert.ok(ids.includes("gobernanza"));
  assert.ok(!ids.includes("consenso"));
  assert.ok(!ids.includes("modelos"));
  assert.ok(!ids.includes("calidad"));
});

test("recorrido terminal en modo evaluacion Gold incluye Consenso, Senales, Seguimiento y Calidad ademas de IPC-35 y Yahoo", () => {
  const ids = buildSteps("terminal", { goldEval: true }).map((s) => s.id);
  for (const esperado of ["universo-ipc35", "consenso", "modelos", "factor", "trayectoria", "marcador", "calidad", "estadistica", "yahoo-secundaria", "gobernanza"]) {
    assert.ok(ids.includes(esperado), `Falta paso ${esperado}`);
  }
});
