// Navegador headless real mediante CDP; no imprime tokens ni respuestas completas.
const DEBUG = "http://127.0.0.1:19333";
const URL = "https://demo.d315dh37vi024o.amplifyapp.com/";

async function main() {
  const tab = await (await fetch(`${DEBUG}/json/new?about:blank`, { method: "PUT" })).json();
  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  let id = 0;
  const pending = new Map();
  let loaded;
  const load = new Promise((resolve) => { loaded = resolve; });
  ws.addEventListener("message", ({ data }) => {
    const msg = JSON.parse(data);
    if (msg.method === "Page.loadEventFired") loaded();
    if (msg.id && pending.has(msg.id)) {
      const [resolve, reject] = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
    }
  });
  function call(method, params = {}) {
    return new Promise((resolve, reject) => {
      const n = ++id; pending.set(n, [resolve, reject]);
      ws.send(JSON.stringify({ id: n, method, params }));
    });
  }
  try {
    await call("Page.enable");
    await call("Runtime.enable");
    await call("Page.navigate", { url: URL });
    await Promise.race([load, new Promise((_, reject) => setTimeout(() => reject(new Error("Navegación vencida")), 20000))]);
    const result = await call("Runtime.evaluate", {
      awaitPromise: true, returnByValue: true,
      expression: `(async () => {
        const ready = () => !document.querySelector('#resultado')?.hidden ||
          document.querySelector('#estado')?.textContent.includes('No fue posible');
        if (!ready()) await new Promise((resolve) => {
          const observer = new MutationObserver(() => { if (ready()) { observer.disconnect(); resolve(); } });
          observer.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });
          setTimeout(() => { observer.disconnect(); resolve(); }, 18000);
        });
        const rows = [...document.querySelectorAll('#cotizaciones tr')];
        return { titulo: document.title, estado: document.querySelector('#estado')?.textContent,
          fecha: document.querySelector('#fecha')?.value, filas: rows.length,
          pppVerificados: document.querySelector('#verificadas')?.textContent,
          contingencias: rows.filter(r => r.cells[2]?.textContent === 'Contingencia secundaria').length,
          contingenciasConPrecio: rows.filter(r => r.cells[2]?.textContent === 'Contingencia secundaria' &&
            (r.cells[3]?.textContent !== '—' || r.cells[4]?.textContent !== '—')).length,
          visible: !document.querySelector('#resultado')?.hidden };
      })()`,
    });
    if (result.exceptionDetails) throw new Error("Fallo de evaluación de interfaz");
    const v = result.result.value;
    console.log(JSON.stringify(v));
    if (!v.visible || !v.fecha || !v.filas || v.contingenciasConPrecio !== 0) process.exitCode = 1;
  } finally {
    ws.close();
    await fetch(`${DEBUG}/json/close/${tab.id}`);
  }
}
main().catch((error) => { console.error("Prueba navegador:", error.message); process.exitCode = 1; });
