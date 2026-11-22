import { test } from "node:test";
import assert from "node:assert/strict";
import { crearLimitador } from "./requestLimiter.mjs";

test("limita las peticiones activas y libera turnos", async () => {
  const run = crearLimitador(2);
  let activas = 0, max = 0;
  const tareas = Array.from({ length: 5 }, () => run(async () => {
    activas++; max = Math.max(max, activas);
    await new Promise((resolve) => setTimeout(resolve, 5));
    activas--;
  }));
  await Promise.all(tareas);
  assert.equal(max, 2);
});

test("cancelar una tarea en cola no impide que avance la siguiente", async () => {
  const run = crearLimitador(1);
  let liberar;
  const primera = run(() => new Promise((resolve) => { liberar = resolve; }));
  await Promise.resolve();
  const ctrl = new AbortController();
  const segunda = run(() => { throw new Error("No debe ejecutarse"); }, ctrl.signal);
  const tercera = run(() => "ok");
  ctrl.abort();
  await assert.rejects(segunda, { name: "AbortError" });
  liberar();
  await primera;
  assert.equal(await tercera, "ok");
});

test("un error libera el turno", async () => {
  const run = crearLimitador(1);
  await assert.rejects(run(async () => { throw new Error("fallo"); }), /fallo/);
  assert.equal(await run(() => "ok"), "ok");
});
