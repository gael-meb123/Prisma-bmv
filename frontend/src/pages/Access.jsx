import React, { useState } from "react";
import { ArrowRight, Lock, Mail, User, Eye, EyeOff } from "lucide-react";
import { Header } from "../components/Header";
import { Button, Logo } from "../components/UI";
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
      }
    } catch (err) {
      setError(err.message || "Error inesperado. Intenta de nuevo.");
    } finally {
      setLoading(false);
    }
  }

  // Después de registrarse exitosamente, mostrar mensaje
  if (registered) {
    return (
      <>
        <Header context="auth" />
        <main id="main-content" className="information-page container" style={{ maxWidth: "460px", margin: "60px auto", padding: "0 20px" }}>
          <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "16px", padding: "32px", boxShadow: "0 16px 45px rgba(9, 42, 73, 0.08)", textAlign: "center" }}>
            <h2 style={{ color: "var(--navy)", fontSize: "22px", margin: "0 0 12px" }}>Cuenta creada</h2>
            <p style={{ color: "var(--muted)", fontSize: "14px", lineHeight: "1.6" }}>
              Tu cuenta ha sido creada. Ya puedes iniciar sesión con tu correo y contraseña.
            </p>
            <Button
              variant="primary"
              onClick={() => { setRegistered(false); setMode("login"); setPassword(""); }}
              style={{ marginTop: "16px" }}
            >
              Iniciar Sesión
            </Button>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Header context="auth" />

      <main id="main-content" className="information-page container" style={{ maxWidth: "460px", margin: "60px auto", padding: "0 20px" }}>
        <div style={{ background: "#ffffff", border: "1px solid var(--line)", borderRadius: "16px", padding: "32px", boxShadow: "0 16px 45px rgba(9, 42, 73, 0.08)" }}>
          <div style={{ textAlign: "center", marginBottom: "24px" }}>
            <span className="eyebrow">TERMINAL INSTITUCIONAL</span>
            <h1 style={{ fontSize: "24px", color: "var(--navy)", margin: "6px 0" }}>
              {mode === "login" ? "Iniciar Sesión" : "Crear Cuenta"}
            </h1>
            <p style={{ fontSize: "13px", color: "var(--muted)", margin: 0 }}>
              {mode === "login"
                ? "Accede a las señales en vivo y al consenso econométrico G2."
                : "Regístrate para acceder a Prisma BMV. Empezarás con el plan Explorer."}
            </p>
          </div>

          {error && (
            <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px", padding: "10px 14px", marginBottom: "16px", fontSize: "13px", color: "#b91c1c" }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {mode === "register" && (
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "var(--navy)", marginBottom: "4px" }}>
                  Nombre del Analista
                </label>
                <div style={{ position: "relative" }}>
                  <User size={16} style={{ position: "absolute", left: "10px", top: "11px", color: "var(--muted)" }} />
                  <input
                    type="text"
                    required
                    value={nombre}
                    onChange={(e) => setNombre(e.target.value)}
                    placeholder="Tu nombre"
                    style={{ width: "100%", padding: "8px 12px 8px 34px", borderRadius: "8px", border: "1px solid var(--line)", fontSize: "13px" }}
                  />
                </div>
              </div>
            )}

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "var(--navy)", marginBottom: "4px" }}>
                Correo Corporativo
              </label>
              <div style={{ position: "relative" }}>
                <Mail size={16} style={{ position: "absolute", left: "10px", top: "11px", color: "var(--muted)" }} />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analista@fondo.com"
                  style={{ width: "100%", padding: "8px 12px 8px 34px", borderRadius: "8px", border: "1px solid var(--line)", fontSize: "13px" }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "var(--navy)", marginBottom: "4px" }}>
                Contraseña
              </label>
              <div style={{ position: "relative" }}>
                <Lock size={16} style={{ position: "absolute", left: "10px", top: "11px", color: "var(--muted)" }} />
                <input
                  type={showPwd ? "text" : "password"}
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "register" ? "Mínimo 8 caracteres" : "••••••••"}
                  style={{ width: "100%", padding: "8px 36px 8px 34px", borderRadius: "8px", border: "1px solid var(--line)", fontSize: "13px" }}
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  style={{ position: "absolute", right: "8px", top: "7px", background: "none", border: "none", cursor: "pointer", color: "var(--muted)", padding: "4px" }}
                >
                  {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <Button
              variant="primary"
              type="submit"
              disabled={loading}
              style={{ width: "100%", justifyContent: "center", marginTop: "8px", opacity: loading ? 0.7 : 1 }}
            >
              <span>{loading ? "Cargando…" : mode === "login" ? "Entrar a Prisma BMV" : "Crear Cuenta"}</span>
              <ArrowRight size={16} />
            </Button>
          </form>

          <div style={{ textAlign: "center", marginTop: "20px", fontSize: "13px", color: "var(--muted)" }}>
            {mode === "login" ? (
              <>
                ¿No tienes cuenta?{" "}
                <button
                  type="button"
                  onClick={() => { setMode("register"); setError(""); }}
                  style={{ background: "none", border: "none", color: "#079baa", cursor: "pointer", fontWeight: "600", fontSize: "13px" }}
                >
                  Regístrate
                </button>
              </>
            ) : (
              <>
                ¿Ya tienes cuenta?{" "}
                <button
                  type="button"
                  onClick={() => { setMode("login"); setError(""); }}
                  style={{ background: "none", border: "none", color: "#079baa", cursor: "pointer", fontWeight: "600", fontSize: "13px" }}
                >
                  Inicia Sesión
                </button>
              </>
            )}
          </div>
        </div>
      </main>
    </>
  );
}
