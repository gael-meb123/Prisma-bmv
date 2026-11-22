// Cliente único de Supabase para el frontend.
// Solo usa la llave pública (anon / publishable); la service_role vive únicamente en el backend.
import { createClient } from "@supabase/supabase-js";

const useCognito = import.meta.env.VITE_AUTH_PROVIDER === "cognito";

function crearClienteSupabase() {
  const url = import.meta.env.VITE_SUPABASE_URL;
  const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    console.error(
      "[Prisma] Faltan VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY. Copia frontend/env.example a frontend/.env y complétalo."
    );
  }

  return createClient(url || "http://localhost", anonKey || "missing-anon-key", {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });
}

export const supabase = useCognito ? null : crearClienteSupabase();
