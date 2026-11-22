import React, { useState } from "react";
import { ArrowRight, CheckCircle2, Eye, EyeOff, Lock, Mail, ShieldCheck, User } from "lucide-react";
import { Header } from "../components/Header";
import { LoginArt } from "../components/Illustrations";
import { useAccount } from "../hooks/useAccount";
import { isCognito, publicRegistration } from "../lib/auth.mjs";

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
  const [challenge, setChallenge] = useState(null);
  const [code, setCode] = useState("");
  const challengeType = typeof challenge === "object" ? challenge?.type : challenge;

  function cambiarModo(m) {
    setMode(m);
    setError("");
    setRegistered(false);
    setChallenge(null);
    setCode("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        const next = challenge
          ? await account.completeChallenge(challengeType === "newPassword" ? password : code)
          : await account.enter(email.trim().toLowerCase(), password);
        if (next) {
          setChallenge(next);
          setPassword("");
          setCode("");
        } else window.location.hash = "/sistema";
      } else if (mode === "recover") {
        await account.startPasswordReset(email.trim().toLowerCase());
        setMode("confirmReset");
      } else if (mode === "confirmReset") {
        await account.confirmPasswordReset(email.trim().toLowerCase(), code, password);
        setMode("login");
        setPassword("");
        setCode("");
        setRegistered(true);
      } else if (mode === "confirmRegister") {
        await account.confirmRegistration(email.trim().toLowerCase(), code);
        setMode("login");
        setCode("");
        setRegistered(true);
      } else {
        const pendiente = await account.register(email.trim().toLowerCase(), password, nombre.trim());
        setRegistered(!pendiente);
        setMode(pendiente ? "confirmRegister" : "login");
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
          <h2>{mode === "login" ? "Bienvenido de vuelta" : mode === "register" ? "Abre tu cuenta" : "Recupera tu acceso"}</h2>
          <p>
            {mode === "login"
              ? (isCognito ? "Accede a la terminal experimental. Las señales todavía no están disponibles." : "Revisa el PPP oficial del día, las señales de tus emisoras y cómo van contra el resultado real.")
              : mode === "register" ? "Empiezas con el plan Explorer." : "Sigue los pasos para recuperar el acceso a tu cuenta."}
          </p>
          <LoginArt />
          <div style={{ display: "grid", gap: 10, fontSize: 14 }}>
            <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <CheckCircle2 size={18} color="#5fd0dc" /> Procedencia y cobertura visibles en la terminal
            </span>
            <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <CheckCircle2 size={18} color="#5fd0dc" /> Estadística descriptiva de los datos disponibles
            </span>
          </div>
        </section>

        <section className="bk-access-form">
          <div className="bk-access-box">
            <h1>{mode === "login" ? "Ingresa a tu terminal" : mode === "register" ? "Abre tu cuenta" : mode === "confirmRegister" ? "Confirma tu correo" : "Recupera tu contraseña"}</h1>
            <p style={{ margin: 0, fontSize: 14 }}>
              {challengeType === "totpSetup" ? "Añade la clave a tu aplicación autenticadora y escribe el código de seis dígitos."
                : challengeType === "newPassword" ? "Elige una nueva contraseña para completar el primer acceso."
                : challenge ? "Introduce el código de verificación MFA."
                : mode === "login" ? "Usa el correo y la contraseña de tu cuenta."
                : mode === "recover" ? "Solicita un código al correo verificado de tu cuenta."
                : mode === "confirmReset" ? "Introduce el código recibido y la nueva contraseña."
                : mode === "confirmRegister" ? "Introduce el código recibido para confirmar tu registro."
                : "Solo necesitas tu nombre, correo y una contraseña."}
            </p>

            <div className="bk-tabs" role="tablist" aria-label="Tipo de acceso">
              <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "is-active" : ""} onClick={() => cambiarModo("login")}>
                Iniciar sesión
              </button>
              {publicRegistration && <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "is-active" : ""} onClick={() => cambiarModo("register")}>
                Abrir cuenta
              </button>}
            </div>

            {registered && (
              <div className="bk-alert bk-alert-info" role="status">
                <CheckCircle2 size={18} /> Operación completada. Ya puedes iniciar sesión.
              </div>
            )}
            {error && (
              <div className="bk-alert bk-alert-error" role="alert">
                {error}
              </div>
            )}

            {challengeType === "totpSetup" && <div className="bk-alert bk-alert-info">
              Clave de configuración: <strong>{challenge.secret}</strong>. No la compartas.
            </div>}
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
              {!challenge && <div className="bk-field">
                <label htmlFor="acc-email">Correo electrónico</label>
                <div className="bk-input">
                  <Mail size={17} />
                  <input id="acc-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="tu@correo.com" autoComplete="email" />
                </div>
              </div>}
              {(["confirmReset", "confirmRegister"].includes(mode) || (challenge && challengeType !== "newPassword")) && <div className="bk-field">
                <label htmlFor="acc-code">Código de verificación</label>
                <div className="bk-input">
                  <input id="acc-code" required inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />
                </div>
              </div>}
              {!["recover", "confirmRegister"].includes(mode) && (!challenge || challengeType === "newPassword") && <div className="bk-field">
                <label htmlFor="acc-pwd">{challengeType === "newPassword" || mode === "confirmReset" ? "Nueva contraseña" : "Contraseña"}</label>
                <div className="bk-input">
                  <Lock size={17} />
                  <input
                    id="acc-pwd"
                    type={showPwd ? "text" : "password"}
                    required
                    minLength={isCognito && (challengeType === "newPassword" || ["register", "confirmReset"].includes(mode)) ? 12 : 8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === "register" ? (isCognito ? "Mínimo 12 caracteres" : "Mínimo 8 caracteres") : "••••••••"}
                    autoComplete={mode === "register" || mode === "confirmReset" || challengeType === "newPassword" ? "new-password" : "current-password"}
                    style={{ paddingRight: 44 }}
                  />
                  <button type="button" className="bk-input-eye" onClick={() => setShowPwd(!showPwd)} aria-label={showPwd ? "Ocultar contraseña" : "Mostrar contraseña"}>
                    {showPwd ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
              </div>}
              {isCognito && (mode === "register" || mode === "confirmReset" || challengeType === "newPassword") &&
                <p>Mínimo 12 caracteres, con mayúscula, minúscula, número y símbolo.</p>}

              <button type="submit" className="bk-btn bk-btn-primary bk-btn-lg" disabled={loading} style={{ width: "100%", marginTop: 6 }}>
                {loading ? "Procesando…" : challenge ? "Continuar" : mode === "login" ? "Ingresar" : mode === "recover" ? "Solicitar código" : mode === "confirmReset" ? "Cambiar contraseña" : mode === "confirmRegister" ? "Confirmar correo" : "Abrir mi cuenta"} <ArrowRight size={17} />
              </button>
            </form>
            {isCognito && publicRegistration && !challenge && (
              <button type="button" disabled={loading} className="bk-btn bk-btn-ghost" onClick={async () => {
                setError(""); setLoading(true);
                try {
                  await account.resendRegistration(email.trim().toLowerCase());
                  setMode("confirmRegister");
                } catch (err) { setError(err.message || "No se pudo reenviar el código."); }
                finally { setLoading(false); }
              }}>Reenviar código de registro</button>
            )}
            {isCognito && mode === "login" && !challenge && (
              <button type="button" className="bk-btn bk-btn-ghost" onClick={() => cambiarModo("recover")}>¿Olvidaste tu contraseña?</button>
            )}

            <p className="bk-secure-note">
              <ShieldCheck size={18} color="#079baa" /> Conexión cifrada. Prisma BMV nunca te pedirá tu contraseña por correo.
            </p>
          </div>
        </section>
      </main>
    </>
  );
}
