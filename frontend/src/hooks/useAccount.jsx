import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { authClient } from "../lib/auth.mjs";
import { planById } from "../plans.mjs";
import { setAuthToken } from "../services/api.mjs";

const AccountContext = createContext(null);

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function AccountProvider({ children }) {
  const [session, setSession] = useState(null);   // Sesión Cognito (tiene .access_token)
  const [profile, setProfile] = useState(null);    // { id, email, nombre, rol, plan, emisoras }
  const [loading, setLoading] = useState(true);    // true mientras se valida la sesión
  const versionPerfil = useRef(0);

  // --- Cargar perfil verificado desde el backend ---
  const fetchProfile = useCallback(async (accessToken, version = ++versionPerfil.current) => {
    try {
      const res = await fetch(`${API_BASE}/api/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!res.ok) {
        // Token vencido o inválido: cerrar sesión
        if (res.status === 401 && versionPerfil.current === version) {
          await authClient.auth.signOut();
          return;
        }
        throw new Error(`/api/me → ${res.status}`);
      }
      const data = await res.json();
      if (versionPerfil.current === version) setProfile(data);
    } catch (err) {
      console.error("[Prisma] Error cargando perfil:", err);
      if (versionPerfil.current === version) setProfile(null);
    }
  }, []);

  // --- Listener de sesión ---
  useEffect(() => {
    let activo = true;
    let eventoRecibido = false;
    function aplicarSesion(s) {
      const version = ++versionPerfil.current;
      setSession(s);
      setProfile(null);
      if (!s) {
        setLoading(false);
        return;
      }
      setLoading(true);
      fetchProfile(s.access_token, version).finally(() => {
        if (activo && versionPerfil.current === version) setLoading(false);
      });
    }
    // 1. Sesión actual (si ya había una guardada)
    authClient.auth.getSession().then(({ data: { session: s } }) => {
      if (activo && !eventoRecibido) aplicarSesion(s);
    }).catch(() => {
      if (activo && !eventoRecibido) aplicarSesion(null);
    });

    // 2. Cambios de sesión (login, logout, token refresh)
    const { data: { subscription } } = authClient.auth.onAuthStateChange(
      (_event, s) => {
        if (!activo) return;
        eventoRecibido = true;
        aplicarSesion(s);
      }
    );

    return () => {
      activo = false;
      versionPerfil.current++;
      subscription.unsubscribe();
    };
  }, [fetchProfile]);

  // --- Acciones ---
  async function enter(email, password) {
    const { error, challenge } = await authClient.auth.signInWithPassword({ email, password });
    if (error) throw error;
    return challenge;
    // onAuthStateChange se encarga de cargar el perfil
  }

  async function completeChallenge(value) {
    const { error, challenge } = await authClient.auth.completeChallenge(value);
    if (error) throw error;
    return challenge;
  }

  async function startPasswordReset(email) {
    const { error } = await authClient.auth.resetPasswordForEmail(email);
    if (error) throw error;
  }

  async function confirmPasswordReset(email, code, password) {
    const { error } = await authClient.auth.confirmPasswordReset(email, code, password);
    if (error) throw error;
  }

  async function startTotpEnrollment() { return authClient.auth.startTotpEnrollment(); }
  async function finishTotpEnrollment(code) { return authClient.auth.finishTotpEnrollment(code); }
  function cancelTotpEnrollment() { authClient.auth.cancelTotpEnrollment?.(); }
  async function startEmailVerification() { return authClient.auth.startEmailVerification(); }
  async function finishEmailVerification(code) { return authClient.auth.finishEmailVerification(code); }

  async function register(email, password, nombre) {
    const { error, confirmacionRequerida } = await authClient.auth.signUp({
      email,
      password,
      options: { data: { nombre } },
    });
    if (error) throw error;
    return confirmacionRequerida;
  }

  async function confirmRegistration(email, code) {
    const { error } = await authClient.auth.confirmRegistration(email, code);
    if (error) throw error;
  }

  async function resendRegistration(email) {
    const { error } = await authClient.auth.resendRegistration(email);
    if (error) throw error;
  }

  async function leave() {
    await authClient.auth.signOut();
    versionPerfil.current++;
    setProfile(null);
    setSession(null);
  }

  async function switchPlan(newPlan) {
    const { error } = await authClient.rpc("cambiar_plan_demo", { nuevo_plan: newPlan });
    if (error) throw error;
    if (session) await fetchProfile(session.access_token);
  }

  async function refreshProfile() {
    if (session) await fetchProfile(session.access_token);
  }

  // El cliente de API toma el token de aquí (ver setAuthToken en services/api.mjs).
  setAuthToken(session?.access_token);

  const role = profile?.plan || "explorer";

  const value = {
    // Estado
    user: profile ? { email: profile.email, name: profile.nombre } : null,
    role,                          // plan id: "explorer" | "professional" | "enterprise"
    userRole: profile?.rol || null, // rol del sistema: "user" | "admin"
    plan: planById(role),
    ready: !loading,              // false mientras carga, para no mostrar flash
    authReady: !loading,
    session,                      // para api.mjs: session.access_token
    profile,

    // Acciones
    enter,
    completeChallenge,
    startPasswordReset,
    confirmPasswordReset,
    startTotpEnrollment,
    finishTotpEnrollment,
    cancelTotpEnrollment,
    startEmailVerification,
    finishEmailVerification,
    register,
    confirmRegistration,
    resendRegistration,
    leave,
    switchPlan,
    refreshProfile,
  };

  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
}

export function useAccount() {
  const ctx = useContext(AccountContext);
  if (!ctx) throw new Error("useAccount debe usarse dentro de AccountProvider");
  return ctx;
}
