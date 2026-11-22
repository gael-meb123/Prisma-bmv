// Solo prueba aislada: no imprimir credenciales, tokens ni datos personales.
const { CognitoUserPool, CognitoUser, AuthenticationDetails } = require("amazon-cognito-identity-js");
const { POOL, CLIENT, EMAIL, PASS, API } = process.env;
if (![POOL, CLIENT, EMAIL, PASS, API].every(Boolean)) throw new Error("Faltan variables de prueba.");
const user = new CognitoUser({ Username: EMAIL, Pool: new CognitoUserPool({ UserPoolId: POOL, ClientId: CLIENT }) });
user.authenticateUser(new AuthenticationDetails({ Username: EMAIL, Password: PASS }), {
  onFailure: (e) => { console.error("Cognito:", e.code || e.name); process.exitCode = 1; },
  onSuccess: async (session) => {
    try {
      const access = session.getAccessToken().getJwtToken();
      const id = session.getIdToken().getJwtToken();
      const get = (path, token) => fetch(`${API}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {}, signal: AbortSignal.timeout(12000) });
      const path = "/api/terminal/serie?emisora=";
      const ok = await get(path + "WALMEX", access);
      const body = await ok.json();
      const denied = await get(path + "AMX", access);
      const deniedBody = await denied.json();
      const noToken = await get(path + "WALMEX");
      await noToken.text();
      const idToken = await get(path + "WALMEX", id);
      await idToken.text();
      const estadistica = await get("/api/terminal/estadistica?emisora=WALMEX", access);
      const resumenEstadistica = await estadistica.json();
      const estadisticaFueraPlan = await get("/api/terminal/estadistica?emisora=AMX", access);
      await estadisticaFueraPlan.text();
      console.log(JSON.stringify({ serie: ok.status, puntos: body.puntos?.length, fueraPlan: denied.status, detalleFueraPlan: deniedBody.detail,
        sinToken: noToken.status, idToken: idToken.status, ultimoCorte: body.puntos?.at(-1)?.fecha,
        estadistica: estadistica.status, registros: resumenEstadistica.cobertura_historico?.registros,
        panelAusente: resumenEstadistica.cobertura_panel === null, estadisticaFueraPlan: estadisticaFueraPlan.status }));
      if (ok.status !== 200 || !body.puntos?.length || denied.status !== 403 || noToken.status !== 401 || idToken.status !== 401 ||
          estadistica.status !== 200 || resumenEstadistica.cobertura_panel !== null || estadisticaFueraPlan.status !== 403) process.exitCode = 1;
    } catch (e) { console.error("Prueba HTTP falló:", e.message); process.exitCode = 1; }
  },
});
