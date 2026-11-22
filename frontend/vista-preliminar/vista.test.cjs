const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function iniciar(fetch) {
  const elements = {};
  class Element {
    constructor() { this.children = []; this.textContent = ""; this.value = ""; this.hidden = false; }
    appendChild(element) { this.children.push(element); }
    replaceChildren(...children) {
      this.children = children;
      if (children[0]?.value) this.value = children[0].value;
    }
    addEventListener(name, callback) { this[name] = callback; }
  }
  for (const id of ["fecha", "estado", "resultado", "cotizaciones", "filas", "verificadas", "sin-ppp", "fuente", "recargar"]) {
    elements[id] = new Element();
  }
  const context = {
    document: { getElementById: (id) => elements[id], createElement: () => new Element() },
    Option: class extends Element { constructor(label, value) { super(); this.textContent = label; this.value = value; } },
    fetch, AbortSignal, Number, Error, encodeURIComponent,
  };
  vm.runInNewContext(fs.readFileSync(__dirname + "/vista.js", "utf8"), context);
  return elements;
}

const tick = () => new Promise((resolve) => setImmediate(resolve));
test("no muestra precios de contingencia aunque la respuesta los contenga", async () => {
  const elementos = iniciar(async (url) => ({
    ok: true,
    json: async () => url.includes("/fechas") ? ["2026-11-19"] : {
      fecha: "2026-11-19", kpis: { total_emisoras: 1, total_verificadas: 0, total_ausentes: 1 },
      cotizaciones: [{ emisora: "WALMEX", estado_captura: "CONTINGENCIA_FUENTE_SECUNDARIA", ppp_bmv_mxn: 55, variacion_pct: 1 }],
      fuente: { actualizada: "2026-11-19" },
    },
  }));
  await tick();
  assert.equal(elementos.resultado.hidden, false);
  assert.equal(elementos.cotizaciones.children[0].children[3].textContent, "—");
  assert.equal(elementos.cotizaciones.children[0].children[4].textContent, "—");
});

test("si falla la API mantiene ocultos los resultados", async () => {
  const elementos = iniciar(async () => { throw new Error("fallo"); });
  await tick();
  assert.equal(elementos.resultado.hidden, true);
  assert.match(elementos.estado.textContent, /No fue posible/);
});
