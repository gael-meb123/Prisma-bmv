function esperar(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", cancelar);
      resolve();
    }, ms);
    function cancelar() {
      clearTimeout(timer);
      reject(signal.reason);
    }
    signal?.addEventListener("abort", cancelar, { once: true });
  });
}

// Solo llamadas de lectura autorizadas por el llamador. Nunca reintenta escrituras.
export async function fetchLectura(url, options, { reintentar = false, fetchImpl = fetch, esperarImpl = esperar } = {}) {
  const primera = await fetchImpl(url, options);
  if (!reintentar || (options.method || "GET").toUpperCase() !== "GET" ||
      ![429, 503].includes(primera.status)) return primera;
  await primera.body?.cancel();
  await esperarImpl(600, options.signal);
  return fetchImpl(url, options);
}
