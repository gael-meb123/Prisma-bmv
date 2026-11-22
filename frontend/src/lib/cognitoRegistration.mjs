export function registrar(pool, Attribute, { email, password, nombre }) {
  if (!nombre?.trim() || nombre.trim().length > 120) return Promise.resolve({ error: new Error("Nombre inválido.") });
  return new Promise((resolve) => pool.signUp(email, password, [
    new Attribute({ Name: "email", Value: email }),
    new Attribute({ Name: "name", Value: nombre.trim() }),
  ], [], (error) => resolve(error ? { error } : { error: null, confirmacionRequerida: true })));
}

export function confirmarRegistro(user, code) {
  if (!/^\d{6}$/.test(code)) return Promise.resolve({ error: new Error("Escribe el código de seis dígitos.") });
  return new Promise((resolve) => user.confirmRegistration(code, false, (error) => resolve({ error: error || null })));
}

export function reenviarRegistro(user) {
  return new Promise((resolve) => user.resendConfirmationCode((error) => resolve({ error: error || null })));
}
