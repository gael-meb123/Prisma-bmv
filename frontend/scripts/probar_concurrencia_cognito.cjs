// Prueba acotada: cuatro solicitudes simultáneas de un usuario sintético.
const { CognitoUserPool, CognitoUser, AuthenticationDetails } = require("amazon-cognito-identity-js");
const { POOL, CLIENT, EMAIL, PASS, API } = process.env;
if (![POOL, CLIENT, EMAIL, PASS, API].every(Boolean)) throw new Error("Faltan variables de prueba.");
const user = new CognitoUser({ Username: EMAIL, Pool: new CognitoUserPool({ UserPoolId: POOL, ClientId: CLIENT }) });
user.authenticateUser(new AuthenticationDetails({ Username: EMAIL, Password: PASS }), {
  onFailure: (error) => { console.error("Cognito:", error.code || error.name); process.exitCode = 1; },
  onSuccess: async (session) => {
    const token = session.getAccessToken().getJwtToken();
    const solicitudes = ["WALMEX", "AMX", "WALMEX", "AMX"];
    try {
      const resultados = await Promise.all(solicitudes.map(async (emisora) => {
        const inicio = Date.now();
        const r = await fetch(`${API}/api/terminal/serie?emisora=${emisora}`, {
          headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(20000),
        });
        await r.text();
        return { emisora, status: r.status, ms: Date.now() - inicio };
      }));
      console.log(JSON.stringify({ solicitudes: resultados }));
      if (resultados.some((r) => r.status !== (r.emisora === "WALMEX" ? 200 : 403))) process.exitCode = 1;
    } catch (error) {
      console.error("Prueba concurrente:", error.name);
      process.exitCode = 1;
    }
  },
});
