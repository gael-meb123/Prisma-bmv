// Devuelve resultados solo al terminar el recorrido. Nunca una página parcial.
export async function recorrerHistorial(cargar, campo, signal) {
  const valores = new Map();
  let despues, hash, ultima;
  const cursores = new Set();
  do {
    signal?.throwIfAborted();
    const pagina = await cargar(despues);
    if (!pagina || !Array.isArray(pagina[campo]) || !/^[a-f0-9]{64}$/.test(pagina.sha256_instantanea)
        || !Object.hasOwn(pagina, "siguiente")) throw new Error("Página histórica inválida.");
    if (hash && hash !== pagina.sha256_instantanea) throw new Error("La instantánea cambió durante la consulta. Vuelve a consultar.");
    hash = pagina.sha256_instantanea;
    for (const valor of pagina[campo]) {
      const clave = campo === "fechas" ? valor : valor.fecha;
      if (typeof clave !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(clave)) throw new Error("Fecha histórica inválida.");
      if (valores.has(clave) && JSON.stringify(valores.get(clave)) !== JSON.stringify(valor)) {
        throw new Error("Conflicto entre páginas históricas.");
      }
      valores.set(clave, valor);
    }
    const siguiente = pagina.siguiente;
    if (siguiente !== null && (typeof siguiente !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(siguiente)
        || (despues && siguiente <= despues) || cursores.has(siguiente))) throw new Error("Cursor histórico inválido.");
    cursores.add(siguiente);
    despues = siguiente;
    ultima = pagina;
  } while (despues !== null);
  signal?.throwIfAborted();
  return { ...ultima, [campo]: [...valores.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, v]) => v),
    cobertura: "recorrido completo de páginas disponibles; puede requerir actualización por capturas tardías" };
}
