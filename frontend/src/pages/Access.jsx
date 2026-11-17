import React, { useState } from "react";
import { ArrowRight, CheckCircle2, Eye, EyeOff, Lock, Mail, ShieldCheck, User } from "lucide-react";
import { Header } from "../components/Header";
import { LoginArt } from "../components/Illustrations";
import { useAccount } from "../hooks/useAccount";

export function Access({ initialMode = "login" }) {
  const account = useAccount();

  const [mode, setMode] = useState(initialMode); // "login" | "register"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nombre, setNombre] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [registered, setRegistered] = useState(false);

  function cambiarModo(m) {
    setMode(m);
    setError("");
    setRegistered(false);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        await account.enter(email.trim().toLowerCase(), password);
        window.location.hash = "/sistema";
      } else {
        await account.register(email.trim().toLowerCase(), password, nombre.trim());
        setRegistered(true);
        setMode("login");
        setPassword("");
      }
    } catch (err) {
      setError(err.message || "Error inesperado. Intenta de nuevo.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Header />
      <main id="main-content" className="bk-access">
        <section className="bk-access-art" aria-hidden="false">
          <span className="bk-eyebrow" style={{ color: "#5fd0dc" }}>Terminal Prisma BMV</span>
          <h2>{mode === "login" ? "Bienvenido de vuelta" : "Abre tu cuenta en un minuto"}</h2>
          <p>
            {mode === "login"
              ? "Revisa el PPP oficial del día, las señales de tus emisoras y cómo van contra el resultado real."
              : "Empiezas con el plan Explorer: monitor de las 15 emisoras y WALMEX completo, sin costo."}
          </p>
          <LoginArt />
          <div style={{ display: "grid", gap: 10, fontSize: 14 }}>
            <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <CheckCircle2 size={18} color="#5fd0dc" /> Datos del boletín oficial con huella SHA-256
            </span>
            <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <CheckCircle2 size={18} color="#5fd0dc" /> Prismi te explica cada gráfica
            </span>
          </div>
        </section>

        <section className="bk-access-form">
          <div className="bk-access-box">
            <h1>{mode === "login" ? "Ingresa a tu terminal" : "Abre tu cuenta"}</h1>
            <p style={{ margin: 0, fontSize: 14 }}>
              {mode === "login" ? "Usa el correo y la contraseña de tu cuenta." : "Solo necesitas tu nombre, correo y una contraseña."}
            </p>

            <div className="bk-tabs" role="tablist" aria-label="Tipo de acceso">
              <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "is-active" : ""} onClick={() => cambiarModo("login")}>
                Iniciar sesión
              </button>
              <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "is-active" : ""} onClick={() => cambiarModo("register")}>
                Abrir cuenta
              </button>
            </div>

            {registered && (
              <div className="bk-alert bk-alert-info" role="status">
                <CheckCircle2 size={18} /> Cuenta creada. Ya puedes iniciar sesión con tu correo y contraseña.
              </div>
            )}
            {error && (
              <div className="bk-alert bk-alert-error" role="alert">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              {mode === "register" && (
                <div className="bk-field">
                  <label htmlFor="acc-nombre">Nombre</label>
                  <div className="bk-input">
                    <User size={17} />
                    <input id="acc-nombre" type="text" required value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Tu nombre" autoComplete="name" />
                  </div>
                </div>
              )}
              <div className="bk-field">
                <label htmlFor="acc-email">Correo electrónico</label>
                <div className="bk-input">
                  <Mail size={17} />
                  <input id="acc-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="tu@correo.com" autoComplete="email" />
                </div>
              </div>
              <div className="bk-field">
                <label htmlFor="acc-pwd">Contraseña</label>
                <div className="bk-input">
                  <Lock size={17} />
                  <input
                    id="acc-pwd"
                    type={showPwd ? "text" : "password"}
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === "register" ? "Mínimo 8 caracteres" : "••••••••"}
                    autoComplete={mode === "register" ? "new-password" : "current-password"}
                    style={{ paddingRight: 44 }}
                  />
                  <button type="button" className="bk-input-eye" onClick={() => setShowPwd(!showPwd)} aria-label={showPwd ? "Ocultar contraseña" : "Mostrar contraseña"}>
                    {showPwd ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
              </div>

              <button type="submit" className="bk-btn bk-btn-primary bk-btn-lg" disabled={loading} style={{ width: "100%", marginTop: 6 }}>
                {loading ? "Procesando…" : mode === "login" ? "Ingresar" : "Abrir mi cuenta"} <ArrowRight size={17} />
              </button>
            </form>

            <p className="bk-secure-note">
              <ShieldCheck size={18} color="#079baa" /> Conexión cifrada. Prisma BMV nunca te pedirá tu contraseña por correo.
            </p>
          </div>
        </section>
      </main>
    </>
  );
}
