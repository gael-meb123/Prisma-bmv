export function solicitarRecuperacion(user) {
  return new Promise((resolve) => user.forgotPassword({
    onSuccess: () => resolve({ error: null }),
    inputVerificationCode: () => resolve({ error: null }),
    onFailure: (error) => resolve({ error }),
  }));
}

export function confirmarRecuperacion(user, code, password) {
  if (!/^\d{6}$/.test(code)) return Promise.resolve({ error: new Error("Escribe el código de seis dígitos.") });
  return new Promise((resolve) => user.confirmPassword(code, password, {
    onSuccess: () => resolve({ error: null }),
    onFailure: (error) => resolve({ error }),
  }));
}
