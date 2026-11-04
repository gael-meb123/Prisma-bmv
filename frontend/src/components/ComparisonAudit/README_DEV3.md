# Módulo 3 (React): Auditoría Temporal ($t+1$ a $t+5$), Gráficas Plotly y Gobernanza AWS
## Guía de Desarrollo para Desarrollador 3

> **Tu Misión:** Desarrollar y mantener los componentes de visualización interactiva y auditoría temporal en `src/components/ComparisonAudit/`.

---

### 1. Tu Territorio de Trabajo
* Carpeta: `src/components/ComparisonAudit/`
* Componentes principales:
  * `TerminalChartPlotly.jsx`: Gráfica interactiva de la serie oficial en Plotly.js (`react-plotly.js` y `plotly.js-dist-min`).
  * `ComparisonAudit.jsx`: Timeline de maduración sesión por sesión ($t$ a $t+5$) y diagrama de arquitectura AWS Data Lakehouse.
* Guía de contexto: `README_DEV3.md`
* No necesitas tocar código de Mercado ni de Selección.

---

### 2. Contrato de Props Recibidas en `TerminalChartPlotly.jsx`
* `serie`: Arreglo de cotizaciones históricas ponderadas `[{ fecha: "2026-09-08", ppp: 47.10 }, ...]`.
* `ticker`: Símbolo bursátil graficado (e.g. `"WALMEX"`).
* `sector`: Sector económico.

---

### 3. Funcionalidades a Validar
* Gráfica fluida con hover tooltips detallados mostrando fecha y precio exacto.
* Punto diamante destacado que marca la cotización activa de la sesión $t$.
* Tarjetas de las 5 sesiones de maduración bursátil hasta el cómputo final del payoff $Y_t$.
