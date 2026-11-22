// La verificación se completa en el navegador; no se envían códigos al backend propio.
export function asegurarSesion(user) {
  if (typeof user.getSession !== "function") return Promise.resolve();
  return new Promise((resolve, reject) => user.getSession((error, session) =>
    error || !session?.isValid() ? reject(error || new Error("Sesión inválida.")) : resolve(session)));
}

export async function solicitarCodigoEmail(user) {
  await asegurarSesion(user);
  return new Promise((resolve, reject) => user.getAttributeVerificationCode("email", {
    onSuccess: () => resolve(),
    inputVerificationCode: () => resolve(),
    onFailure: reject,
  }));
}

export async function verificarCodigoEmail(user, code) {
  const limpio = String(code ?? "").trim();
  await asegurarSesion(user);
  return new Promise((resolve, reject) => user.verifyAttribute("email", limpio, {
    onSuccess: () => resolve(),
    onFailure: reject,
  }));
}
