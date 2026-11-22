// Prueba únicamente el perfil sintético; no imprimir tokens ni listados.
const { CognitoUserPool, CognitoUser, AuthenticationDetails } = require("amazon-cognito-identity-js");
const { POOL, CLIENT, EMAIL, PASS, API, TEST_ADMIN } = process.env;
if (![POOL, CLIENT, EMAIL, PASS, API, TEST_ADMIN].every(Boolean)) throw new Error("Faltan variables.");
const user = new CognitoUser({ Username: EMAIL, Pool: new CognitoUserPool({ UserPoolId: POOL, ClientId: CLIENT }) });
user.authenticateUser(new AuthenticationDetails({ Username: EMAIL, Password: PASS }), {
  onFailure: (error) => { console.error("Cognito:", error.code || error.name); process.exitCode = 1; },
  onSuccess: async (session) => {
    try {
      const token = session.getAccessToken().getJwtToken();
      async function call(path, method = "GET", body, authenticated = true) {
        const r = await fetch(API + path, { method, headers: {
          ...(authenticated ? { Authorization: `Bearer ${token}` } : {}),
          ...(body ? { "Content-Type": "application/json" } : {}),
        }, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(15000) });
        return { status: r.status, data: await r.json() };
      }
      const me = await call("/api/me");
      if (me.status !== 200 || !me.data.id) throw new Error("Perfil no disponible");
      const path = "/api/admin/usuarios/" + encodeURIComponent(me.data.id);
      const listado = await call("/api/admin/usuarios");
      const sinToken = await call("/api/admin/usuarios", "GET", undefined, false);
      if (TEST_ADMIN === "no") {
        const cambio = await call(path, "PATCH", { plan: "professional" });
        const alta = await call("/api/admin/usuarios", "POST", { nombre: "Prueba", email: EMAIL, rol: "user", plan: "explorer" });
        console.log(JSON.stringify({ rol: "user", listado: listado.status, cambio: cambio.status, alta: alta.status, sinToken: sinToken.status }));
        if (listado.status !== 403 || cambio.status !== 403 || alta.status !== 403 || sinToken.status !== 401) process.exitCode = 1;
      } else {
        const democion = await call(path, "PATCH", { rol: "user" });
        const invalido = await call(path, "PATCH", { plan: "inexistente" });
        const cambio = await call(path, "PATCH", { plan: "professional" });
        const restaurar = await call(path, "PATCH", { plan: "explorer" });
        const falta = await call("/api/admin/usuarios/prueba-sintetica-inexistente", "PATCH", { plan: "explorer" });
        const altaInvalida = await call("/api/admin/usuarios", "POST", { nombre: "Prueba", email: "invalido", rol: "user", plan: "explorer" });
        const altaExistente = await call("/api/admin/usuarios", "POST", { nombre: "Prueba", email: EMAIL, rol: "user", plan: "explorer" });
        console.log(JSON.stringify({ rol: "admin", listado: listado.status, sinToken: sinToken.status,
          democion: democion.status, invalido: invalido.status, cambio: cambio.status,
          planDevuelto: cambio.data.plan, restaurar: restaurar.status, inexistente: falta.status,
          altaInvalida: altaInvalida.status, altaExistente: altaExistente.status }));
        if (listado.status !== 200 || !Array.isArray(listado.data) || sinToken.status !== 401 ||
            democion.status !== 400 || invalido.status !== 422 || cambio.status !== 200 ||
            cambio.data.plan !== "professional" || restaurar.status !== 200 || falta.status !== 409 ||
            altaInvalida.status !== 422 || altaExistente.status !== 409) process.exitCode = 1;
      }
    } catch (error) { console.error("Prueba admin:", error.name); process.exitCode = 1; }
  },
});
