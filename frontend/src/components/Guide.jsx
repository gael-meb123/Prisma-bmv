import React, { useState, useRef, useEffect } from "react";
import { X, Send, Map as MapIcon, LogIn, UserPlus } from "lucide-react";
import { guideMoment } from "../guide/moments.mjs";
import { guideChoice, saveGuideChoice, startTour, tourDone } from "../guide/tour.mjs";
import { api } from "../services/api.mjs";
import { useAccount } from "../hooks/useAccount";
import { Mascot } from "./Mascot";
import "./guide.css";

const isTerminalRoute = (route) => route === "/sistema" || route.startsWith("/ficha");
const isAuthRoute = (route) => route === "/acceso" || route === "/registro";

// Qué recorrido ofrecer (o ninguno) según ruta y sesión.
//  - Primera visita a la vista general: con sesión → completo; sin sesión → parte 1.
//  - Al entrar a la terminal con sesión por primera vez → parte 2.
function pendingOffer({ route, hasSession, ready }) {
  if (!ready || isAuthRoute(route)) return null;
  if (isTerminalRoute(route)) {
    if (!hasSession) return null;
    if (tourDone("terminal") || guideChoice("terminal")) return null;
    return "terminal";
  }
  if (tourDone("public") || guideChoice("public")) return null;
  return hasSession ? "full" : "public";
}

const OFFER_TEXT = {
  public: "¡Hola! Soy Prismi. ¿Te enseño en un minuto qué es Prisma BMV y cómo entrar a la terminal?",
  full: "¡Hola! Soy Prismi. ¿Te llevo volando por Prisma BMV y por dentro de la terminal?",
  terminal: "¡Ya estás dentro! ¿Te enseño cómo funciona la terminal?",
};

