/**
 * Prismi explica cada gráfica de la terminal.
 *
 * Cada función recibe los MISMOS datos que dibuja la gráfica y devuelve:
 *  - titulo:      encabezado del mensaje de Prismi
 *  - texto:       qué muestra, cómo se lee y qué dicen los datos de hoy (sin inventar cifras)
 *  - contexto:    resumen compacto que viaja al backend si el usuario pregunta algo más
 *  - sugerencias: preguntas de seguimiento sugeridas
 *  - expresion:   cara de Prismi para el mensaje
 *
 * Todo se calcula aquí, sin red: funciona aunque no haya llave de Claude.
 * Ninguna explicación recomienda comprar o vender.
 */

const money = (v) =>
  v == null || Number.isNaN(v) ? "—" : `$${Number(v).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const pct = (v, d = 2) => (v == null || Number.isNaN(v) ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(d)}%`);
const prob = (p) => (p == null ? "—" : `${(p * 100).toFixed(1)}%`);

const CONSENSO_TXT = {
  CONSENSO_ALTO_SUBIDA: "todos los modelos se inclinan por subida",
  CONSENSO_ALTO_NO_SUBIDA: "todos los modelos se inclinan por no subida",
  DIVERGENCIA_ALERTA: "los modelos no coinciden (divergencia)",
  CONSENSO_PANEL_G2_SUBIDA: "todos los modelos se inclinan por subida",
  CONSENSO_PANEL_G2_NO_SUBIDA: "todos los modelos se inclinan por no subida",
};

export function textoConsenso(etiqueta) {
  if (!etiqueta) return "sin consenso calculado";
  return CONSENSO_TXT[etiqueta] || (etiqueta.startsWith("DIVERGENCIA") ? "los modelos no coinciden (divergencia)" : etiqueta.replaceAll("_", " ").toLowerCase());
}

const AVISO = "Recuerda: son probabilidades estadísticas, no una recomendación de compra o venta.";

/* Serie PPP ------------------------------------------------------------------ */
export function explicarSerie({ emisora, sector, puntos = [] }) {
  const con = puntos.filter((p) => p.ppp != null);
  const huecos = puntos.length - con.length;
  if (!con.length) {
    return { titulo: `Serie PPP de ${emisora}`, texto: `Aún no hay PPP verificados de ${emisora} para dibujar.`, contexto: "", sugerencias: [], expresion: "unsure" };
  }
  const primero = con[0];
  const ultimo = con[con.length - 1];
  const max = con.reduce((a, b) => (b.ppp > a.ppp ? b : a));
  const min = con.reduce((a, b) => (b.ppp < a.ppp ? b : a));
  const cambio = (ultimo.ppp / primero.ppp - 1) * 100;
  const texto = [
    `Esta gráfica muestra el PPP oficial de ${emisora}${sector ? ` (${sector})` : ""} sesión por sesión, del ${primero.fecha} al ${ultimo.fecha}. Cada punto sale del boletín de la BMV de ese día.`,
    `El último PPP es ${money(ultimo.ppp)} (${ultimo.fecha}); en todo el periodo cambió ${pct(cambio)} desde ${money(primero.ppp)}. El máximo fue ${money(max.ppp)} el ${max.fecha} y el mínimo ${money(min.ppp)} el ${min.fecha}.`,
    huecos
      ? `Hay ${huecos} ${huecos === 1 ? "sesión" : "sesiones"} sin PPP verificado: se ven como un corte en la línea porque no rellenamos datos.`
      : "No hay huecos: la emisora apareció en todos los boletines del periodo.",
    "El rombo verde marca el precio base de la señal más reciente (t). Puedes acercarte arrastrando sobre la gráfica.",
  ].join("\n\n");
  return {
    titulo: `Serie PPP de ${emisora}`,
    texto,
    contexto: `Serie PPP ${emisora}: ${con.length} sesiones con PPP del ${primero.fecha} al ${ultimo.fecha}; último ${money(ultimo.ppp)}; cambio ${pct(cambio)}; máximo ${money(max.ppp)} (${max.fecha}); mínimo ${money(min.ppp)} (${min.fecha}); ${huecos} sesiones sin PPP.`,
    sugerencias: ["¿Qué es el PPP?", `¿Cuál es la señal de ${emisora}?`, "¿Por qué no se rellenan los huecos?"],
    expresion: "idle",
  };
}

