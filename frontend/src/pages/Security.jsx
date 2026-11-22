import React, { useEffect, useState } from "react";
import { Header, Footer } from "../components/Header";
import { useAccount } from "../hooks/useAccount";
import { isCognito } from "../lib/auth.mjs";

export function Security() {
  const account = useAccount();
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [emailPending, setEmailPending] = useState(false);

  useEffect(() => () => account.cancelTotpEnrollment(), []);

  async function iniciar() {
    setError(""); setMessage(""); setBusy(true);
    try { setSecret(await account.startTotpEnrollment()); }
    catch (e) { setError(e.message || "No se pudo iniciar la configuración."); }
    finally { setBusy(false); }
  }

  async function confirmar(e) {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      await account.finishTotpEnrollment(code);
      setSecret(""); setCode("");
      setMessage("Autenticador verificado y configurado como segundo factor preferido.");
    } catch (err) { setError(err.message || "No se pudo verificar el autenticador."); }
    finally { setBusy(false); }
  }

  function cancelar() {
    account.cancelTotpEnrollment();
    setSecret(""); setCode(""); setError("");
  }

  async function solicitarCorreo() {
    setError(""); setMessage(""); setBusy(true);
    try {
      await account.startEmailVerification();
      setEmailPending(true);
      setMessage("Si el proveedor aceptó la solicitud, revisa tu correo para obtener el código.");
    } catch (err) { setError(err.message || "No se pudo solicitar el código."); }
    finally { setBusy(false); }
  }

  async function confirmarCorreo(e) {
    e.preventDefault();
    setError(""); setMessage(""); setBusy(true);
    try {
      await account.finishEmailVerification(emailCode);
      setEmailCode(""); setEmailPending(false);
      setMessage("Correo verificado. Ya puedes usarlo para recuperar el acceso.");
    } catch (err) { setError(err.message || "No se pudo verificar el correo."); }
    finally { setBusy(false); }
  }

  return <>
    <Header />
    <main id="main-content" className="bk-container" style={{ maxWidth: 700, padding: "60px 0" }}>
      <h1>Seguridad de la cuenta</h1>
      {!account.ready ? <p>Verificando sesión…</p> : !account.session ? <p>Inicia sesión para configurar tu autenticador.</p> :
        !isCognito ? <p>La configuración TOTP solo está disponible con Cognito.</p> : <>
          <h2>Verificación de correo</h2>
          <p>Verifica tu correo antes de usar la recuperación de contraseña. No compartas el código.</p>
          {!emailPending ? (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="bk-btn bk-btn-outline" type="button" onClick={solicitarCorreo} disabled={busy}>Enviar código al correo</button>
              <button className="bk-btn bk-btn-ghost" type="button" onClick={() => { setError(""); setMessage(""); setEmailPending(true); }} disabled={busy}>Ya tengo un código</button>
            </div>
          ) : (
            <form onSubmit={confirmarCorreo}>
              <label htmlFor="email-code">Código recibido</label>{" "}
              <input id="email-code" required inputMode="numeric" autoComplete="one-time-code"
                value={emailCode} onChange={(e) => setEmailCode(e.target.value)} />
              <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
                <button className="bk-btn bk-btn-primary" type="submit" disabled={busy}>Verificar correo</button>
                <button className="bk-btn bk-btn-outline" type="button" onClick={solicitarCorreo} disabled={busy}>Reenviar código</button>
              </div>
            </form>
          )}
          <h2>Autenticador</h2>
          <p>Configura un autenticador TOTP para solicitar un código adicional al iniciar sesión.</p>
          <p>Si ya tienes un autenticador, volver a configurarlo puede reemplazarlo. Conserva el acceso a tu correo verificado para recuperar la cuenta.</p>
          {!secret ? <button className="bk-btn bk-btn-primary" type="button" onClick={iniciar} disabled={busy}>
            {busy ? "Procesando…" : "Configurar autenticador"}
          </button> : <form onSubmit={confirmar}>
            <p>Añade manualmente esta clave a tu aplicación autenticadora. Es privada: no la compartas ni la envíes por correo.</p>
            <p><strong>Clave: <code>{secret}</code></strong></p>
            <label htmlFor="totp-code">Código de seis dígitos</label>{" "}
            <input id="totp-code" required pattern="[0-9]{6}" inputMode="numeric" autoComplete="one-time-code"
              value={code} onChange={(e) => setCode(e.target.value)} />
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button className="bk-btn bk-btn-primary" type="submit" disabled={busy}>Verificar y activar</button>
              <button className="bk-btn bk-btn-outline" type="button" onClick={cancelar} disabled={busy}>Cancelar</button>
            </div>
          </form>}
          {message && <p role="status">{message}</p>}
          {error && <p role="alert">{error}</p>}
        </>}
    </main>
    <Footer />
  </>;
}
