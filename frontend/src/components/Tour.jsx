import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { X, MousePointerClick, ChevronLeft, ChevronRight } from "lucide-react";
import { Mascot } from "./Mascot";
import { buildSteps, markTourDone } from "../guide/tour.mjs";
import "./tour.css";

// Medidas de Prismi en pantalla (el SVG mide size x size*1.25)
const W = 96;
const H = 120;
const GAP = 14;
const MARGIN = 12;
const MOBILE = 720;
const TYPE_SPEED = 3; // caracteres por cuadro de 22 ms
const HEADER_OFFSET = 80; // deja libre la barra superior al desplazar

const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), Math.max(lo, hi));

function reduceMotion() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function routeFromHash() {
  return location.hash.startsWith("#/") ? location.hash.slice(1) : "/";
}

function findTarget(target) {
  if (!target) return null;
  for (const selector of Array.isArray(target) ? target : [target]) {
    let el = null;
    try {
      el = document.querySelector(selector);
    } catch {
      el = null;
    }
    if (!el) continue;
    const box = el.getBoundingClientRect();
    if (box.width > 0 && box.height > 0) return el;
  }
  return null;
}

function measure(el) {
  const b = el.getBoundingClientRect();
  return { top: b.top, left: b.left, width: b.width, height: b.height, right: b.right, bottom: b.bottom };
}

function sameRect(a, b) {
  return a && b && ["top", "left", "width", "height"].every((k) => Math.abs(a[k] - b[k]) < 0.5);
}

function dockSpot() {
  return { x: window.innerWidth - W - 24, y: window.innerHeight - H - 16 };
}

// Dónde se para Prismi y hacia dónde apunta.
function mascotSpot(rect, step) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const mobile = vw <= MOBILE;
  // En móvil el globo ocupa la parte baja: Prismi se queda encima de él.
  if (mobile && (step?.dock || !rect)) {
    return { x: vw - W - 16, y: clamp(vh * 0.55 - H, MARGIN, vh - H - MARGIN), pose: step?.pose || "wave" };
  }
  if (step?.dock) return { ...dockSpot(), pose: step.pose || "cheer" };
  if (!rect) {
    return { x: (vw - W) / 2, y: clamp(vh / 2 - H - 30, MARGIN, vh - H - MARGIN), pose: step?.pose || "wave" };
  }
  const visTop = Math.max(rect.top, 0);
  const visBottom = Math.min(rect.bottom, vh);
  const sideY = clamp((visTop + visBottom) / 2 - H / 2, MARGIN, vh - H - MARGIN);
  if (!mobile && vw - rect.right - MARGIN >= W + GAP) {
    return { x: rect.right + GAP, y: sideY, pose: "point-left" };
  }
  if (!mobile && rect.left - MARGIN >= W + GAP) {
    return { x: rect.left - GAP - W, y: sideY, pose: "point-right" };
  }
  // Sin espacio a los lados: arriba o abajo del objetivo.
  const floor = mobile ? vh * 0.55 : vh - MARGIN;
  const x = clamp(rect.left + 8, MARGIN, vw - W - MARGIN);
  if (rect.bottom + GAP + H <= floor) return { x, y: rect.bottom + GAP, pose: "point-up" };
  if (rect.top - GAP - H >= MARGIN) return { x, y: rect.top - GAP - H, pose: "point-down" };
  return { x, y: clamp(floor - H, MARGIN, vh - H - MARGIN), pose: "point-up" };
}

function gazeToward(spot, rect) {
  if (!rect) return { x: 0, y: 0.3 };
  const dx = rect.left + rect.width / 2 - (spot.x + W / 2);
  const dy = rect.top + rect.height / 2 - (spot.y + H * 0.35);
  const len = Math.hypot(dx, dy) || 1;
  return { x: dx / len, y: dy / len };
}

