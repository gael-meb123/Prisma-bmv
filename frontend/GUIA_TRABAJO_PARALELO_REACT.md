# Arquitectura y Guía de Trabajo en Paralelo: Prisma BMV (React + Plotly)

Esta guía define la estrategia de desacoplamiento total para que 3 desarrolladores construyan simultáneamente la plataforma web sin bloqueos mutuos, sin dependencias de backend encendido y sin conflictos de merge en Git.

---

## 1. Estrategia de Desacoplamiento (Zero-Dependency)

* **Desarrollo 100% Offline con Fallback a Mocks:**
  - El archivo `src/services/api.js` se comunica con el backend de FastAPI (`http://localhost:8000`), pero si el backend no está encendido, automáticamente conmuta a los datos simulados en `src/mocks/mockData.js`.
  - Ningún compañero necesita tener instalado Python, ni credenciales de AWS, ni tener el backend corriendo en su máquina para diseñar, programar y probar su módulo en React.

* **Aislamiento por Directorios Exclusivos:**
  - Cada desarrollador tiene su propia carpeta de componentes y su propio archivo de documentación Markdown (`README_DEVx.md`) con las especificaciones del contrato de datos.
  - Ningún desarrollador debe tocar los archivos de las carpetas de los demás.

* **Flujo de Trabajo Git por Ramas:**
  - `feature/dev1-mercado` -> Trabaja en `src/components/MarketMonitor/`
  - `feature/dev2-senales-ia` -> Trabaja en `src/components/AIEngine/`
  - `feature/dev3-auditoria-plotly` -> Trabaja en `src/components/AuditGovernance/`
  - La rama `main` integra los componentes finales en `App.jsx`.

---

## 2. Asignación de Módulos a los 3 Compañeros

### Desarrollador 1: Monitor de Mercado BMV Oficial (PPP)
* **Directorio de trabajo:** `src/components/MarketMonitor/`
* **Guía de contexto:** `src/components/MarketMonitor/README_DEV1.md`
* **Componente principal:** `MarketMonitor.jsx`
* **Responsabilidades cuantitativas:**
  - Selector de fecha de sesión bursátil.
  - Filtro interactivo por sector económico.
  - Tarjetas de KPIs del mercado (15 emisoras, conteo de alzas/bajas, líder alcista y bajista).
  - Tabla de cotizaciones con estados de auditoría (`PPP_PUBLICADO_VERIFICADO` vs `NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA`).
  - Tarjeta de verificación criptográfica con el hash SHA-256 del boletín oficial.

### Desarrollador 2: Motor Predictivo IA y Consenso de Panel (G2)
* **Directorio de trabajo:** `src/components/AIEngine/`
* **Guía de contexto:** `src/components/AIEngine/README_DEV2.md`
* **Componente principal:** `AIEngine.jsx`
* **Responsabilidades cuantitativas:**
  - Selector de emisoras del panel cuantitativo (`WALMEX`, `GMEXICO`, `GFNORTE`, `AMX`).
  - Control de acceso Freemium: Bloqueo visual con banner para usuarios con plan `explorer` cuando intentan acceder a emisoras distintas de WALMEX.
  - Insignia visual del Consenso G2 (Verde para `CONSENSO_PANEL_G2_SUBIDA`, Rojo para `CONSENSO_PANEL_G2_NO_SUBIDA`, Ámbar para `DIVERGENCIA_PANEL_G2`).
  - Barras horizontales de probabilidad comparando las 3 variantes del modelo (`G2_V1_POOLED_REL3_CALIBRADO`, `G2_V2_POOLED_REL3_ZONA_NEUTRAL`, `G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO`) con línea de umbral en el 50%.
  - Tarjeta de interpretación estadística del factor de reversión relativa `ret_10_rel_panel`.

### Desarrollador 3: Auditoría Temporal ($t+1$ a $t+5$), Gráficas Plotly y Gobernanza Cloud
* **Directorio de trabajo:** `src/components/AuditGovernance/`
* **Guía de contexto:** `src/components/AuditGovernance/README_DEV3.md`
* **Componentes principales:** `AuditGovernance.jsx` y `PriceChartPlotly.jsx`
* **Responsabilidades cuantitativas:**
  - Gráfica interactiva de la serie de precios promedio ponderados de WALMEX utilizando Plotly.js (`react-plotly.js` y `plotly.js-dist-min`), con estilo dark institucional, tooltips dinámicos y punto de señal activa en $t$.
  - Seguimiento del ciclo de maduración de la señal bursátil en 5 pasos ($t$, $t+1$, $t+2$, $t+3$, $t+4$, $t+5$) hasta el cálculo formal del payoff.
  - Panel visual de arquitectura y gobernanza del Data Lakehouse en AWS (EventBridge, Lambda, S3 Medallion, Athena).

---

## 3. Componentes Compartidos (Ya Integrados)

* **`src/components/Navbar/Navbar.jsx`:**
  - Barra institucional con logotipo de Prisma BMV.
  - Pestañas para conmutar entre los módulos de los tres desarrolladores.
  - Selector de plan (Explorer, Professional, Enterprise) que permite probar el funcionamiento del control de acceso de Desarrollador 2.
  - Conmutador para ver la Landing Page comercial o la Terminal Cuantitativa.

* **`src/components/LandingPage/LandingPage.jsx`:**
  - Portal de presentación SaaS institucional para inversionistas y mesas de dinero.
  - Explicación de la diferencia fundamental entre el precio de cierre manipulable y el PPP oficial.
  - Tablas de precios freemium ($0 Explorer, $49 Professional, $199 Enterprise).

* **`src/components/Prismi/PrismiMascot.jsx`:**
  - Mascota animada flotante en la esquina inferior derecha: **Prismi (La Gráfica Bailarina)**.
  - Tour guiado en 3 pasos para nuevos usuarios.
  - Ventana de chat interactiva con Claude (con respuestas cuantitativas precisas y rechazo estricto a preguntas fuera de dominio).

---

## 4. Instrucciones de Ejecución Local para el Equipo

1. **Instalar dependencias (solo la primera vez):**
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