export function Guide({ route, phase, selectedTicker, busy, error }) {
  const account = useAccount();
  const hasSession = Boolean(account.session);
  const ready = account.ready;
  const nombre = account.user?.name?.split(" ")[0] || "";

  const [open, setOpen] = useState(false);
  const [bubbleOpen, setBubbleOpen] = useState(true);
  const [, setTick] = useState(0); // fuerza recalcular la oferta tras elegir/terminar
  const [messages, setMessages] = useState([
    {
      sender: "prismi",
      text: "¡Hola! Soy Prismi, el billete con superpoderes de Prisma BMV. Puedo explicarte cómo funcionan los modelos predictivos G2, qué es el PPP oficial o el estado de cualquier emisora del IPC.",
    },
  ]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const threadRef = useRef(null);

  const moment = guideMoment({ route, phase, selectedTicker, busy, error, hasSession, nombre });
  // Se recalcula en cada render; `tick` provoca el render tras elegir o terminar.
  const offer = pendingOffer({ route, hasSession, ready });
  const expression = sending ? "thinking" : moment.expression;
  const askLogin = ready && !hasSession && !isAuthRoute(route);

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages, open]);

  // Al terminar un recorrido, Prismi vuelve a su esquina en silencio.
  useEffect(() => {
    function onDone() {
      setTick((t) => t + 1);
      setBubbleOpen(false);
    }
    window.addEventListener("prisma:tour-done", onDone);
    return () => window.removeEventListener("prisma:tour-done", onDone);
  }, []);

  // Cambios de sesión o de pantalla: Prismi vuelve a hablar.
  useEffect(() => {
    if (!ready) return;
    setBubbleOpen(true);
    if (hasSession) {
      setMessages((prev) => [
        ...prev,
        { sender: "prismi", text: `Sesión iniciada${nombre ? `, ${nombre}` : ""}. Tu plan es ${account.plan.name}. ¿En qué te ayudo?` },
      ]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasSession, ready]);

  useEffect(() => {
    // La terminal sin sesión: Prismi explica cómo entrar.
    if (isTerminalRoute(route) && ready && !hasSession) setBubbleOpen(true);
    // La terminal recién abierta con sesión y sin tour visto: ofrecerlo.
    if (isTerminalRoute(route) && ready && hasSession && offer === "terminal") setBubbleOpen(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route]);

  function acceptTour() {
    saveGuideChoice("tour", offer === "terminal" ? "terminal" : "public");
    setBubbleOpen(false);
    setOpen(false);
    startTour(offer);
    setTick((t) => t + 1);
  }

  function declineTour() {
    saveGuideChoice("chat", offer === "terminal" ? "terminal" : "public");
    setBubbleOpen(false);
    setOpen(true);
    setTick((t) => t + 1);
  }

  // Botón de mapa: el recorrido que corresponde a donde estás.
  function replayTour() {
    setOpen(false);
    if (isTerminalRoute(route) && hasSession) startTour("terminal");
    else startTour(hasSession ? "full" : "public");
  }

  function goLogin(mode) {
    setBubbleOpen(false);
    setOpen(false);
    window.location.hash = mode === "register" ? "/registro" : "/acceso";
  }

  async function handleSend(e) {
    e.preventDefault();
    if (!draft.trim() || sending) return;
    const userText = draft.trim();
    setDraft("");
    setMessages((prev) => [...prev, { sender: "user", text: userText }]);
    setSending(true);
    try {
      const resp = await api.chatPrismi(userText, [], undefined, { hasSession });
      setMessages((prev) => [...prev, { sender: "prismi", text: resp }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          sender: "prismi",
          text: "Hubo una interrupción en el enlace analítico. Recuerda que mi conocimiento está especializado en Prisma BMV y modelos cuantitativos.",
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  const loginButtons = (
    <div className="guide-offer-actions">
      <button type="button" className="button button-primary" onClick={() => goLogin("login")}>
        <LogIn size={14} aria-hidden="true" /> Iniciar sesión
      </button>
      <button type="button" className="button button-outline" onClick={() => goLogin("register")}>
        <UserPlus size={14} aria-hidden="true" /> Crear cuenta
      </button>
    </div>
  );

  return (
    <aside className="guide" aria-label="Asistente Prismi">
      {/* Globo: oferta de recorrido, invitación a entrar o mensaje contextual */}
      {!open && bubbleOpen && (
        <div className="guide-bubble">
          <button className="guide-bubble-close" onClick={() => setBubbleOpen(false)} aria-label="Cerrar aviso">
            <X size={14} />
          </button>
          {offer ? (
            <>
              <p className="guide-bubble-text">{OFFER_TEXT[offer]}</p>
              <div className="guide-offer-actions">
                <button type="button" className="button button-primary" onClick={acceptTour}>
                  Sí, enséñame
                </button>
                <button type="button" className="button button-outline" onClick={declineTour}>
                  Prefiero preguntar
                </button>
              </div>
            </>
          ) : (
            <>
              <strong className="guide-bubble-prompt">{moment.prompt}</strong>
              <p className="guide-bubble-text">{moment.message}</p>
              {askLogin && loginButtons}
            </>
          )}
        </div>
      )}

      {/* Chat */}
      {open && (
        <div className="guide-chat">
          <div className="guide-chat-header">
            <div className="guide-chat-id">
              <Mascot size={30} expression={expression} />
              <div>
                <strong>Prismi</strong>
                <span>{hasSession ? `${account.user?.email} · ${account.plan.name}` : "Sin sesión iniciada"}</span>
              </div>
            </div>
            <div className="guide-chat-tools">
              <button type="button" onClick={replayTour} aria-label="Ver el recorrido guiado" title="Ver el recorrido guiado">
                <MapIcon size={17} />
              </button>
              <button type="button" onClick={() => setOpen(false)} aria-label="Minimizar chat">
                <X size={18} />
              </button>
            </div>
          </div>

          <div ref={threadRef} className="guide-chat-thread">
            {messages.map((m, idx) => (
              <div key={idx} className={`guide-msg guide-msg-${m.sender}`}>
                {m.text}
              </div>
            ))}
            {askLogin && (
              <div className="guide-msg guide-msg-prismi">
                Aún no has iniciado sesión. La terminal y mis respuestas completas son para usuarios registrados; el registro es gratis.
                {loginButtons}
              </div>
            )}
            {sending && <div className="guide-msg guide-msg-typing">Prismi está analizando el modelo…</div>}
          </div>

          <form onSubmit={handleSend} className="guide-chat-form">
            <input
              type="text"
              placeholder={hasSession ? "Pregunta sobre WALMEX, PPP, o modelos G2…" : "Pregunta cómo entrar, qué es el PPP…"}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
            <button type="submit" disabled={!draft.trim() || sending} className="button button-primary" aria-label="Enviar pregunta">
              <Send size={14} />
            </button>
          </form>
        </div>
      )}

      {/* Prismi en la esquina */}
      <button
        type="button"
        className="guide-toggle"
        onClick={() => {
          if ((offer || askLogin) && !bubbleOpen && !open) {
            setBubbleOpen(true);
            return;
          }
          setOpen(!open);
          setBubbleOpen(false);
        }}
        aria-label={open ? "Cerrar asistente Prismi" : "Abrir asistente Prismi"}
      >
        <Mascot size={72} expression={expression} pose={bubbleOpen && !open ? "wave" : "idle"} />
      </button>
    </aside>
  );
}