function overlaps(a, b, pad = 6) {
  return !(
    a.left + a.width <= b.left - pad ||
    a.left >= b.left + b.width + pad ||
    a.top + a.height <= b.top - pad ||
    a.top >= b.top + b.height + pad
  );
}

// El globo va pegado a Prismi, del lado contrario al objetivo si cabe.
function bubbleSpot(mascot, rect, bw, bh) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  if (vw <= MOBILE) return { left: MARGIN, top: vh - bh - MARGIN, mobile: true };
  const mx = mascot.x;
  const my = mascot.y;
  const spots = {
    right: { left: mx + W + 6, top: my + H * 0.3 - bh / 2 },
    rightTop: { left: mx + W + 6, top: my },
    rightBottom: { left: mx + W + 6, top: my + H - bh },
    left: { left: mx - 6 - bw, top: my + H * 0.3 - bh / 2 },
    leftTop: { left: mx - 6 - bw, top: my },
    leftBottom: { left: mx - 6 - bw, top: my + H - bh },
    above: { left: mx + W / 2 - bw / 2, top: my - 6 - bh },
    below: { left: mx + W / 2 - bw / 2, top: my + H + 6 },
  };
  const order = {
    "point-left": ["right", "rightTop", "rightBottom", "above", "below", "left"],
    "point-right": ["left", "leftTop", "leftBottom", "above", "below", "right"],
    "point-up": ["rightTop", "leftTop", "below", "right", "left", "above"],
    "point-down": ["rightBottom", "leftBottom", "above", "right", "left", "below"],
  }[mascot.side || mascot.pose] || ["left", "right", "above", "below"];
  const fits = (s) => s.left >= MARGIN && s.top >= MARGIN && s.left + bw <= vw - MARGIN && s.top + bh <= vh - MARGIN;
  const clean = (s) => !rect || !overlaps({ ...s, width: bw, height: bh }, rect);
  const pick =
    order.map((k) => spots[k]).find((s) => fits(s) && clean(s)) ||
    order.map((k) => spots[k]).find(fits) ||
    spots[order[0]];
  return {
    left: Math.round(clamp(pick.left, MARGIN, vw - bw - MARGIN)),
    top: Math.round(clamp(pick.top, MARGIN, vh - bh - MARGIN)),
  };
}