/* Variación por sector -------------------------------------------------------- */
export function explicarSectores({ fecha, sectores = [] }) {
  const con = sectores.filter((s) => s.variacion_media_pct != null);
  const sin = sectores.length - con.length;
  if (!con.length) {
    return { titulo: "Variación por sector", texto: "En esta sesión no hay PPP verificados para comparar sectores.", contexto: "", sugerencias: [], expresion: "unsure" };
  }
  const orden = [...con].sort((a, b) => b.variacion_media_pct - a.variacion_media_pct);
  const top = orden[0];
  const bottom = orden[orden.length - 1];
  const suben = con.filter((s) => s.variacion_media_pct > 0).length;
  const texto = [
    `Cada barra es el promedio de cuánto cambió el PPP de las emisoras de un sector frente a la sesión anterior (${fecha}). Verde: el sector subió; rojo: bajó.`,
    `Hoy ${suben} de ${con.length} sectores con datos subieron. El de mayor alza fue ${top.sector} (${pct(top.variacion_media_pct)}) y el de mayor baja ${bottom.sector} (${pct(bottom.variacion_media_pct)}).`,
    sin
      ? `${sin} ${sin === 1 ? "sector no aparece" : "sectores no aparecen"} porque sus emisoras no publicaron PPP en el boletín del día; no se estiman.`
      : "Todos los sectores tuvieron al menos una emisora con PPP verificado.",
    "Ojo: varios sectores tienen una sola emisora, así que su barra es el movimiento de esa emisora.",
  ].join("\n\n");
  return {
    titulo: "Variación media por sector",
    texto,
    contexto: `Sectores ${fecha}: ${orden.map((s) => `${s.sector} ${pct(s.variacion_media_pct)}`).join("; ")}; ${sin} sectores sin PPP.`,
    sugerencias: ["¿Por qué falta un sector?", "¿Qué emisoras hay en cada sector?"],
    expresion: "idle",
  };
}

/* Monitor de cotizaciones ----------------------------------------------------- */
export function explicarMonitor({ fecha, cotizaciones = [] }) {
  const ver = cotizaciones.filter((c) => c.ppp_bmv_mxn != null);
  const aus = cotizaciones.length - ver.length;
  const texto = [
    `Esta tabla es como el estado de cuenta del mercado: una fila por emisora del IPC con su PPP oficial de la sesión ${fecha} y su variación contra la sesión anterior.`,
    `${ver.length} de ${cotizaciones.length} emisoras tienen PPP verificado.${aus ? ` ${aus} no aparecieron en el boletín: se muestran con guion y la etiqueta «Ausente en boletín», sin precio inventado.` : ""}`,
    "Haz clic en una fila para analizar esa emisora en Señales y Seguimiento. El sello SHA-256 de abajo identifica el archivo exacto del boletín del que salieron los precios.",
  ].join("\n\n");
  return {
    titulo: "Monitor de mercado",
    texto,
    contexto: `Monitor ${fecha}: ${ver.length} con PPP, ${aus} ausentes. ${ver.map((c) => `${c.emisora} ${money(c.ppp_bmv_mxn)} (${pct(c.variacion_pct)})`).join("; ")}.`,
    sugerencias: ["¿Qué significa «Ausente en boletín»?", "¿Qué es el sello SHA-256?"],
    expresion: "happy",
  };
}

/* Probabilidades por modelo ---------------------------------------------------- */
export function explicarProbabilidades({ emisora, fecha, modelos = [], consensos = {} }) {
  if (!modelos.length) {
    return { titulo: `Modelos de ${emisora}`, texto: `No hay señal registrada de ${emisora} para esta fecha (la ventana de 21 sesiones puede estar incompleta).`, contexto: "", sugerencias: [], expresion: "unsure" };
  }
  const validos = modelos.filter((m) => m.valida);
  const arriba = validos.filter((m) => m.probabilidad >= 0.5);
  const ps = validos.map((m) => m.probabilidad);
  const g2 = consensos.G2 ? `En la segunda generación (G2), ${textoConsenso(consensos.G2)}.` : "";
  const g1 = consensos.G1 ? ` En la primera generación (G1, solo WALMEX), ${textoConsenso(consensos.G1)}.` : "";
  const texto = [
    `Cada barra es la probabilidad que calcula un modelo de que el PPP de ${emisora} dentro de 5 sesiones (t+5) sea mayor que el de hoy (señal del ${fecha}).`,
    "La línea punteada marca 50 %: a la derecha (verde) el modelo se inclina por subida; a la izquierda (rojo), por no subida. Entre más lejos del 50 %, más convencido está.",
    `Hoy ${arriba.length} de ${validos.length} modelos están por encima de 50 %; las probabilidades van de ${prob(Math.min(...ps))} a ${prob(Math.max(...ps))}. ${g2}${g1}`,
    "Que estén cerca de 50 % significa que la señal es débil: el modelo ve casi tantos motivos para subir como para no subir.",
    AVISO,
  ].join("\n\n");
  return {
    titulo: `Probabilidad por modelo · ${emisora}`,
    texto,
    contexto: `Señal ${emisora} ${fecha}: ${modelos.map((m) => `${m.nombre} ${prob(m.probabilidad)}${m.valida ? "" : " (anulada)"}`).join("; ")}. Consenso G2: ${consensos.G2 || "—"}; G1: ${consensos.G1 || "—"}.`,
    sugerencias: ["¿Por qué los modelos no coinciden?", "¿Qué diferencia hay entre V1 y V4?", "¿Qué es el consenso?"],
    expresion: "thinking",
  };
}

