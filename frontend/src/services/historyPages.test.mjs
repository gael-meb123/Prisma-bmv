import { test } from "node:test";
import assert from "node:assert/strict";
import { recorrerHistorial } from "./historyPages.mjs";
const hash = "a".repeat(64);
const page = (fechas, siguiente = null) => ({ fechas, siguiente, sha256_instantanea: hash });
test("combina todas las páginas y deduplica la instantánea", async () => {
  const result = await recorrerHistorial(async cursor => cursor
    ? page(["2026-11-18", "2026-11-20"])
    : page(["2026-11-18", "2026-11-19"], "2026-11-19"), "fechas");
  assert.deepEqual(result.fechas, ["2026-11-18", "2026-11-19", "2026-11-20"]);
});
test("error posterior no entrega un historial parcial", async () => {
  await assert.rejects(recorrerHistorial(async cursor => {
    if (cursor) throw new Error("corrupción");
    return page(["2026-11-19"], "2026-11-19");
  }, "fechas"), /corrupción/);
});
test("detecta cambio de instantánea, cursor repetido y conflicto", async () => {
  await assert.rejects(recorrerHistorial(async cursor => cursor
    ? { ...page([]), sha256_instantanea: "b".repeat(64) }
    : page([], "2026-11-19"), "fechas"), /instantánea cambió/);
  await assert.rejects(recorrerHistorial(async () => page([], "2026-11-19"), "fechas"), /Cursor/);
  await assert.rejects(recorrerHistorial(async cursor => ({
    sha256_instantanea: hash, siguiente: cursor ? null : "2026-11-19",
    puntos: [{ fecha: "2026-11-19", ppp: cursor ? 2 : 1 }],
  }), "puntos"), /Conflicto/);
});
test("cancelación detiene recorrido", async () => {
  const ctrl = new AbortController();
  ctrl.abort();
  await assert.rejects(recorrerHistorial(() => { throw new Error("No debe consultar"); }, "fechas", ctrl.signal), { name: "AbortError" });
});
