// Prueba temporal: no imprime credenciales ni tokens.
const { CognitoUserPool, CognitoUser, AuthenticationDetails } = require("amazon-cognito-identity-js");
const { POOL, CLIENT, EMAIL, PASS, API } = process.env;
if (![POOL, CLIENT, EMAIL, PASS, API].every(Boolean)) throw new Error("Faltan variables de prueba.");
const pool = new CognitoUserPool({ UserPoolId: POOL, ClientId: CLIENT });
const user = new CognitoUser({ Username: EMAIL, Pool: pool });
user.authenticateUser(new AuthenticationDetails({ Username: EMAIL, Password: PASS }), {
  onFailure: (error) => { console.error("Cognito:", error.code || error.name); process.exitCode = 1; },
  onSuccess: async (session) => {
    try {
      const access = await fetch(`${API}/api/me`, { headers: { Authorization: `Bearer ${session.getAccessToken().getJwtToken()}` } });
      const body = await access.json();
      const id = await fetch(`${API}/api/me`, { headers: { Authorization: `Bearer ${session.getIdToken().getJwtToken()}` } });
      console.log(JSON.stringify({ accessStatus: access.status, plan: body.plan, rol: body.rol,
        emisoras: body.emisoras, idTokenStatus: id.status }));
      if (access.status !== 200 || body.plan !== "explorer" || id.status !== 401) process.exitCode = 1;
    } catch (error) { console.error("HTTP:", error.message); process.exitCode = 1; }
  },
});