/* Descomposición del factor clave ---------------------------------------------- */
export function explicarFactor({ emisora, factor }) {
  if (!factor) {
    return { titulo: "Factor clave", texto: "No hay señal G2 para descomponer en esta fecha.", contexto: "", sugerencias: [], expresion: "unsure" };
  }
  const c = factor.contribuciones || {};
  const claves = Object.keys(c);
  if (!claves.length) {
    return { titulo: "Factor clave", texto: factor.lectura, contexto: factor.lectura, sugerencias: ["¿Qué es ret_10_rel_panel?"], expresion: "unsure" };
  }
  const mayor = claves.filter((k) => k !== "intercepto").reduce((a, b) => (Math.abs(c[b]) > Math.abs(c[a]) ? b : a));
  const NOMBRE = { ret_10: "el retorno de 10 sesiones", ret_10_rel_panel: "el retorno relativo al panel", volatilidad_20: "la volatilidad de 20 sesiones", intercepto: "el intercepto" };
  const texto = [
    `Esta cascada abre la "caja" del modelo ${factor.nombre}: muestra cuánto empuja cada variable la probabilidad de ${emisora}. Las barras verdes empujan hacia subida y las rojas hacia no subida; la barra turquesa es la suma.`,
    `La suma da ${factor.log_odds_total >= 0 ? "+" : ""}${factor.log_odds_total?.toFixed(4)} en log-odds, que equivale a una probabilidad de ${prob(factor.probabilidad_reconstruida)}. Lo que más pesa hoy es ${NOMBRE[mayor] || mayor} (${c[mayor] >= 0 ? "+" : ""}${c[mayor].toFixed(4)}).`,
    `El retorno relativo al panel de ${emisora} es ${factor.ret_rel_pp >= 0 ? "+" : ""}${factor.ret_rel_pp?.toFixed(2)} puntos porcentuales${factor.z_rel != null ? ` (${factor.z_rel >= 0 ? "+" : ""}${factor.z_rel.toFixed(2)} desviaciones respecto a su propia historia)` : ""}. ${factor.lectura}`,
    "La descomposición usa los coeficientes congelados del registro oficial; por redondeo puede diferir unas milésimas de la probabilidad registrada.",
  ].join("\n\n");
  return {
    titulo: `¿Por qué ${factor.nombre} da ${prob(factor.probabilidad_reconstruida)}?`,
    texto,
    contexto: `Descomposición ${factor.nombre} ${emisora}: ${claves.map((k) => `${k} ${c[k].toFixed(4)}`).join("; ")}; total ${factor.log_odds_total?.toFixed(4)} ⇒ p ${prob(factor.probabilidad_reconstruida)}; ret_10_rel_panel ${factor.ret_rel_pp?.toFixed(2)} pp; z ${factor.z_rel?.toFixed(2)}. ${factor.lectura}`,
    sugerencias: ["¿Qué es ret_10_rel_panel?", "¿Qué es el log-odds?", "¿Qué es la reversión a la media?"],
    expresion: "thinking",
  };
}

