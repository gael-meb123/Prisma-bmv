# Módulo 2 (React): Motor Predictivo IA y Consenso de Panel (G2)
## Guía de Desarrollo para Desarrollador 2

> **Tu Misión:** Desarrollar y mantener el componente del motor econométrico en `src/components/AnalysisPanel/`. Este módulo interpreta las señales de los 3 modelos G2, el consenso probabilístico y el factor de reversión relativa.

---

### 1. Tu Territorio de Trabajo
* Carpeta: `src/components/AnalysisPanel/`
* Componente principal: `AnalysisPanel.jsx`
* Guía de contexto: `README_DEV2.md`
* No necesitas tocar el código de Mercado ni de Gráficas Plotly.

---

### 2. Contrato de Props Recibidas en `AnalysisPanel.jsx`
* `ticker`: Símbolo bursátil analizado (e.g. `"WALMEX"`, `"GMEXICO"`).
* `senales`: Arreglo de señales emitidas por los 3 modelos G2 (`modelo`, `prob`, `pred`, `consenso`, `ppp_base`, `ret_rel`).
* `userRole`: Plan actual del usuario (`"explorer"`, `"profesional"`, `"enterprise"`).
* `onPlanGate(ticker)`: Callback cuando un usuario con plan explorer intenta ver una emisora bloqueada.
* `onOpenAudit()`: Callback para abrir la auditoría de maduración temporal.
* `onOpenReport()`: Callback para abrir la ficha ejecutiva de reporte.

---

### 3. Funcionalidades a Validar
* Bloqueo elegante con banner de actualización para planes que no tienen acceso al activo.
* Renderizado de las barras de probabilidad de 0% a 100% con línea divisoria de umbral en 50%.
* Distintivos semánticos de consenso (Verde para SUBIDA, Rojo para NO_SUBIDA, Ámbar para DIVERGENCIA).
