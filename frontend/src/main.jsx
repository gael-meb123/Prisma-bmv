import React from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/manrope/latin-400.css";
import "@fontsource/manrope/latin-500.css";
import "@fontsource/manrope/latin-600.css";
import "@fontsource/manrope/latin-700.css";
import "@fontsource/manrope/latin-800.css";
import App from "./App";
import { AccountProvider } from "./hooks/useAccount";
import "./styles.css";
import "./public-ui.css";
import "./print.css";
import "./bank.css";

class ErrorBoundary extends React.Component {
  state = { failed: false, error: null };

  static getDerivedStateFromError(error) {
    return { failed: true, error };
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="information-page container" style={{ padding: "80px 20px", textAlign: "center" }} role="alert">
          <h1 style={{ color: "var(--navy)" }}>No pudimos cargar esta vista</h1>
          <p style={{ color: "var(--muted)" }}>
            Ocurrió una excepción en la interfaz. No se presentarán datos inconsistentes.
          </p>
          <button
            className="button button-primary"
            onClick={() => {
              window.location.hash = "/";
              window.location.reload();
            }}
          >
            Volver al inicio
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AccountProvider>
        <App />
      </AccountProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
