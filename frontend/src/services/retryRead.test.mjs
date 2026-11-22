import { test } from "node:test";
import assert from "node:assert/strict";
import { fetchLectura } from "./retryRead.mjs";

test("reintenta una lectura temporalmente limitada una sola vez", async () => {
  let n = 0, pausas = 0, cancelado = 0;
  const fetchImpl = async () => ++n === 1
    ? { status: 503, body: { cancel: async () => { cancelado++; } } }
    : { status: 200 };
  const r = await fetchLectura("/mercado", { method: "GET" }, {
    reintentar: true, fetchImpl, esperarImpl: async () => { pausas++; },
  });
  assert.equal(r.status, 200);
  assert.equal(n, 2);
  assert.equal(pausas, 1);
  assert.equal(cancelado, 1);
});

test("no reintenta escrituras ni lecturas sin autorización", async () => {
  let n = 0;
  const fetchImpl = async () => { n++; return { status: 503 }; };
  await fetchLectura("/usuarios", { method: "POST" }, { reintentar: true, fetchImpl });
  await fetchLectura("/senales", { method: "GET" }, { reintentar: false, fetchImpl });
  assert.equal(n, 2);
});

test("una cancelación durante la espera no hace otra llamada", async () => {
  let n = 0;
  const ctrl = new AbortController();
  const promise = fetchLectura("/mercado", { method: "GET", signal: ctrl.signal }, {
    reintentar: true,
    fetchImpl: async () => { n++; return { status: 429 }; },
  });
  await Promise.resolve();
  ctrl.abort();
  await assert.rejects(promise, { name: "AbortError" });
  assert.equal(n, 1);
});
