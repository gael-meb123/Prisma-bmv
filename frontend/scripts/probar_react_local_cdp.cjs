// Prueba local con Cognito real. Chrome debe ser aislado y tener web security
// deshabilitado SOLO para localhost: el CORS productivo se prueba por separado.
const DEBUG = process.env.DEBUG_URL || "http://127.0.0.1:19334";
const ORIGIN = process.env.APP_ORIGIN || "http://127.0.0.1:5173";
const { EMAIL, PASS } = process.env;
if ((!EMAIL || !PASS) && process.env.FORMULARIOS_SOLO !== "1") throw new Error("Faltan credenciales sintéticas de prueba.");

async function main() {
  const tab = await (await fetch(`${DEBUG}/json/new?about:blank`, { method: "PUT" })).json();
  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true }); ws.addEventListener("error", reject, { once: true });
  });
  let id = 0, onLoad;
  const errores = [];
  const respuestasApi = [];
  const load = new Promise((resolve) => { onLoad = resolve; });
  const pending = new Map();
  ws.addEventListener("message", ({ data }) => {
    const msg = JSON.parse(data);
    if (msg.method === "Page.loadEventFired") onLoad();
    if (msg.method === "Runtime.exceptionThrown") {
      errores.push(msg.params?.exceptionDetails?.exception?.description?.split("\n")[0] || "Excepción de JavaScript");
    }
    if (msg.method === "Network.responseReceived" && msg.params?.response?.url?.startsWith("https://j42hw8l6rl.execute-api.us-east-1.amazonaws.com/")) {
      const r = msg.params.response;
      respuestasApi.push({ ruta: new URL(r.url).pathname, status: r.status });
    }
    if (msg.id && pending.has(msg.id)) {
      const [resolve, reject] = pending.get(msg.id); pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
    }
  });
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const n = ++id; pending.set(n, [resolve, reject]); ws.send(JSON.stringify({ id: n, method, params }));
  });
  async function evalua(expression) {
    const r = await call("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error("Error en la página.");
    return r.result.value;
  }
  async function espera(test, ms = 25000) {
    return evalua(`new Promise(resolve => {
      const test = () => (${test});
      if (test()) return resolve(true);
      const observer = new MutationObserver(() => { if (test()) { observer.disconnect(); resolve(true); } });
      observer.observe(document.documentElement, { subtree:true, childList:true, attributes:true, characterData:true });
      setTimeout(() => { observer.disconnect(); resolve(false); }, ${ms});
    })`);
  }
  try {
    await call("Page.enable"); await call("Runtime.enable"); await call("Network.enable");
    await call("Page.navigate", { url: `${ORIGIN}/#/acceso` });
    await Promise.race([load, new Promise((_, reject) => setTimeout(() => reject(new Error("Navegación vencida")), 30000))]);
    if (!await espera("!!document.querySelector('#acc-email')")) {
      const diagnostico = await evalua(`({ hash: location.hash, titulo: document.title, texto: document.body.innerText.slice(0, 400) })`);
      console.error("Diagnóstico de interfaz:", JSON.stringify({ ...diagnostico, errores }));
      throw new Error("Formulario no cargó.");
    }
    if (process.env.DIAGNOSTICO_SOLO === "1") { console.log("Formulario local disponible."); return; }
    if (process.env.FORMULARIOS_SOLO === "1") {
      await evalua("location.hash = '#/registro'");
      const registro = await espera("!!document.querySelector('#acc-nombre') && document.querySelector('#acc-pwd')?.minLength === 12");
      await evalua("location.hash = '#/acceso'");
      await espera("!!document.querySelector('#acc-email')");
      await evalua("[...document.querySelectorAll('button')].find(b => b.innerText.includes('Olvidaste'))?.click()");
      const recuperacion = await espera("document.body.innerText.includes('Solicitar código') && !document.querySelector('#acc-pwd')");
      console.log(JSON.stringify({ registroPublicoVisible: registro, recuperacionVisible: recuperacion,
        erroresJavaScript: errores.length, correosEnviados: 0 }));
      if (!registro || !recuperacion || errores.length) process.exitCode = 1;
      return;
    }
    await evalua("document.querySelector('#acc-email').focus()");
    await call("Input.insertText", { text: EMAIL });
    await evalua("document.querySelector('#acc-pwd').focus()");
    await call("Input.insertText", { text: PASS });
    await evalua("document.querySelector('form').requestSubmit()");
    if (!await espera("location.hash.startsWith('#/sistema')", 40000)) throw new Error("Acceso no completado.");
    if (!await espera("document.body.innerText.includes('Mi terminal') || !!document.querySelector('.tm-side')", 30000)) {
      throw new Error("Terminal no cargó.");
    }
    if (process.env.TEST_ADMIN === "si") {
      await evalua("location.hash = '#/admin'");
      if (!await espera("document.body.innerText.includes('Gestión de Usuarios')", 30000)) throw new Error("Administración no cargó.");
      await evalua(`[...document.querySelectorAll('button')].find(b => b.innerText.includes('Nuevo Usuario'))?.click()`);
      if (!await espera("!!document.querySelector('form input[type=email]')", 10000)) throw new Error("Formulario de invitación no cargó.");
      const sinPassword = await evalua("!document.querySelector('form input[type=password]')");
      await evalua("document.querySelector('form input[type=text]').focus()");
      await call("Input.insertText", { text: "Prueba sintética" });
      await evalua("document.querySelector('form input[type=email]').focus()");
      await call("Input.insertText", { text: EMAIL });
      await evalua("document.querySelector('form').requestSubmit()");
      const duplicadoBloqueado = await espera("document.body.innerText.includes('La cuenta ya existe')", 30000);
      console.log(JSON.stringify({ admin: "ok", formularioSinPassword: sinPassword,
        duplicadoBloqueado, corsLocalDeshabilitado: process.env.CORS_LOCAL_DESHABILITADO !== "false", respuestasApi,
        diagnostico: duplicadoBloqueado ? null : await evalua(`({
          hash: location.hash,
          adminVisible: document.body.innerText.includes('Gestión de Usuarios'),
          accesoRestringido: document.body.innerText.includes('Acceso Restringido'),
          invitacionAceptada: document.body.innerText.includes('Cognito aceptó el envío'),
          avisoParcial: document.body.innerText.includes('no se confirmó el envío'),
          formularioValido: document.querySelector('form')?.checkValidity(),
          correoValido: document.querySelector('form input[type=email]')?.validity.valid,
          nombreValido: document.querySelector('form input[type=text]')?.validity.valid,
          errorGenerico: document.body.innerText.includes('No se pudo crear el usuario'),
          errorDatos: document.body.innerText.includes('Datos de invitación inválidos'),
          errorServidor: document.body.innerText.includes('Error 503')
        })`) }));
      if (!sinPassword || !duplicadoBloqueado) process.exitCode = 1;
      return;
    }
    await evalua("location.hash = '#/sistema/mercado'");
    if (!await espera("!!document.querySelector('#tm-fecha option[value=\"2026-11-17\"]')", 30000)) {
      throw new Error("Fecha de mercado no disponible.");
    }
    await evalua(`(() => { const s = document.querySelector('#tm-fecha');
      s.value = '2026-11-17'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    const mercadoDiario = await espera(`document.body.innerText.includes('Capturas de mercado · sesión 2026-11-17')
      && document.body.innerText.includes('Silver diario')
      && document.querySelectorAll('.tm-table tbody tr').length === 15`, 35000);
    const mercadoValidado = mercadoDiario && await evalua(`(() => {
      const filas = [...document.querySelectorAll('.tm-table tbody tr')];
      const wal = filas.find(r => r.innerText.includes('WALMEX'));
      return !!wal && wal.cells[2]?.innerText !== '—' && wal.cells[4]?.innerText !== '—';
    })()`);
    if (!mercadoValidado) {
      const detalleMercado = await evalua(`(() => {
        const w = [...document.querySelectorAll('.tm-table tbody tr')].find(r => r.innerText.includes('WALMEX'));
        return { fecha: document.querySelector('#tm-fecha')?.value,
          filas: document.querySelectorAll('.tm-table tbody tr').length,
          titulo: [...document.querySelectorAll('h2,h3,h4')].map(x => x.innerText).filter(t => /mercado/i.test(t)).slice(0, 3),
          fuenteDiaria: document.body.innerText.includes('Silver diario'), celdasWalmex: w ? [...w.cells].map(c => c.innerText) : [] };
      })()`);
      console.error("Diagnóstico mercado:", JSON.stringify(detalleMercado));
    }
    await evalua("location.hash = '#/sistema/estadistica'");
    const estadisticaVisible = await espera("document.body.innerText.includes('Panel no disponible') || document.body.innerText.includes('Análisis no disponible')", 35000);
    const estadoEstadistica = await evalua(`document.body.innerText.includes('Panel no disponible')
      ? 'panel_no_disponible' : document.body.innerText.includes('Análisis no disponible') ? 'error' : 'no_cargó'`);
    const detalleEstadistica = estadoEstadistica === "error" ? await evalua(`(() => {
      const t = document.body.innerText; const i = t.indexOf('Análisis no disponible');
      return t.slice(i, i + 250);
    })()`) : null;
    await evalua("location.hash = '#/sistema/senales'");
    const senalesBloqueadas = await espera("document.body.innerText.includes('Sección no disponible')", 15000);
    await evalua("location.hash = '#/seguridad'");
    const verificarCorreoVisible = await espera("document.body.innerText.includes('Enviar código al correo')", 15000);
    await evalua("location.hash = '#/ficha'");
    const fichaBloqueada = await espera("document.body.innerText.includes('Ficha no disponible')", 15000);
    console.log(JSON.stringify({ acceso: "ok", terminal: "ok", mercadoDiario: mercadoValidado, estadistica: estadisticaVisible ? estadoEstadistica : "timeout",
      fichaBloqueada, senalesBloqueadas, verificarCorreoVisible,
      corsLocalDeshabilitado: process.env.CORS_LOCAL_DESHABILITADO !== "false", detalleEstadistica, respuestasApi }));
    if (!mercadoValidado || estadoEstadistica !== "panel_no_disponible" || !fichaBloqueada || !senalesBloqueadas || !verificarCorreoVisible) process.exitCode = 1;
  } finally {
    try { await call("Storage.clearDataForOrigin", { origin: ORIGIN, storageTypes: "all" }); } catch {}
    ws.close();
    await fetch(`${DEBUG}/json/close/${tab.id}`).catch(() => {});
  }
}
main().catch((error) => { console.error("React local:", error.message); process.exitCode = 1; });