export function Tour({ route }) {
  const [active, setActive] = useState(false);
  const [index, setIndex] = useState(0);
  const [stage, setStage] = useState("seeking"); // seeking | flying | talking
  const [rect, setRect] = useState(null);
  const [mascot, setMascot] = useState(() => ({ ...dockSpot(), pose: "wave", gaze: { x: 0, y: 0 } }));
  const [motion, setMotion] = useState({ flying: false, facing: 1, ms: 900, instant: false });
  const [bubblePos, setBubblePos] = useState(null);
  const [typed, setTyped] = useState(0);
  const [part, setPart] = useState("full"); // public | terminal | full
  const steps = useMemo(() => buildSteps(part), [part]);

  const mascotRef = useRef(mascot);
  const elRef = useRef(null);
  const dirRef = useRef(1);
  const bubbleRef = useRef(null);

  const step = active ? steps[index] || null : null;
  const total = steps.length;
  const isLast = index >= total - 1;
  const fullText = step?.body || "";
  const typing = stage === "talking" && typed < fullText.length;

  function placeMascot(next) {
    mascotRef.current = next;
    setMascot(next);
  }

  function go(delta) {
    const next = index + delta;
    if (next >= total) {
      finish();
      return;
    }
    if (next < 0) return;
    dirRef.current = delta;
    setIndex(next);
  }

  function finish() {
    setActive(false);
    setStage("seeking");
    setRect(null);
    elRef.current = null;
    markTourDone(part);
    window.dispatchEvent(new CustomEvent("prisma:tour-done", { detail: { part } }));
  }

  // Arranque: lo dispara el asistente (o cualquier botón) con el evento prisma:tour-start.
  useEffect(() => {
    function onStart(event) {
      const requested = event?.detail?.part;
      setPart(requested === "public" || requested === "terminal" ? requested : "full");
      dirRef.current = 1;
      placeMascot({ ...dockSpot(), pose: "wave", gaze: { x: 0, y: 0 } });
      setIndex(0);
      setStage("seeking");
      setActive(true);
    }
    window.addEventListener("prisma:tour-start", onStart);
    return () => window.removeEventListener("prisma:tour-start", onStart);
  }, []);

  useEffect(() => {
    if (active) document.body.dataset.tour = "on";
    else delete document.body.dataset.tour;
    return () => delete document.body.dataset.tour;
  }, [active]);

  // 1) Navegar a la ruta/fase del paso, 2) encontrar el objetivo, 3) volar hasta él.
  useEffect(() => {
    if (!active || !step) return undefined;
    if (step.route && routeFromHash() !== step.route) {
      location.hash = step.route;
      return undefined; // el cambio de ruta vuelve a ejecutar este efecto
    }
    if (step.phase) {
      window.dispatchEvent(new CustomEvent("prisma:tour-phase", { detail: step.phase }));
    }

    let cancelled = false;
    let timer = 0;
    let frame = 0;
    let tries = 0;
    setStage("seeking");
    setTyped(0);
    elRef.current = null;

    function land(el) {
      if (cancelled) return;
      elRef.current = el;
      const r = el ? measure(el) : null;
      setRect(r);
      const spot = mascotSpot(r, step);
      const finalPose = step.pose || spot.pose;
      const from = mascotRef.current;
      const dx = spot.x - from.x;
      const distance = Math.hypot(dx, spot.y - from.y);
      const gaze = gazeToward(spot, r);
      if (distance < 6 || reduceMotion()) {
        setMotion({ flying: false, facing: 1, ms: 0, instant: true });
        placeMascot({ x: spot.x, y: spot.y, pose: finalPose, side: spot.pose, gaze });
        setStage("talking");
        return;
      }
      const ms = Math.round(clamp(520 + distance * 0.55, 650, 1400));
      setMotion({ flying: true, facing: dx < 0 ? -1 : 1, ms, instant: false });
      placeMascot({ x: spot.x, y: spot.y, pose: "fly", gaze: { x: dx < 0 ? -1 : 1, y: 0 } });
      setStage("flying");
      timer = window.setTimeout(() => {
        if (cancelled) return;
        setMotion((m) => ({ ...m, flying: false }));
        placeMascot({ x: spot.x, y: spot.y, pose: finalPose, side: spot.pose, gaze });
        setStage("talking");
      }, ms);
    }

    // Espera a que el scroll suave termine (el rectángulo deja de moverse).
    function settle(el) {
      let last = null;
      let still = 0;
      const started = performance.now();
      function tick() {
        if (cancelled) return;
        const now = measure(el);
        still = sameRect(now, last) ? still + 1 : 0;
        last = now;
        if (still >= 6 || performance.now() - started > 1200) land(el);
        else frame = requestAnimationFrame(tick);
      }
      frame = requestAnimationFrame(tick);
    }

    function seek() {
      if (cancelled) return;
      if (!step.target) {
        land(null);
        return;
      }
      const el = findTarget(step.target);
      if (el) {
        const b = el.getBoundingClientRect();
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const behavior = reduceMotion() ? "auto" : "smooth";
        // "Ancho" = no cabe Prismi a ningún lado; entonces se para debajo del objetivo.
        const wide = vw <= MOBILE || vw - b.width < 2 * (W + GAP + MARGIN);
        const roomBelow = wide ? H + GAP + MARGIN + (vw <= MOBILE ? vh * 0.45 : 0) : 0;
        const fits = b.height + roomBelow + HEADER_OFFSET <= vh;
        let block = null;
        if (wide) {
          if (b.top < HEADER_OFFSET - 4 || (fits ? b.bottom + roomBelow > vh : b.top > HEADER_OFFSET + 4)) block = "start";
        } else if (b.top < 90 || b.bottom > vh - 90) {
          block = b.height > vh - 200 ? "start" : "center";
        }
        if (block) {
          const previous = el.style.scrollMarginTop;
          el.style.scrollMarginTop = `${HEADER_OFFSET}px`;
          el.scrollIntoView({ block, behavior });
          window.setTimeout(() => {
            el.style.scrollMarginTop = previous;
          }, 50);
        }
        settle(el);
        return;
      }
      tries += 1;
      if (tries > 40) {
        // El objetivo no apareció: los pasos opcionales se saltan; los demás se explican al centro.
        if (step.optional) {
          const next = index + dirRef.current;
          if (next >= 0 && next < total) setIndex(next);
          else land(null);
          return;
        }
        land(null);
        return;
      }
      timer = window.setTimeout(seek, 100);
    }

    // Pequeña pausa para que React pinte la ruta o la fase nueva.
    timer = window.setTimeout(seek, step.phase ? 120 : 30);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      cancelAnimationFrame(frame);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, index, route]);

  // Seguir al objetivo si la página se mueve (scroll, resize, contenido que crece).
  useEffect(() => {
    if (!active || stage !== "talking") return undefined;
    const el = elRef.current;
    let frame = 0;
    function follow() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const r = el && el.isConnected ? measure(el) : null;
        setRect((old) => (sameRect(old, r) ? old : r));
        const spot = mascotSpot(r, step);
        const cur = mascotRef.current;
        if (Math.abs(cur.x - spot.x) < 0.5 && Math.abs(cur.y - spot.y) < 0.5) return;
        setMotion((m) => ({ ...m, instant: true }));
        placeMascot({ ...cur, x: spot.x, y: spot.y, pose: step.pose || spot.pose, side: spot.pose, gaze: gazeToward(spot, r) });
      });
    }
    window.addEventListener("scroll", follow, true);
    window.addEventListener("resize", follow);
    const observer = el ? new ResizeObserver(follow) : null;
    if (el) observer.observe(el);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", follow, true);
      window.removeEventListener("resize", follow);
      observer?.disconnect();
    };
  }, [active, stage, step]);

  // Pasos interactivos: avanzan cuando el usuario hace clic en el elemento resaltado.
  useEffect(() => {
    if (!active || stage === "seeking" || step?.advanceOn !== "click") return undefined;
    const el = elRef.current;
    if (!el) return undefined;
    function onClick() {
      // Clic en el último paso (p. ej. «Iniciar sesión»): termina sin bloquear la navegación.
      if (index >= total - 1) {
        window.setTimeout(finish, 0);
        return;
      }
      dirRef.current = 1;
      setIndex((i) => Math.min(i + 1, total - 1));
    }
    el.addEventListener("click", onClick, true);
    return () => el.removeEventListener("click", onClick, true);
  }, [active, stage, step, total, index]);

  // Efecto máquina de escribir.
  useEffect(() => {
    if (stage !== "talking") return undefined;
    if (reduceMotion()) {
      setTyped(fullText.length);
      return undefined;
    }
    const id = window.setInterval(() => {
      setTyped((n) => {
        if (n >= fullText.length) {
          window.clearInterval(id);
          return n;
        }
        return n + TYPE_SPEED;
      });
    }, 22);
    return () => window.clearInterval(id);
  }, [stage, fullText]);

  // Teclado: Esc cierra, flechas navegan.
  useEffect(() => {
    if (!active) return undefined;
    function onKey(event) {
      if (event.target.closest?.("input, textarea, select")) return;
      if (event.key === "Escape") finish();
      if (event.key === "ArrowRight") next();
      if (event.key === "ArrowLeft") go(-1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // Coloca el globo cuando Prismi aterriza.
  useLayoutEffect(() => {
    if (!active || stage !== "talking") {
      setBubblePos(null);
      return;
    }
    const node = bubbleRef.current;
    if (!node) return;
    setBubblePos(bubbleSpot(mascot, rect, node.offsetWidth, node.offsetHeight));
  }, [active, stage, mascot, rect, index]);

  function next() {
    if (typing) {
      setTyped(fullText.length);
      return;
    }
    go(1);
  }

  if (!active || !step) return null;

  const pad = 8;
  const showSpot = rect && stage !== "seeking";
  const tilt = motion.flying ? `rotate(${motion.facing * 16}deg) scaleX(${motion.facing})` : "none";
  const mascotStyle = {
    left: mascot.x,
    top: mascot.y,
    "--fly-ms": `${motion.instant ? 0 : motion.ms}ms`,
    "--trail": `${-motion.facing * 46}px`,
  };

  return (
    <div className="ptour" role="dialog" aria-modal="false" aria-label="Recorrido guiado de Prisma BMV">
      <div
        className={`ptour-spot ${showSpot ? "is-on" : "is-off"}`}
        aria-hidden="true"
        style={
          showSpot
            ? { top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }
            : undefined
        }
      />

      <div
        className={`ptour-mascot ${motion.flying ? "is-flying" : ""} ${stage === "talking" ? "is-landed" : ""}`}
        style={mascotStyle}
        aria-hidden="true"
      >
        <span className="ptour-trail">
          <i>$</i>
          <i>$</i>
          <i>$</i>
        </span>
        <div className="ptour-tilt" style={{ transform: tilt }}>
          <Mascot size={W} expression={motion.flying ? "happy" : step.expression} pose={mascot.pose} gaze={mascot.gaze} />
        </div>
      </div>

      <section
        ref={bubbleRef}
        className={`ptour-bubble ${bubblePos?.mobile ? "is-mobile" : ""} ${stage === "talking" && bubblePos ? "is-shown" : ""}`}
        style={bubblePos ? { top: bubblePos.top, left: bubblePos.left } : { top: -9999, left: -9999 }}
        aria-live="polite"
      >
        <button type="button" className="ptour-close" aria-label="Salir del recorrido" onClick={finish}>
          <X size={16} aria-hidden="true" />
        </button>
        <div className="ptour-progress" aria-label={`Paso ${index + 1} de ${total}`}>
          <span style={{ width: `${((index + 1) / total) * 100}%` }} />
        </div>
        <p className="ptour-count">
          Paso {index + 1} de {total}
        </p>
        <h2 className="ptour-title">{step.title}</h2>
        <p className="ptour-text">
          <span className="ptour-text-ghost" aria-hidden="true">{fullText}</span>
          <span className="ptour-text-live">
            {fullText.slice(0, typed)}
            {typing && <b className="ptour-caret" aria-hidden="true" />}
          </span>
        </p>
        {step.emphasis && <p className="ptour-emphasis">{step.emphasis}</p>}
        {step.advanceOn === "click" && (
          <p className="ptour-hint">
            <MousePointerClick size={16} aria-hidden="true" />
            {step.hint || "Haz clic en el elemento resaltado"}
          </p>
        )}
        <div className="ptour-actions">
          <button type="button" className="ptour-skip" onClick={finish}>
            {isLast ? "Cerrar" : "Saltar tour"}
          </button>
          <div className="ptour-actions-main">
            <button
              type="button"
              className="button button-outline ptour-back"
              onClick={() => go(-1)}
              disabled={index === 0}
              aria-label="Paso anterior"
            >
              <ChevronLeft size={15} aria-hidden="true" />
            </button>
            <button type="button" className="button button-primary ptour-next" onClick={next}>
              {typing ? "Mostrar todo" : isLast ? "Terminar" : step.advanceOn === "click" ? "Saltar paso" : "Siguiente"}
              {!typing && !isLast && <ChevronRight size={15} aria-hidden="true" />}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
