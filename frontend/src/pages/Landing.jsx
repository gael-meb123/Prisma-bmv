import React, { useEffect } from "react";
import {
  ArrowRight,
  BarChart3,
  Check,
  CreditCard,
  Database,
  Fingerprint,
  LineChart,
  Lock,
  MessageCircle,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Timer,
  XCircle,
  CheckCircle2,
} from "lucide-react";
import { Header, Footer } from "../components/Header";
import { HeroIllustration, MiniSpark, PlanCardArt, ShieldArt, StepIcon, WaveDivider } from "../components/Illustrations";
import { useAccount } from "../hooks/useAccount";
import { useMarketStatus } from "../hooks/useMarketStatus";
import { PLANS } from "../plans.mjs";
import { formatMoney, formatPct } from "../utils/presentation.mjs";

const PASOS = [
  ["boletin", "Boletín oficial", "Cada día hábil a las 16:45 descargamos el boletín de la BMV y guardamos su huella SHA-256."],
  ["lago", "Datos auditables", "El HTML queda intacto en Bronze; los 15 PPP pasan a Silver sin rellenar huecos."],
  ["modelo", "Modelos de panel", "Cinco modelos G2 estiman la probabilidad de que el PPP suba en 5 sesiones."],
  ["auditoria", "Auditoría t+5", "Cada señal se compara con el PPP real cinco sesiones después. Los errores no se borran."],
];

const FAQS = [
  [
    "¿Por qué el PPP y no el precio de cierre?",
    "El último hecho puede moverse con una orden pequeña en la subasta de cierre. El PPP pondera por volumen todas las operaciones de la sesión: refleja dónde se negoció realmente el día y es el precio de referencia que publica la BMV.",
  ],
  [
    "¿Qué significa que no imputamos datos?",
    "Si una emisora no aparece en el boletín del día, el hueco se registra tal cual. No se rellena con el precio anterior ni con estimaciones; si falta una sesión de la ventana de cálculo, ese día la emisora no recibe señal.",
  ],
  [
    "¿Prisma BMV me dice qué comprar?",
    "No. La terminal muestra probabilidades estadísticas y cómo se han comportado en el pasado. No emite recomendaciones de compra o venta ni asesoría de inversión.",
  ],
  [
    "¿Qué incluye el plan gratuito Explorer?",
    "El monitor de las 15 emisoras con su PPP oficial, el análisis completo de WALMEX, el sello SHA-256 de cada boletín y Prismi, el asistente que te explica cada gráfica.",
  ],
];

function emisoraConMayor(cotizaciones = [], signo = 1) {
  const validas = cotizaciones.filter((c) => c.variacion_pct != null);
  if (!validas.length) return null;
  return validas.reduce((best, c) => (signo * c.variacion_pct > signo * best.variacion_pct ? c : best));
}

