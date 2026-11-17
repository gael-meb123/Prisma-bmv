/**
 * Prisma BMV - Momentos de la Guía Prismi
 * Define las expresiones y los mensajes contextuales según la pantalla activa.
 */

export function guideMoment({ route, phase, selectedTicker, busy = false, error = null, hasSession = false, nombre = "" }) {
  if (busy) {
    return {
      expression: "thinking",
      message: "Procesando boletín regulatorio de la BMV e inferencia IRLS de panel…",
      prompt: "Calculando modelos…"
    };
  }

  if (error) {
    return {
      expression: "unsure",
      message: "Ocurrió una inconsistencia en la consulta. Revisa el estado del Data Lake.",
      prompt: "¿Necesitas ayuda?"
    };
  }

  if (route === "/acceso" || route === "/registro") {
    return {
      expression: "happy",
      prompt: route === "/registro" ? "Crear tu cuenta es gratis" : "¡Bienvenido de vuelta!",
      message: route === "/registro"
        ? "Empiezas con el plan Explorer: monitor de las 15 emisoras y análisis completo de WALMEX."
        : "Escribe tu correo y contraseña. ¿No tienes cuenta? Usa la pestaña «Abrir cuenta»."
    };
  }

  if ((route.startsWith("/sistema") || route.startsWith("/ficha")) && !hasSession) {
    return {
      expression: "unsure",
      prompt: "La terminal necesita sesión",
      message: "Inicia sesión o crea tu cuenta gratis para ver las señales, la serie histórica y la auditoría."
    };
  }

  if (route === "/") {
    return hasSession
      ? {
          expression: "happy",
          prompt: `¡Hola${nombre ? `, ${nombre}` : ""}!`,
          message: "Tu sesión está activa. Usa «Mi terminal» para ir directo a tu resumen."
        }
      : {
          expression: "happy",
          prompt: "¡Hola! ¿Quieres conocer la terminal?",
          message: "Descubre por qué el PPP oficial de la BMV es superior al precio de cierre. Para entrar a la terminal, inicia sesión."
        };
  }

  if (route === "/metodologia") {
    return {
      expression: "idle",
      prompt: "¿Quieres entender los 3 modelos G2?",
      message: "Aquí explicamos el algoritmo Newton-Raphson IRLS y el factor de reversión relativa."
    };
  }

  if (route === "/fuentes") {
    return {
      expression: "idle",
      prompt: "¿Quieres verificar la procedencia oficial?",
      message: "Todos los datos se auditan con hash SHA-256 contra el boletín regulatorio de la BMV."
    };
  }

  if (route === "/planes") {
    return {
      expression: "happy",
      prompt: "¿Dudas sobre qué plan elegir?",
      message: "Explorer es gratuito para WALMEX; Professional desbloquea las 15 emisoras del IPC."
    };
  }

  if (route.startsWith("/sistema")) {
    const em = selectedTicker || "WALMEX";
    const porSeccion = {
      resumen: ["¿Por dónde empezar?", `Este es tu resumen. Pulsa «Explicar» en la gráfica de ${em} y te cuento qué muestra.`, "happy"],
      mercado: ["El monitor de mercado", "Cada fila es una emisora con su PPP oficial. Haz clic en una para analizarla.", "idle"],
      senales: [`¿Analizando ${em}?`, "Cada barra es la probabilidad de un modelo. Pídeme que te explique por qué da ese número.", "thinking"],
      seguimiento: ["La prueba de fuego", "Aquí ves si la señal va acertando. Solo cuenta el resultado en t+5.", "surprised"],
      calidad: ["¿Qué tan confiables son?", "La calibración compara lo que el modelo dice con lo que pasó.", "thinking"],
      gobernanza: ["¿De dónde salen los datos?", "Te explico el camino del boletín de la BMV hasta esta pantalla.", "happy"],
    };
    const [prompt, message, expression] = porSeccion[phase] || porSeccion.resumen;
    return { expression, prompt, message };
  }

  return {
    expression: "idle",
    prompt: "¡Hola! Soy Prismi, tu asistente.",
    message: "Puedo resolver cualquier consulta sobre los modelos econométricos o cotizaciones BMV."
  };
}
