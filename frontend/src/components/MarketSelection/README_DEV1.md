# Módulo 1 (React): Monitor de Mercado BMV Oficial y Selección de Activos
## Guía de Desarrollo para Desarrollador 1

> **Tu Misión:** Desarrollar y mantener el componente de selección y auditoría de mercado oficial en `src/components/MarketSelection/`. Este módulo permite filtrar el universo del IPC, verificar cotizaciones ponderadas y auditar la integridad del boletín regulatorio.

---

### 1. Tu Territorio de Trabajo
* Carpeta: `src/components/MarketSelection/`
* Componente principal: `MarketSelection.jsx`
* Guía de contexto: `README_DEV1.md`
* No necesitas modificar código de Modelos IA ni de Auditoría Temporal.

---

### 2. Contrato de Props Recibidas en `MarketSelection.jsx`
* `cotizaciones`: Arreglo de emisoras con cotización oficial `{ emisora, serie, sector, ppp_bmv_mxn, anterior_bmv_mxn, variacion_pct, estado_captura }`.
* `selectedTicker`: Ticker actualmente enfocado (e.g. `"WALMEX"`).
* `onSelectTicker(ticker)`: Función de callback cuando el usuario hace clic en una emisora.
* `onShowEvidence(evidence)`: Función de callback para abrir el modal de sello criptográfico SHA-256.
* `sha256`: Hash criptográfico del archivo HTML original del boletín.
* `urlFuente`: Enlace oficial al boletín en `bmv.com.mx`.

---

### 3. Funcionalidades a Validar
* Búsqueda dinámica en tiempo real por ticker o sector.
* Resaltado visual de la fila activa (`#e6f6f9`).
* Insignias semánticas (`badge-available` para cotizaciones verificadas, `badge-missing` para huecos por baja liquidez).
