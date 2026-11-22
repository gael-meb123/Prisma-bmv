// Solo usuario sintético. No imprimir claves, códigos, contraseñas ni tokens.
const crypto = require("node:crypto");
const { CognitoUserPool, CognitoUser, AuthenticationDetails } = require("amazon-cognito-identity-js");
const { POOL, CLIENT, EMAIL, PASS } = process.env;
if (![POOL, CLIENT, EMAIL, PASS].every(Boolean)) throw new Error("Faltan variables de prueba.");

function codigo(secret) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const char of secret.replace(/=+$/, "").toUpperCase()) {
    const value = alphabet.indexOf(char);
    if (value < 0) throw new Error("Clave TOTP inválida");
    bits += value.toString(2).padStart(5, "0");
  }
  const key = Buffer.from((bits.match(/.{8}/g) || []).map((x) => parseInt(x, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const hash = crypto.createHmac("sha1", key).update(counter).digest();
  const offset = hash[hash.length - 1] & 15;
  return String((hash.readUInt32BE(offset) & 0x7fffffff) % 1000000).padStart(6, "0");
}

const pool = new CognitoUserPool({ UserPoolId: POOL, ClientId: CLIENT });
function autenticar(secret) {
  const user = new CognitoUser({ Username: EMAIL, Pool: pool });
  return new Promise((resolve, reject) => {
    const cb = {
      onSuccess: (session) => resolve({ user, session }),
      onFailure: reject,
      totpRequired: () => {
        if (!secret) return reject(new Error("MFA estaba habilitado antes de la prueba."));
        user.sendMFACode(codigo(secret), cb, "SOFTWARE_TOKEN_MFA");
      },
    };
    user.authenticateUser(new AuthenticationDetails({ Username: EMAIL, Password: PASS }), cb);
  });
}

let etapa = "inicio";
(async () => {
  const { asociarTotp, activarTotp } = await import("../src/lib/totp.mjs");
  etapa = "acceso inicial";
  const primera = await autenticar();
  etapa = "asociación";
  const secret = await asociarTotp(primera.user);
  etapa = "verificación y preferencia";
  await activarTotp(primera.user, codigo(secret));
  primera.user.signOut();
  // Cognito puede rechazar el mismo código usado en la activación.
  await new Promise((resolve) => setTimeout(resolve, 31000 - (Date.now() % 30000)));
  etapa = "acceso con MFA";
  const segunda = await autenticar(secret);
  etapa = "renovación";
  const renewed = await new Promise((resolve, reject) => segunda.user.refreshSession(
    segunda.session.getRefreshToken(), (error, session) => error ? reject(error) : resolve(session),
  ));
  if (!renewed?.isValid() || !renewed.getAccessToken().getJwtToken()) throw new Error("Renovación fallida.");
  console.log(JSON.stringify({ accesoInicial: "ok", altaTotp: "ok", accesoConTotp: "ok", renovacion: "ok" }));
})().catch((error) => { console.error("Prueba TOTP:", etapa, error.code || error.name || "error"); process.exitCode = 1; });
