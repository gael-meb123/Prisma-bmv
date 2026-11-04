# Prisma BMV - Guía Maestra de Desarrollo en Paralelo

Esta guía define el protocolo de trabajo para que tres desarrolladores (Dev 1, Dev 2 y Dev 3) trabajen simultáneamente en la interfaz web de **Prisma BMV** sin colisiones de Git, sin dependencias mutuas y con desacoplamiento total del backend.

---

## 1. Principio de Desacoplamiento (Zero-Dependency)

* **Desarrollo 100% Offline con Fallback a Mocks:**
  - El cliente `src/services/api.mjs` consulta el backend en `http://localhost:8000/api`. Si el servidor no está corriendo o si no se tienen credenciales de AWS, el sistema automáticamente conmuta a los datos simulados en `src/mocks/mockData.js`.
  - Ningún compañero necesita tener Python instalado ni conexión con AWS para programar o probar la interfaz.
* **Aislamiento Estricto de Archivos por Desarrollador:**
  - Cada compañero trabaja exclusivamente en su carpeta asignada.
  - No deben editarse los archivos asignados a otro compañero.

---

## 2. Asignación de Módulos a los Tres Compañeros

### Desarrollador 1: Monitor de Mercado BMV Oficial (PPP) y Selección
* **Su Directorio:** `src/components/MarketSelection/`
* **Su Guía de Contexto:** `src/components/MarketSelection/README_DEV1.md`
* **Componente Principal:** `MarketSelection.jsx`
* **Rama Git:** `feature/dev1-mercado`
* **Responsabilidades:**
  - Selector de emisoras del universo de 15 acciones del IPC.
  - Filtro interactivo por sector económico y buscador por ticker.
  - Tabla de cotizaciones con distintivos semánticos (`PPP_PUBLICADO_VERIFICADO` vs `NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA`).
  - Botón de auditoría que invoca el modal de evidencia con el sello hash SHA-256 del boletín.

### Desarrollador 2: Motor Predictivo IA y Consenso de Panel (G2)
* **Su Directorio:** `src/components/AnalysisPanel/`
* **Su Guía de Contexto:** `src/components/AnalysisPanel/README_DEV2.md`
* **Componente Principal:** `AnalysisPanel.jsx`
* **Rama Git:** `feature/dev2-senales-ia`
* **Responsabilidades:**
  - Visualización del precio base de inferencia $PPP_t$ y horizonte prospectivo a 5 sesiones ($t+5$).
  - Insignia de Consenso G2 (Verde para SUBIDA, Rojo para NO_SUBIDA, Ámbar para DIVERGENCIA).
  - Barras horizontales de probabilidad para los 3 modelos G2 (`V1 Calibrado`, `V2 Zona Neutral`, `V3 Alta Discriminación`) con marca central en el umbral neutral del 50%.
  - Tarjeta explicativa del factor de reversión relativa (`ret_10_rel_panel`).
  - Bloqueo freemium visual cuando se accede a emisoras Pro con el plan Explorer.

### Desarrollador 3: Auditoría Temporal ($t+1$ a $t+5$), Gráficas Plotly y Gobernanza AWS
* **Su Directorio:** `src/components/ComparisonAudit/`
* **Su Guía de Contexto:** `src/components/ComparisonAudit/README_DEV3.md`
* **Componentes Principales:** `TerminalChartPlotly.jsx` y `ComparisonAudit.jsx`
* **Rama Git:** `feature/dev3-auditoria-plotly`
* **Responsabilidades:**
  - Gráfica interactiva de la serie de precios ponderados en Plotly.js (`react-plotly.js` y `plotly.js-dist-min`), con estilo institucional, tooltips dinámicos y punto de señal activa en $t$.
  - Cronología del ciclo de vida de la señal bursátil en 5 pasos ($t$, $t+1$, $t+2$, $t+3$, $t+4$, $t+5$) hasta el cálculo del payoff $Y_t$.
  - Panel visual de arquitectura y gobernanza del Data Lakehouse en AWS (EventBridge, Lambda, S3 Medallion, Athena SQL).

---

## 3. Instrucciones de Ejecución para el Equipo

1. **Instalar dependencias:**
   ```bash
   cd frontend
   npm install
   ```

2. **Iniciar el servidor de desarrollo:**
   ```bash
   npm run dev
   ```
   Abrir en el navegador: `http://localhost:5173`

3. **Verificar que el código compila para producción sin errores:**
   ```bash
   npm run build
   ```
