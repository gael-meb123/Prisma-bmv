/**
 * Prisma BMV - Recorrido Guiado Interactivo por Prismi
 */

const DONE_KEY = "prisma.tour.done";

export const TOUR_STEPS = [
  {
    id: "greeting",
    route: "/",
    target: ".hero-copy h1",
    expression: "happy",
    title: "Bienvenido a Prisma BMV",
    body: "Soy Prismi, tu asistente cuantitativo. Te acompañaré a conocer la terminal bursátil y los modelos de panel.",
    emphasis: "Iniciemos el recorrido",
    placement: "bottom"
  },
  {
    id: "terminal-entry",
    route: "/",
    target: ".hero-copy .button-primary",
    expression: "happy",
    title: "Acceso a la Terminal",
    body: "Haz clic en este botón para ingresar al espacio analítico dual con datos en vivo.",
    emphasis: "Entrar a la Terminal",
    placement: "bottom"
  },
  {
    id: "workspace-visual",
    route: "/sistema",
    target: ".workspace-map",
    expression: "happy",
    title: "Gráfica Financiera Plotly",
    body: "En este panel visualizas la serie de tiempo interactiva del Precio Promedio Ponderado oficial.",
    emphasis: "Gráfica interactiva de alta precisión",
    placement: "right"
  },
  {
    id: "workspace-analysis",
    route: "/sistema",
    target: ".workspace-panel",
    expression: "thinking",
    title: "Consenso Econométrico G2",
    body: "Aquí se evalúa la probabilidad de subida a 5 sesiones con los 3 modelos y el factor de reversión relativa.",
    emphasis: "Inferencia a 5 sesiones (t+5)",
    placement: "left"
  }
];

export function tourDone() {
  return localStorage.getItem(DONE_KEY) === "true";
}

export function markTourDone() {
  localStorage.setItem(DONE_KEY, "true");
}
