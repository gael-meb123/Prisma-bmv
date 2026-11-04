import React, { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, Sparkles, HelpCircle, ChevronRight } from "lucide-react";
import { guideMoment } from "../guide/moments.mjs";
import { api } from "../services/api.mjs";

export function Guide({ route, phase, selectedTicker, busy, error }) {
  const [open, setOpen] = useState(false);
  const [bubbleOpen, setBubbleOpen] = useState(true);
  const [messages, setMessages] = useState([
    {
      sender: "prismi",
      text: "¡Hola! Soy Prismi, la gráfica bailarina de Prisma BMV. 🕯️💃 Puedo explicarte cómo funcionan los modelos predictivos G2, qué es el PPP oficial o el estado de cualquier emisora del IPC."
    }
  ]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const threadRef = useRef(null);

  const moment = guideMoment({ route, phase, selectedTicker, busy, error });

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages, open]);

  async function handleSend(e) {
    e.preventDefault();
    if (!draft.trim() || sending) return;

    const userText = draft.trim();
    setDraft("");
    setMessages((prev) => [...prev, { sender: "user", text: userText }]);
    setSending(true);

    try {
      const resp = await api.chatPrismi(userText);
      setMessages((prev) => [...prev, { sender: "prismi", text: resp }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          sender: "prismi",
          text: "Hubo una interrupción en el enlace analítico. Recuerda que mi conocimiento está especializado en Prisma BMV y modelos cuantitativos."
        }
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <aside className="guide" aria-label="Asistente Prismi" style={{ position: "fixed", bottom: "24px", right: "24px", zIndex: 1000, display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
      {/* Globo contextual de diálogo si está cerrado */}
      {!open && bubbleOpen && (
        <div
          className="guide-bubble"
          style={{
            background: "#ffffff",
            border: "1px solid var(--line)",
            borderRadius: "14px",
            padding: "12px 16px",
            boxShadow: "0 12px 35px rgba(9, 42, 73, 0.12)",
            maxWidth: "320px",
            marginBottom: "12px",
            position: "relative",
            fontSize: "13px",
            lineHeight: "1.5",
            color: "var(--navy)"
          }}
        >
          <button
            onClick={() => setBubbleOpen(false)}
            style={{ position: "absolute", top: "6px", right: "6px", background: "transparent", border: 0, cursor: "pointer", color: "var(--muted)" }}
            aria-label="Cerrar aviso"
          >
            <X size={14} />
          </button>
          <strong style={{ display: "block", color: "var(--teal-dark)", fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "4px" }}>
            {moment.prompt}
          </strong>
          <p style={{ margin: 0 }}>{moment.message}</p>
        </div>
      )}

      {/* Ventana de Chat Inteligente */}
      {open && (
        <div
          className="guide-chat"
          style={{
            width: "360px",
            maxWidth: "calc(100vw - 32px)",
            height: "460px",
            background: "#ffffff",
            border: "1px solid var(--line)",
            borderRadius: "16px",
            boxShadow: "0 20px 50px rgba(9, 42, 73, 0.2)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            marginBottom: "14px"
          }}
        >
          {/* Header de Prismi */}
          <div
            style={{
              background: "linear-gradient(105deg, #062c50, #073b67 56%, #06294c)",
              padding: "14px 16px",
              color: "#ffffff",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ width: 28, height: 28, borderRadius: "50%", background: "#10b98125", border: "1px solid #10b981", display: "grid", placeItems: "center" }}>
                🕯️
              </div>
              <div>
                <strong style={{ fontSize: "14px", display: "block" }}>Prismi AI</strong>
                <span style={{ fontSize: "11px", color: "#8ee3ed" }}>La Gráfica Bailarina de Prisma BMV</span>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              style={{ background: "transparent", border: 0, color: "#ffffff", cursor: "pointer" }}
              aria-label="Minimizar chat"
            >
              <X size={18} />
            </button>
          </div>

          {/* Hilo de mensajes */}
          <div
            ref={threadRef}
            style={{
              flex: 1,
              padding: "14px",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              fontSize: "13px"
            }}
          >
            {messages.map((m, idx) => (
              <div
                key={idx}
                style={{
                  alignSelf: m.sender === "user" ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  background: m.sender === "user" ? "#079baa" : "#f1f5f9",
                  color: m.sender === "user" ? "#ffffff" : "var(--navy)",
                  padding: "10px 14px",
                  borderRadius: "14px",
                  borderBottomRightRadius: m.sender === "user" ? "2px" : "14px",
                  borderBottomLeftRadius: m.sender === "prismi" ? "2px" : "14px",
                  lineHeight: "1.5"
                }}
              >
                {m.text}
              </div>
            ))}
            {sending && (
              <div style={{ alignSelf: "flex-start", background: "#f1f5f9", padding: "8px 12px", borderRadius: "12px", fontSize: "12px", color: "var(--muted)" }}>
                Prismi está analizando el modelo…
              </div>
            )}
          </div>

          {/* Formulario de envío */}
          <form
            onSubmit={handleSend}
            style={{
              padding: "10px 12px",
              borderTop: "1px solid var(--line)",
              display: "flex",
              gap: "8px",
              background: "#fafcff"
            }}
          >
            <input
              type="text"
              placeholder="Pregunta sobre WALMEX, PPP, o modelos G2…"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              style={{
                flex: 1,
                padding: "8px 12px",
                borderRadius: "8px",
                border: "1px solid var(--line)",
                fontSize: "12px"
              }}
            />
            <button
              type="submit"
              disabled={!draft.trim() || sending}
              className="button button-primary"
              style={{ padding: "0 12px" }}
              aria-label="Enviar pregunta"
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      )}

      {/* Botón flotante Mascota Candlestick SVG */}
      <button
        onClick={() => {
          setOpen(!open);
          setBubbleOpen(false);
        }}
        style={{
          width: "56px",
          height: "56px",
          borderRadius: "50%",
          background: "linear-gradient(135deg, #062c50, #079baa)",
          border: "2px solid #ffffff",
          boxShadow: "0 10px 25px rgba(7, 155, 170, 0.35)",
          display: "grid",
          placeItems: "center",
          cursor: "pointer",
          padding: 0
        }}
        aria-label="Abrir asistente Prismi"
      >
        <svg viewBox="0 0 48 48" width="34" height="34">
          <line x1="24" y1="4" x2="24" y2="12" stroke="#ffffff" strokeWidth="2.5" strokeLinecap="round" />
          <rect x="14" y="12" width="20" height="24" rx="4" fill="#10b981" stroke="#ffffff" strokeWidth="1.5" />
          <circle cx="19" cy="21" r="2.2" fill="#022c22" />
          <circle cx="29" cy="21" r="2.2" fill="#022c22" />
          <circle cx="19.7" cy="20.3" r="0.8" fill="#ffffff" />
          <circle cx="29.7" cy="20.3" r="0.8" fill="#ffffff" />
          <path d="M 19 27 Q 24 31 29 27" fill="transparent" stroke="#022c22" strokeWidth="1.5" strokeLinecap="round" />
          <circle cx="16" cy="25" r="1.5" fill="#f43f5e" opacity="0.7" />
          <circle cx="32" cy="25" r="1.5" fill="#f43f5e" opacity="0.7" />
          <line x1="24" y1="36" x2="24" y2="44" stroke="#ffffff" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      </button>
    </aside>
  );
}
