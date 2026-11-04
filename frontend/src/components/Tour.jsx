import React, { useState, useEffect } from "react";
import { X, ChevronRight } from "lucide-react";
import { TOUR_STEPS, markTourDone, tourDone } from "../guide/tour.mjs";

export function Tour({ route }) {
  const [activeStep, setActiveStep] = useState(null);

  useEffect(() => {
    // Si ya completó el tour, no lo mostramos automáticamente
    if (tourDone()) return;
    const initial = TOUR_STEPS.find((s) => s.route === route);
    if (initial) setActiveStep(initial);
  }, [route]);

  if (!activeStep) return null;

  function nextStep() {
    const currentIndex = TOUR_STEPS.findIndex((s) => s.id === activeStep.id);
    if (currentIndex >= 0 && currentIndex < TOUR_STEPS.length - 1) {
      const next = TOUR_STEPS[currentIndex + 1];
      setActiveStep(next);
      if (next.route !== route) {
        window.location.hash = next.route;
      }
    } else {
      markTourDone();
      setActiveStep(null);
    }
  }

  function closeTour() {
    markTourDone();
    setActiveStep(null);
  }

  return (
    <div
      className="tour-overlay"
      style={{
        position: "fixed",
        bottom: "90px",
        right: "24px",
        zIndex: 1001,
        maxWidth: "340px",
        background: "#062c50",
        color: "#ffffff",
        border: "1px solid #148ba4",
        borderRadius: "14px",
        padding: "16px",
        boxShadow: "0 16px 40px rgba(0, 0, 0, 0.4)",
        fontSize: "13px"
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <span style={{ fontSize: "10px", fontWeight: "800", color: "#60d7e7", textTransform: "uppercase", letterSpacing: "1px" }}>
          Tour Guiado · {activeStep.emphasis}
        </span>
        <button onClick={closeTour} style={{ background: "transparent", border: 0, color: "#ffffff", cursor: "pointer" }}>
          <X size={16} />
        </button>
      </div>

      <strong style={{ fontSize: "15px", display: "block", marginBottom: "6px" }}>
        {activeStep.title}
      </strong>
      <p style={{ margin: "0 0 14px 0", color: "#d5ecf8", lineHeight: "1.5" }}>
        {activeStep.body}
      </p>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <button onClick={closeTour} style={{ background: "transparent", border: 0, color: "#8ee3ed", fontSize: "12px", cursor: "pointer" }}>
          Saltar tour
        </button>
        <button
          onClick={nextStep}
          className="button button-primary"
          style={{ padding: "6px 14px", fontSize: "12px", background: "#079baa", borderColor: "#1fd2ea" }}
        >
          <span>Siguiente</span>
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
