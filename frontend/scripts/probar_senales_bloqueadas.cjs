// Comprueba que no se exponen señales sin procedencia validada.
const { CognitoUserPool, CognitoUser, AuthenticationDetails } = require("amazon-cognito-identity-js");
const { POOL, CLIENT, EMAIL, PASS, API } = process.env;
if (![POOL, CLIENT, EMAIL, PASS, API].every(Boolean)) throw new Error("Faltan variables de prueba.");
const user = new CognitoUser({ Username: EMAIL, Pool: new CognitoUserPool({ UserPoolId: POOL, ClientId: CLIENT }) });
user.authenticateUser(new AuthenticationDetails({ Username: EMAIL, Password: PASS }), {
  onFailure: (error) => { console.error("Cognito:", error.code || error.name); process.exitCode = 1; },
  onSuccess: async (session) => {
    try {
      const access = session.getAccessToken().getJwtToken();
      const id = session.getIdToken().getJwtToken();
      async function get(path, token) {
        const r = await fetch(API + path, { headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: AbortSignal.timeout(18000) });
        const data = await r.json();
        return { status: r.status, data };
      }
      const panel = await get("/api/senales/panel?emisora=WALMEX", access);
      const seguimiento = await get("/api/terminal/seguimiento?emisora=WALMEX", access);
      const fueraPlan = await get("/api/terminal/senal?emisora=AMX", access);
      const anonimo = await get("/api/terminal/senal?emisora=WALMEX");
      const idToken = await get("/api/terminal/senal?emisora=WALMEX", id);
      console.log(JSON.stringify({ panel: panel.status, seguimiento: seguimiento.status,
        fueraPlan: fueraPlan.status, sinToken: anonimo.status, idToken: idToken.status }));
      if (panel.status !== 503 || seguimiento.status !== 503 || fueraPlan.status !== 403 ||
          anonimo.status !== 401 || idToken.status !== 401 ||
          !panel.data.detail?.includes("pendientes de validación")) process.exitCode = 1;
    } catch (error) { console.error("Prueba señales:", error.name); process.exitCode = 1; }
  },
});