/* Trayectoria t0 → t+5 ---------------------------------------------------------- */
export function explicarTrayectoria({ emisora, fecha_senal, trayectoria = [], resumen, modelos = [] }) {
  if (!resumen) {
    return { titulo: "Seguimiento t+5", texto: `Todavía no hay señales de ${emisora} en seguimiento.`, contexto: "", sugerencias: [], expresion: "unsure" };
  }
  const obs = trayectoria.filter((t) => t.estado === "OBSERVADO" && t.paso !== "t0");
  const huecos = trayectoria.filter((t) => t.estado === "HUECO_DOCUMENTADO");
  const futuros = trayectoria.filter((t) => t.estado === "FUTURO");
  const ultimo = obs[obs.length - 1];
  const resuelta = resumen.estado === "RESUELTA_T+5";
  const aciertos = modelos.filter((m) => (resuelta ? m.acierto_t5 : m.acierto_parcial));
  const texto = [
    `Aquí seguimos la señal que se emitió el ${fecha_senal} para ${emisora}, con PPP base de ${money(resumen.ppp_base)}. Cada punto es cuánto ha cambiado el PPP desde ese día en las siguientes sesiones (t+1, t+2… hasta t+5 = ${resumen.fecha_objetivo}).`,
    ultimo
      ? `Al ${ultimo.fecha} (${ultimo.paso}) el PPP va ${pct(ultimo.retorno_pct)} contra la base.`
      : "Todavía no hay sesiones posteriores con PPP.",
    resuelta
      ? `La señal ya se resolvió con el PPP de t+5: ${aciertos.length} de ${modelos.length} modelos acertaron la dirección.`
      : `Va en ${obs.length} de 5 sesiones. Si hoy se cerrara, ${resumen.modelos_acertando} de ${resumen.modelos_con_precio} modelos irían acertando, pero solo cuenta el resultado en t+5.`,
    [
      futuros.length ? `Los círculos grises son sesiones que aún no ocurren (${futuros.length}).` : "",
      huecos.length ? `Las X ámbar son sesiones en las que ${emisora} no apareció en el boletín: no se interpolan.` : "",
    ]
      .filter(Boolean)
      .join(" "),
  ]
    .filter(Boolean)
    .join("\n\n");
  return {
    titulo: `Seguimiento de la señal del ${fecha_senal}`,
    texto,
    contexto: `Seguimiento ${emisora} señal ${fecha_senal}: base ${money(resumen.ppp_base)}, objetivo ${resumen.fecha_objetivo}, estado ${resumen.estado}; trayectoria ${trayectoria.map((t) => `${t.paso} ${t.estado === "OBSERVADO" ? pct(t.retorno_pct) : t.estado}`).join(", ")}; modelos: ${modelos.map((m) => `${m.nombre} ${prob(m.probabilidad)} ${m.prediccion} ${resuelta ? (m.acierto_t5 ? "acertó" : "falló") : m.acierto_parcial == null ? "sin precio" : m.acierto_parcial ? "va acertando" : "va fallando"}`).join("; ")}.`,
    sugerencias: ["¿Por qué solo cuenta t+5?", "¿Qué pasa si falta el PPP en t+5?", "¿Cómo van los aciertos?"],
    expresion: resuelta ? "surprised" : "idle",
  };
}

/* Marcador por modelo ------------------------------------------------------------ */
export function explicarMarcador({ fecha_corte, modelos = [] }) {
  if (!modelos.length) {
    return { titulo: "Marcador", texto: "Aún no hay señales con resultado para comparar modelos.", contexto: "", sugerencias: [], expresion: "unsure" };
  }
  const conT5 = modelos.filter((m) => m.resueltas_t5 > 0);
  const mejorParcial = modelos.reduce((a, b) => ((b.tasa_parcial_pct ?? -1) > (a.tasa_parcial_pct ?? -1) ? b : a));
  const mejorBrier = conT5.length ? conT5.reduce((a, b) => ((b.brier_t5 ?? 9) < (a.brier_t5 ?? 9) ? b : a)) : null;
  const resueltas = Math.max(0, ...modelos.map((m) => m.resueltas_t5));
  const texto = [
    `El marcador compara a los modelos con lo que realmente pasó (corte ${fecha_corte}). La barra turquesa es el porcentaje de señales que "van acertando" con el último precio disponible; la azul marino, el porcentaje de aciertos ya resueltos en t+5.`,
    `La mejor tasa parcial es la de ${mejorParcial.nombre} (${mejorParcial.tasa_parcial_pct?.toFixed(1)} %, ${mejorParcial.aciertos_parciales} de ${mejorParcial.en_seguimiento}).${mejorBrier ? ` Con el Brier score (menor es mejor) destaca ${mejorBrier.nombre} con ${mejorBrier.brier_t5?.toFixed(4)}.` : ""}`,
    `Cuidado al leerlo: hay pocas señales resueltas (hasta ${resueltas} por modelo). Con tan pocas, un solo acierto o error mueve la tasa decenas de puntos. La línea de 50 % es lo que lograría una moneda al aire.`,
  ].join("\n\n");
  return {
    titulo: "Marcador por modelo",
    texto,
    contexto: `Marcador ${fecha_corte}: ${modelos.map((m) => `${m.nombre} parcial ${m.tasa_parcial_pct?.toFixed(1)}% (${m.aciertos_parciales}/${m.en_seguimiento}), t+5 ${m.aciertos_t5}/${m.resueltas_t5}, Brier ${m.brier_t5 ?? "—"}`).join("; ")}.`,
    sugerencias: ["¿Qué es el Brier score?", "¿Por qué pocas señales son inestables?"],
    expresion: "thinking",
  };
}

