import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Algunas dependencias de Cognito esperan el alias de Node en el navegador.
  define: { global: 'globalThis' },
})
