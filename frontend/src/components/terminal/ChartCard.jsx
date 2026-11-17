import React from "react";
import { Mascot } from "../Mascot";
import { EmptyArt } from "../Illustrations";
import { pedirExplicacion } from "../../guide/explicaciones.mjs";

/** Botón "Prismi te lo explica": abre el chat de Prismi con la explicación de la gráfica. */
export function ExplainButton({ explicar, label = "Prismi te lo explica", tour }) {
  if (!explicar) return null;
  return (
    <button
      type="button"
      className="tm-explain"
      data-tour={tour}
      onClick={() => pedirExplicacion(explicar())}
      title="Pídele a Prismi que te explique esta gráfica"
    >
      <span className="tm-explain-face" aria-hidden="true">
        <Mascot size={22} expression="happy" title="" />
      </span>
      {label}
    </button>
  );
}

/** Tarjeta de gráfica con encabezado, botón de Prismi y pie opcional. */
export function ChartCard({ title, subtitle, explicar, tour, explainTour, foot, children, className = "", actions }) {
  return (
    <section className={`bk-card tm-chart ${className}`} data-tour={tour}>
      <header className="tm-chart-head">
        <div style={{ minWidth: 0 }}>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", justifyContent: "flex-end" }}>
          {actions}
          <ExplainButton explicar={explicar} tour={explainTour} />
        </div>
      </header>
      <div className="tm-chart-body">{children}</div>
      {foot && <footer className="tm-chart-foot">{foot}</footer>}
    </section>
  );
}

/** Estado vacío, de carga o bloqueado por plan. */
export function Estado({ loading, locked, titulo, texto, children }) {
  if (loading) {
    return (
      <div className="tm-empty" aria-busy="true">
        <Mascot size={54} expression="thinking" title="Prismi está cargando los datos" />
        <p>Cargando datos del lakehouse…</p>
      </div>
    );
  }
  return (
    <div className="tm-empty">
      <EmptyArt locked={locked} />
      {titulo && <h3>{titulo}</h3>}
      {texto && <p>{texto}</p>}
      {children}
    </div>
  );
}
