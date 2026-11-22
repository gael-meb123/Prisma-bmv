const { CognitoUserPool, CognitoUser, AuthenticationDetails } = require("amazon-cognito-identity-js");
const { POOL, CLIENT, EMAIL, PASS } = process.env;
const user = new CognitoUser({ Username: EMAIL, Pool: new CognitoUserPool({ UserPoolId: POOL, ClientId: CLIENT }) });
user.authenticateUser(new AuthenticationDetails({ Username: EMAIL, Password: PASS }), {
  async onSuccess(session) {
    try {
      if (!session.isValid() || session.getAccessToken().payload.token_use !== "access") throw new Error();
      if (process.env.API_REGISTRO) {
        const response = await fetch(process.env.API_REGISTRO + "/api/me", {
          headers: { Authorization: "Bearer " + session.getAccessToken().getJwtToken() },
        });
        const profile = await response.json();
        if (response.status !== 200 || profile.rol !== "user" || profile.plan !== "explorer") throw new Error();
      }
    } catch { console.error("Sesión o perfil incorrectos"); process.exitCode = 1; }
    finally { user.signOut(); }
  },
  onFailure() { console.error("Acceso SRP rechazado"); process.exitCode = 1; },
});