export function Landing() {
  const account = useAccount();
  const status = useMarketStatus();
  const hasSession = Boolean(account.session);
  const mercado = status?.mercado;
  const cot = mercado?.cotizaciones || [];
  const walmex = cot.find((c) => c.emisora === "WALMEX");
  const alza = emisoraConMayor(cot, 1);
  const baja = emisoraConMayor(cot, -1);
  const k = mercado?.kpis || {};

  // Enlaces internos tipo "#/#como-funciona": desplazarse a la sección.
  useEffect(() => {
    const ancla = location.hash.split("#")[2];
    if (ancla) document.getElementById(ancla)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const quick = [
    [BarChart3, "Ver el mercado", "#/sistema/mercado"],
    [LineChart, "Señales del día", "#/sistema/senales"],
    [Timer, "Seguimiento t+5", "#/sistema/seguimiento"],
    [CreditCard, "Comparar planes", "#/planes"],
    [MessageCircle, "Hablar con Prismi", null],
  ];

  return (
    <>
      <Header />

      <main id="main-content" className="landing">
        {/* ------------------------------------------------------------ Hero */}
        <section className="bk-hero">
          <div className="bk-container bk-hero-grid">
            <div>
              <span className="bk-chip" style={{ marginBottom: 18 }}>
                <Sparkles size={14} /> Boletín oficial BMV · datos verificados con SHA-256
              </span>
              <h1 data-tour="hero">
                Tu banca de inteligencia bursátil sobre el <em>PPP oficial</em>
              </h1>
              <p className="bk-hero-lead">
                Consulta el Precio Promedio Ponderado de las 15 emisoras del IPC, revisa qué probabilidad asigna cada modelo
                a que suba en 5 sesiones y comprueba cómo les fue después. Todo con la claridad de tu banca en línea.
              </p>
              <div className="bk-hero-ctas">
                {hasSession ? (
                  <a href="#/sistema" data-tour="cta-sistema" className="bk-btn bk-btn-primary bk-btn-lg">
                    Entrar a mi terminal <ArrowRight size={17} />
                  </a>
                ) : (
                  <>
                    <a href="#/registro" className="bk-btn bk-btn-primary bk-btn-lg">
                      Abrir mi cuenta gratis <ArrowRight size={17} />
                    </a>
                    <a href="#/sistema" data-tour="cta-sistema" className="bk-btn bk-btn-outline bk-btn-lg">
                      <Lock size={16} /> Ingresar a la terminal
                    </a>
                  </>
                )}
              </div>
              <div className="bk-trust">
                <span><Fingerprint size={17} /> Huella SHA-256 por boletín</span>
                <span><ShieldCheck size={17} /> Cero imputación</span>
                <span><Database size={17} /> Lakehouse en AWS</span>
              </div>
            </div>

            <div className="bk-hero-art">
              <HeroIllustration ppp={walmex?.ppp_bmv_mxn ? formatMoney(walmex.ppp_bmv_mxn) : "$54.59"} />
              {mercado && (
                <>
                  <div className="bk-hero-float f1">
                    PPP verificados hoy
                    <strong className="bk-mono">
                      {k.total_verificadas ?? "—"}/{k.total_emisoras ?? 15}
                    </strong>
                    sesión {mercado.fecha}
                  </div>
                  {alza && (
                    <div className="bk-hero-float f2">
                      Mayor alza del día
                      <strong className="bk-mono bk-up">
                        {alza.emisora} {formatPct(alza.variacion_pct)}
                      </strong>
                      {formatMoney(alza.ppp_bmv_mxn)}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
          <WaveDivider />
        </section>

        {/* ------------------------------------------------ Accesos rápidos */}
        <section className="bk-container">
          <div className="bk-quick">
            <h3>¿Qué quieres consultar hoy?</h3>
            <div className="bk-quick-grid">
              {quick.map(([Icon, label, href]) =>
                href ? (
                  <a key={label} href={href} className="bk-quick-item">
                    <span className="bk-quick-icon"><Icon size={22} /></span>
                    {label}
                  </a>
                ) : (
                  <button
                    key={label}
                    type="button"
                    className="bk-quick-item"
                    onClick={() => window.dispatchEvent(new CustomEvent("prisma:open-guide"))}
                  >
                    <span className="bk-quick-icon"><Icon size={22} /></span>
                    {label}
                  </button>
                )
              )}
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------- Mercado hoy */}
        <section className="bk-section bk-container" aria-labelledby="mercado-hoy">
          <div className="bk-market-head">
            <div>
              <span className="bk-eyebrow">Resumen del mercado</span>
              <h2 id="mercado-hoy">Mercado hoy{mercado ? ` · ${mercado.fecha}` : ""}</h2>
            </div>
            <a href="#/sistema/mercado" className="bk-btn bk-btn-ghost">
              Ver las 15 emisoras <ArrowRight size={16} />
            </a>
          </div>
          <div className="bk-grid-4">
            <div className="bk-card bk-stat">
              <small>PPP verificados</small>
              <strong className="bk-mono">{k.total_verificadas ?? "—"} de {k.total_emisoras ?? 15}</strong>
              <span>{k.total_ausentes ?? 0} emisoras sin dato en el boletín (sin rellenar)</span>
            </div>
            <div className="bk-card bk-stat">
              <small>Alzas · bajas</small>
              <strong className="bk-mono">
                <span className="bk-up">{k.conteo_alzas ?? "—"}</span> · <span className="bk-down">{k.conteo_bajas ?? "—"}</span>
              </strong>
              <span>Variación del PPP contra la sesión anterior</span>
            </div>
            <div className="bk-card bk-stat">
              <small>Mayor alza</small>
              <strong className="bk-mono bk-up">
                <TrendingUp size={20} style={{ verticalAlign: "-3px" }} /> {alza ? `${alza.emisora} ${formatPct(alza.variacion_pct)}` : "—"}
              </strong>
              <span>{alza ? `PPP ${formatMoney(alza.ppp_bmv_mxn)}` : "Sin datos"}</span>
            </div>
            <div className="bk-card bk-stat">
              <small>Mayor baja</small>
              <strong className="bk-mono bk-down">
                <TrendingDown size={20} style={{ verticalAlign: "-3px" }} /> {baja ? `${baja.emisora} ${formatPct(baja.variacion_pct)}` : "—"}
              </strong>
              <span>{baja ? `PPP ${formatMoney(baja.ppp_bmv_mxn)}` : "Sin datos"}</span>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------- Por qué el PPP */}
        <section data-tour="por-que-ppp" className="bk-container" aria-labelledby="por-que">
          <div className="bk-section-head">
            <span className="bk-eyebrow">Fundamento</span>
            <h2 id="por-que">¿Por qué el PPP oficial y no el precio de cierre?</h2>
            <p>El precio que mira la terminal es el mismo que publica la BMV para valuar y liquidar.</p>
          </div>
          <div className="bk-grid-2">
            <div className="bk-card bk-compare bk-compare-bad">
              <XCircle size={30} color="#d64545" style={{ flex: "none" }} />
              <div>
                <h3>Precio de cierre</h3>
                <p>Lo fija la última operación, a veces en una subasta con poco volumen. Una sola postura puede moverlo sin reflejar el día.</p>
              </div>
            </div>
            <div className="bk-card bk-compare bk-compare-good">
              <CheckCircle2 size={30} color="#0e9f6e" style={{ flex: "none" }} />
              <div>
                <h3>PPP oficial de la BMV</h3>
                <p>Pondera por volumen todas las operaciones de la sesión. Es difícil de mover con pocas órdenes y se publica en el boletín oficial.</p>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------- Cómo funciona */}
        <section id="como-funciona" data-tour="capacidades" className="bk-section bk-container" aria-labelledby="como">
          <div className="bk-section-head">
            <span className="bk-eyebrow">Cómo funciona</span>
            <h2 id="como">Del boletín oficial a una señal auditada</h2>
            <p>Cuatro pasos automáticos cada día hábil, sin intervención manual.</p>
          </div>
          <div className="bk-steps">
            {PASOS.map(([icono, titulo, texto], i) => (
              <div key={titulo} className="bk-card bk-step">
                <span className="bk-step-num">Paso {i + 1}</span>
                <StepIcon kind={icono} />
                <h3>{titulo}</h3>
                <p>{texto}</p>
              </div>
            ))}
          </div>
        </section>

        {/* -------------------------------------------------------- Planes */}
        <section id="planes" data-tour="planes" className="bk-container" aria-labelledby="productos">
          <div className="bk-section-head">
            <span className="bk-eyebrow">Planes</span>
            <h2 id="productos">Elige el plan que va con tu análisis</h2>
            <p>Empieza gratis con WALMEX y amplía cuando necesites el panel completo.</p>
          </div>
          <div className="bk-products">
            {PLANS.map((plan) => (
              <article key={plan.id} className={`bk-card bk-product ${plan.id === "professional" ? "is-featured" : ""}`}>
                <div className="bk-product-art"><PlanCardArt plan={plan.id} /></div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <h3>{plan.name}</h3>
                  {plan.id === "professional" && <span className="bk-chip">Más elegido</span>}
                </div>
                <div className="bk-product-price">
                  <strong>{plan.price.amount}</strong>
                  <span>{plan.price.detail}</span>
                </div>
                <p style={{ margin: 0, fontSize: 14 }}>{plan.summary}</p>
                <ul>
                  {plan.includes.slice(0, 5).map((item) => (
                    <li key={item}><Check size={16} /> {item}</li>
                  ))}
                </ul>
                <a
                  href={hasSession ? "#/planes" : "#/registro"}
                  className={`bk-btn ${plan.id === "professional" ? "bk-btn-primary" : "bk-btn-outline"}`}
                >
                  {plan.id === "explorer" ? "Abrir cuenta gratis" : `Elegir ${plan.name}`}
                </a>
              </article>
            ))}
          </div>
        </section>

        {/* ----------------------------------------------------- Seguridad */}
        <section className="bk-section bk-container" aria-labelledby="seguridad">
          <div className="bk-security">
            <div>
              <span className="bk-eyebrow" style={{ color: "#5fd0dc" }}>Seguridad y transparencia</span>
              <h2 id="seguridad">Cada cifra se puede rastrear hasta su origen</h2>
              <p>Como en tu banco, la confianza se construye con controles que puedes verificar.</p>
              <ul>
                <li><Fingerprint size={20} /> El boletín HTML se guarda intacto con su huella SHA-256: si cambiara un número, la huella no coincidiría.</li>
                <li><ShieldCheck size={20} /> Las señales emitidas no se reescriben. Los aciertos y los errores quedan registrados.</li>
                <li><Lock size={20} /> Acceso con sesión cifrada; cada plan ve solo lo que incluye.</li>
              </ul>
            </div>
            <div className="bk-security-art">
              <ShieldArt />
            </div>
          </div>
        </section>

        {/* ----------------------------------------------------------- FAQ */}
        <section id="faq" className="bk-container" aria-labelledby="preguntas">
          <div className="bk-section-head">
            <span className="bk-eyebrow">Ayuda</span>
            <h2 id="preguntas">Preguntas frecuentes</h2>
          </div>
          <div className="bk-faq">
            {FAQS.map(([q, a]) => (
              <details key={q}>
                <summary>{q}</summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
          {walmex && (
            <div className="bk-card bk-card-pad" style={{ maxWidth: 860, margin: "24px auto 0", display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
              <MiniSpark values={[1, 1.4, 1.2, 1.8, 1.6, 2.2]} />
              <div style={{ flex: 1, minWidth: 220 }}>
                <strong style={{ color: "var(--bk-navy)" }}>WALMEX está incluida gratis</strong>
                <p style={{ margin: 0, fontSize: 13.5 }}>
                  PPP de la sesión {mercado.fecha}: <span className="bk-mono">{formatMoney(walmex.ppp_bmv_mxn)}</span> ({formatPct(walmex.variacion_pct)}).
                </p>
              </div>
              <a href={hasSession ? "#/sistema" : "#/registro"} className="bk-btn bk-btn-primary bk-btn-sm">
                {hasSession ? "Ver en mi terminal" : "Abrir cuenta"} <ArrowRight size={15} />
              </a>
            </div>
          )}
        </section>
      </main>

      <Footer />
    </>
  );
}