/* Calibración (Gael · métricas institucionales) ------------------------------------ */
export function explicarCalibracion({ etiqueta, bins = [], filas = [] }) {
  const lejos = bins.length
    ? bins.reduce((a, b) => (Math.abs(b.frecuencia_observada - b.prob_media) > Math.abs(a.frecuencia_observada - a.prob_media) ? b : a))
    : null;
  const texto = [
    `El diagrama de confiabilidad responde: cuando ${etiqueta} dice "55 %", ¿de verdad sube el 55 % de las veces? Si el modelo está bien calibrado, los puntos caen sobre la diagonal punteada.`,
    lejos
      ? `El punto más alejado de la diagonal está en una probabilidad predicha de ${(lejos.prob_media * 100).toFixed(1)} %, con frecuencia observada de ${(lejos.frecuencia_observada * 100).toFixed(1)} %${lejos.n != null ? ` (${lejos.n} ${lejos.n === 1 ? "observación" : "observaciones"})` : ""}.`
      : "",
    bins.some((b) => b.n != null)
      ? (() => {
          const total = bins.reduce((s, b) => s + (b.n || 0), 0);
          const centro = bins.filter((b) => b.prob_media >= 0.4 && b.prob_media <= 0.6).reduce((s, b) => s + (b.n || 0), 0);
          const pocos = bins.filter((b) => b.n != null && b.n < 20);
          return `Lee los puntos según su tamaño: ${centro} de ${total} observaciones están entre 40 % y 60 %, donde la curva sigue de cerca la diagonal.${pocos.length ? ` ${pocos.length === 1 ? "Un tramo tiene" : `${pocos.length} tramos tienen`} menos de 20 observaciones; ahí un solo caso mueve mucho la frecuencia, así que no hay que sobreinterpretarlo.` : ""}`;
        })()
      : "",
    filas.length
      ? `En la tabla, la exactitud lleva su intervalo de confianza al 95 %; el BSS compara contra adivinar con la frecuencia histórica (positivo = mejor que eso) y el ECE mide el error de calibración (menor es mejor).`
      : "",
  ]
    .filter(Boolean)
    .join("\n\n");
  return {
    titulo: "Calidad y calibración de los modelos",
    texto,
    contexto: `Calibración ${etiqueta}: ${bins.map((b) => `${(b.prob_media * 100).toFixed(1)}%→${(b.frecuencia_observada * 100).toFixed(1)}% (n=${b.n ?? "?"})`).join(", ")}. Métricas: ${filas.map((f) => `${f.label} acc ${Number(f.accuracy_pct).toFixed(2)}% BSS ${Number(f.bss_pct).toFixed(2)}% ECE ${Number(f.ece).toFixed(4)}`).join("; ")}.`,
    sugerencias: ["¿Qué es el BSS?", "¿Qué significa estar calibrado?"],
    expresion: "thinking",
  };
}

/* Gobernanza AWS -------------------------------------------------------------------- */
export function explicarGobernanza({ nodos = [] }) {
  const texto = [
    "Este diagrama muestra el camino de los datos, de izquierda a derecha. El grosor de cada banda indica cuánto fluye por ella.",
    "EventBridge despierta a la Lambda a las 16:45 (hora de la Ciudad de México) de lunes a viernes. La Lambda descarga el boletín de la BMV y lo guarda intacto en S3 Bronze con su huella SHA-256; luego escribe los 15 PPP en Silver y las señales en Gold. Athena consulta Silver y Gold con SQL, y esta terminal lee de ahí.",
    "CloudWatch guarda los registros de cada ejecución durante 7 días e IAM limita qué puede leer o escribir cada pieza. Pasa el cursor por cada bloque para ver su configuración.",
  ].join("\n\n");
  return {
    titulo: "¿De dónde salen los datos?",
    texto,
    contexto: `Gobernanza AWS: ${nodos.map((n) => `${n.nombre} (${n.detalle})`).join("; ")}.`,
    sugerencias: ["¿Qué es Bronze, Silver y Gold?", "¿Para qué sirve el SHA-256?"],
    expresion: "happy",
  };
}

/** Dispara la explicación: Guide.jsx la escucha y abre el chat de Prismi. */
export function pedirExplicacion(explicacion) {
  window.dispatchEvent(new CustomEvent("prisma:explain", { detail: explicacion }));
}
