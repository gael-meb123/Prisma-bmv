// La clave TOTP permanece solo en memoria; nunca se guarda ni se envía a terceros.
export function asociarTotp(user) {
  return new Promise((resolve, reject) => user.associateSoftwareToken({
    associateSecretCode: (secret) => secret ? resolve(secret) : reject(new Error("Cognito no devolvió una clave TOTP.")),
    onFailure: reject,
  }));
}

export function verificarTotp(user, code, callbacks) {
  user.verifySoftwareToken(code, "Prisma BMV", callbacks);
}

export function activarTotp(user, code) {
  return new Promise((resolve, reject) => verificarTotp(user, code, {
    onFailure: reject,
    onSuccess: (result) => {
      if (result?.Status !== "SUCCESS") {
        reject(new Error("Cognito no confirmó el código TOTP."));
        return;
      }
      user.setUserMfaPreference(null, { Enabled: true, PreferredMfa: true }, (error) => {
        if (error) reject(new Error("El autenticador fue verificado, pero no se pudo activar como MFA preferido. Revisa la configuración de la cuenta."));
        else resolve();
      });
    },
  }));
}
