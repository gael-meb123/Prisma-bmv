/**
 * Prisma BMV - Momentos de la Guía Prismi
 * Define las expresiones y los mensajes contextuales según la pantalla activa.
 */

export function guideMoment({ route, phase, selectedTicker, busy = false, error = null, hasSession = false, nombre = "" }) {
  if (busy) {
    return {
      expression: "thinking",
      message: "Consultando datos verificados del Data Lakehouse en AWS…",
      prompt: "Procesando consulta…"
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
        ? "Empiezas con el plan Explorer ($0 MXN): monitor BMV de 35 componentes provisionales y análisis completo de WALMEX."
        : "Escribe tu correo y contraseña de Cognito. ¿No tienes cuenta? Usa la pestaña «Abrir cuenta»."
    };
  }

  if ((route.startsWith("/sistema") || route.startsWith("/ficha")) && !hasSession) {
    return {
      expression: "unsure",
      prompt: "La terminal necesita sesión",
      message: "Inicia sesión o crea tu cuenta gratis para explorar la serie histórica, estadística, observaciones secundarias y gobernanza."
    };
  }

  if (route === "/") {
    return hasSession
      ? {
          expression: "happy",
          prompt: `¡Hola${nombre ? `, ${nombre}` : ""}!`,
          message: "Tu sesión está activa. Usa «Entrar a mi terminal» o pídelo en el icono del mapa para repetir el recorrido guiado."
        }
      : {
          expression: "happy",
          prompt: "¡Hola! ¿Quieres conocer la terminal?",
          message: "Descubre por qué el PPP oficial de la BMV es superior al precio de cierre y cómo opera el lakehouse en AWS."
        };
  }

  if (route === "/metodologia") {
    return {
      expression: "idle",
      prompt: "¿Quieres entender los modelos G2?",
      message: "Aquí explicamos la regresión logística agrupada (IRLS), el factor relativo del panel y la política ¼-Kelly."
    };
  }

  if (route === "/fuentes") {
    return {
      expression: "idle",
      prompt: "¿Quieres verificar la procedencia oficial?",
      message: "Todos los boletines BMV se auditan con hash SHA-256 inmutable en S3 y las observaciones Yahoo se mantienen separadas."
    };
  }

  if (route === "/planes") {
    return {
      expression: "happy",
      prompt: "¿Dudas sobre qué plan elegir?",
      message: "Explorer ($0 MXN) incluye WALMEX y monitor IPC-35; Professional ($399 MXN) y Enterprise ($3,490 MXN) amplían el panel completo."
    };
  }

  if (route.startsWith("/sistema")) {
    const em = selectedTicker || "WALMEX";
    const porSeccion = {
      resumen: ["¿Por dónde empezar?", `Este es tu resumen. Pulsa «Explicar» en la gráfica de ${em} o inicia el recorrido guiado.`, "happy"],
      mercado: ["Monitor base (15) e IPC-35", "Alterna entre el panel base y los 35 componentes provisionales con sectores BMV y cero imputación.", "idle"],
      consenso: ["Consenso G2 (V1–V5)", "Compara de un vistazo si los cinco modelos coinciden o divergen en el archivo histórico Gold.", "thinking"],
      senales: [`¿Analizando ${em}?`, "Cada barra es la probabilidad estadística de un modelo. Pídeme que te explique la cascada de factores.", "thinking"],
      seguimiento: ["La prueba de fuego", "Aquí sigues la trayectoria real sesión por sesión hasta t+5 sin interpolar huecos.", "surprised"],
      calidad: ["¿Qué tan confiables son?", "La calibración compara la probabilidad predicha contra la frecuencia observada fuera de muestra.", "thinking"],
      estadistica: ["Estadística y Yahoo (.MX)", "Explora medidas descriptivas del panel base o IPC-35 y consulta cierres secundarios Yahoo separados del PPP.", "thinking"],
      gobernanza: ["Gobernanza viva en AWS", "Revisa DisparadorDiarioBMV, el avance de la ventana limpia 21/21, hashes SHA-256 y compuertas activas.", "happy"],
    };
    const [prompt, message, expression] = porSeccion[phase] || porSeccion.resumen;
    return { expression, prompt, message };
  }

  return {
    expression: "idle",
    prompt: "¡Hola! Soy Prismi, tu asistente.",
    message: "Puedo ayudarte con el PPP oficial BMV, el universo IPC-35, la gobernanza en AWS y tus planes."
  };
}
