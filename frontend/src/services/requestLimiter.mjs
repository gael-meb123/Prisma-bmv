// Limita las peticiones HTTP de la interfaz sin compartir datos entre usuarios.
export function crearLimitador(limite = 2) {
  if (!Number.isInteger(limite) || limite < 1) throw new Error("Límite inválido");
  let activas = 0;
  const cola = [];
  const aborto = () => new DOMException("Solicitud cancelada", "AbortError");
  function avanzar() {
    while (activas < limite && cola.length) {
      const entrada = cola.shift();
      entrada.signal?.removeEventListener("abort", entrada.cancelar);
      if (entrada.signal?.aborted) { entrada.reject(aborto()); continue; }
      activas++;
      entrada.resolve(() => { activas--; avanzar(); });
    }
  }
  return async function limitar(tarea, signal) {
    if (signal?.aborted) throw aborto();
    const liberar = await new Promise((resolve, reject) => {
      const entrada = { resolve, reject, signal };
      entrada.cancelar = () => {
        const i = cola.indexOf(entrada);
        if (i >= 0) { cola.splice(i, 1); reject(aborto()); }
      };
      signal?.addEventListener("abort", entrada.cancelar, { once: true });
      cola.push(entrada);
      avanzar();
    });
    try {
      if (signal?.aborted) throw aborto();
      return await tarea();
    } finally {
      liberar();
    }
  };
}
