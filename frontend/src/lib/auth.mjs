import { CognitoUserPool, CognitoUser, CognitoUserAttribute, AuthenticationDetails } from "amazon-cognito-identity-js";
import { asociarTotp, verificarTotp, activarTotp } from "./totp.mjs";
import { asegurarSesion, solicitarCodigoEmail, verificarCodigoEmail } from "./emailVerification.mjs";
import { registrar, confirmarRegistro, reenviarRegistro } from "./cognitoRegistration.mjs";
import { solicitarRecuperacion, confirmarRecuperacion } from "./cognitoRecovery.mjs";

export const isCognito = true;
export const publicRegistration = import.meta.env.VITE_COGNITO_SELF_SIGNUP === "true";
const listeners = new Set();
let pool;
let pendingChallenge = null;
let pendingTotpEnrollment = null;
function userPool() {
  if (!pool) {
    const UserPoolId = import.meta.env.VITE_COGNITO_POOL_ID;
    const ClientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
    if (!UserPoolId || !ClientId) throw new Error("Falta configurar Cognito.");
    pool = new CognitoUserPool({ UserPoolId, ClientId });
  }
  return pool;
}
function sessionValue(s) {
  if (!s) return null;
  const token = s.getAccessToken();
  // Solo estabiliza la interfaz mientras se carga el perfil. La API valida el JWT.
  return { access_token: token.getJwtToken(), user_id: token.decodePayload()?.sub || null };
}
function emit(value) { for (const f of listeners) f("SESSION", value); }
function callbacks(resolve, user) {
  return {
    onSuccess: (s) => { pendingChallenge = null; emit(sessionValue(s)); resolve({ error: null }); },
    onFailure: (error) => resolve({ error }),
    newPasswordRequired: (_attributes, required) => {
      pendingChallenge = { user, type: "newPassword", required };
      resolve({ challenge: "newPassword", required });
    },
    mfaRequired: () => { pendingChallenge = { user, type: "sms" }; resolve({ challenge: "sms" }); },
    totpRequired: () => { pendingChallenge = { user, type: "totp" }; resolve({ challenge: "totp" }); },
    mfaSetup: () => {
      pendingChallenge = { user, type: "totpSetup" };
      asociarTotp(user).then(
        (secret) => resolve({ challenge: { type: "totpSetup", secret } }),
        (error) => { pendingChallenge = null; resolve({ error }); },
      );
    },
  };
}
const cognito = {
  auth: {
    async getSession() {
      const user = userPool().getCurrentUser();
      if (!user) return { data: { session: null } };
      return new Promise((resolve, reject) => user.getSession((err, s) =>
        err ? reject(err) : resolve({ data: { session: sessionValue(s) } })));
    },
    onAuthStateChange(callback) {
      listeners.add(callback);
      return { data: { subscription: { unsubscribe: () => listeners.delete(callback) } } };
    },
    async signInWithPassword({ email, password }) {
      return new Promise((resolve) => {
        const user = new CognitoUser({ Username: email, Pool: userPool() });
        pendingChallenge = null;
        user.authenticateUser(new AuthenticationDetails({ Username: email, Password: password }), callbacks(resolve, user));
      });
    },
    async completeChallenge(value) {
      const pending = pendingChallenge;
      if (!pending) return { error: new Error("El desafío de acceso venció. Inicia sesión de nuevo.") };
      if (pending.type === "newPassword" && pending.required?.length) {
        return { error: new Error("La cuenta requiere atributos adicionales; contacta al administrador.") };
      }
      return new Promise((resolve) => {
        const cb = callbacks(resolve, pending.user);
        if (pending.type === "newPassword") pending.user.completeNewPasswordChallenge(value, {}, cb);
        else if (pending.type === "totpSetup") verificarTotp(pending.user, value, cb);
        else pending.user.sendMFACode(value, cb, pending.type === "totp" ? "SOFTWARE_TOKEN_MFA" : "SMS_MFA");
      });
    },
    async startTotpEnrollment() {
      const user = userPool().getCurrentUser();
      if (!user) throw new Error("Inicia sesión antes de configurar el autenticador.");
      await asegurarSesion(user);
      pendingTotpEnrollment = user;
      try { return await asociarTotp(user); }
      catch (error) { pendingTotpEnrollment = null; throw error; }
    },
    async finishTotpEnrollment(code) {
      if (!pendingTotpEnrollment) throw new Error("La configuración venció. Comienza de nuevo.");
      await asegurarSesion(pendingTotpEnrollment);
      await activarTotp(pendingTotpEnrollment, String(code ?? "").trim());
      pendingTotpEnrollment = null;
    },
    cancelTotpEnrollment() { pendingTotpEnrollment = null; },
    async startEmailVerification() {
      const user = userPool().getCurrentUser();
      if (!user) throw new Error("Inicia sesión para verificar tu correo.");
      await solicitarCodigoEmail(user);
    },
    async finishEmailVerification(code) {
      const user = userPool().getCurrentUser();
      if (!user) throw new Error("Inicia sesión para verificar tu correo.");
      await verificarCodigoEmail(user, code);
    },
    async resetPasswordForEmail(email) {
      const user = new CognitoUser({ Username: email, Pool: userPool() });
      return solicitarRecuperacion(user);
    },
    async confirmPasswordReset(email, code, password) {
      const user = new CognitoUser({ Username: email, Pool: userPool() });
      return confirmarRecuperacion(user, String(code ?? "").trim(), password);
    },
    async signOut() {
      pendingChallenge = null;
      pendingTotpEnrollment = null;
      userPool().getCurrentUser()?.signOut();
      emit(null);
      return { error: null };
    },
    async signUp({ email, password, options }) {
      if (!publicRegistration) return { error: new Error("El registro público aún no está habilitado.") };
      return registrar(userPool(), CognitoUserAttribute, { email, password, nombre: options?.data?.nombre });
    },
    async confirmRegistration(email, code) {
      return confirmarRegistro(new CognitoUser({ Username: email, Pool: userPool() }), String(code ?? "").trim());
    },
    async resendRegistration(email) {
      return reenviarRegistro(new CognitoUser({ Username: email, Pool: userPool() }));
    },
  },
  async rpc() { return { error: new Error("Los cambios de plan se gestionan desde Administración (Cognito + DynamoDB).") }; },
};

export const authClient = cognito;
