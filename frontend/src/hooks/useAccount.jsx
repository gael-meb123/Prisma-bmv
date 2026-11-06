import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { supabase } from "../lib/supabase.mjs";
import { planById } from "../plans.mjs";

const AccountContext = createContext(null);

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function AccountProvider({ children }) {
  const [session, setSession] = useState(null);   // Supabase session (tiene .access_token)
  const [profile, setProfile] = useState(null);    // { id, email, nombre, rol, plan, emisoras }
  const [loading, setLoading] = useState(true);    // true mientras se valida la sesión

  // --- Cargar perfil verificado desde el backend ---
  const fetchProfile = useCallback(async (accessToken) => {
    try {
      const res = await fetch(`${API_BASE}/api/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!res.ok) {
        // Token vencido o inválido: cerrar sesión
        if (res.status === 401) {
          await supabase.auth.signOut();
          return;
        }
        throw new Error(`/api/me → ${res.status}`);
      }
      const data = await res.json();
      setProfile(data);
    } catch (err) {
      console.error("[Prisma] Error cargando perfil:", err);
      setProfile(null);
    }
  }, []);

  // --- Listener de sesión ---
  useEffect(() => {
    // 1. Sesión actual (si ya había una guardada)
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      setSession(s);
      if (s) {
        fetchProfile(s.access_token).finally(() => setLoading(false));
      } else {
        setLoading(false);
      }
    });

    // 2. Cambios de sesión (login, logout, token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, s) => {
        setSession(s);
        if (s) {
          fetchProfile(s.access_token);
        } else {
          setProfile(null);
        }
      }
    );

    return () => subscription.unsubscribe();
  }, [fetchProfile]);

  // --- Acciones ---
  async function enter(email, password) {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    // onAuthStateChange se encarga de cargar el perfil
  }

  async function register(email, password, nombre) {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { nombre } },
    });
    if (error) throw error;
  }

  async function leave() {
    await supabase.auth.signOut();
    setProfile(null);
    setSession(null);
  }

  async function switchPlan(newPlan) {
    // Llama a la función SQL cambiar_plan_demo (botón simulado de demo)
    const { error } = await supabase.rpc("cambiar_plan_demo", { nuevo_plan: newPlan });
    if (error) throw error;
    // Refrescar perfil para ver el cambio
    if (session) await fetchProfile(session.access_token);
  }

  async function refreshProfile() {
    if (session) await fetchProfile(session.access_token);
  }

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
    register,
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
