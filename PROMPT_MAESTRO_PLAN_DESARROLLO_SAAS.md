# MASTER BLUEPRINT & PROMPT DE DESARROLLO AGÉNTICO
## Plataforma FinTech Institucional: "Prisma BMV - Quantitative Terminal"

> **PROPÓSITO DE ESTE DOCUMENTO:**
> Este documento es la especificación maestra y prompt integral para gobernar el desarrollo de extremo a extremo de la plataforma SaaS profesional **Prisma BMV**. Define la visión de producto, la arquitectura tecnológica, los modelos de negocio freemium, el sistema de diseño UI/UX, el asistente interactivo con Claude API, la autenticación y los skills agénticos especializados para cada módulo.

---

### REGLA SUPREMA DE IDENTIDAD DE MARCA
* **CERO IDENTIDAD ACADÉMICA:** Queda estrictamente prohibido incluir cualquier mención a "Big Data", "TecNM Celaya", "Universidad", "7mo Semestre", "Proyecto Escolar" o cualquier referencia académica en la interfaz, documentación de usuario, metadatos, títulos, footers o código visible.
* **POSICIONAMIENTO:** La plataforma se presenta al 100% como una solución FinTech de inteligencia cuantitativa de grado institucional desarrollada por **Prisma BMV**, enfocada en fondos de inversión, family offices, analistas bursátiles y traders profesionales en el mercado accionario mexicano (BMV).

---

### ESTRUCTURA DEL PLAN MAESTRO

El plan se divide en 7 pilares estratégicos:
1. **Landing Page Pública de Alto Impacto (Carta de Presentación)**
2. **Sistema de Asistente Interactivo y Mascota Virtual (Onboarding + Claude API)**
3. **Modelo de Negocio Freemium Institucional (Argumentado y Gating)**
4. **Sistema de Autenticación, Usuarios y Estado de Sesión**
5. **Terminal Cuantitativa Privada (Los 3 Módulos Analíticos de IA y Mercado)**
6. **Skills Agénticos Especializados para el Desarrollo por Módulos**
7. **Roadmap de Implementación y Arquitectura de Código**

---

## PILAR 1: LANDING PAGE PÚBLICA DE ALTO IMPACTO

La página de inicio pública es la carta de presentación institucional para inversionistas y analistas:

* **Hero Section:**
  * **Titular Principal:** "Inteligencia Cuantitativa Institucional sobre la Bolsa Mexicana de Valores".
  * **Subtitular:** "Anticipe el movimiento direccional del Precio Promedio Ponderado (PPP) a 5 sesiones hábiles mediante modelos de panel multivariado, reversión a la media y auditoría criptográfica SHA-256."
  * **Call to Action (CTA) Primario:** "Comenzar Prueba Gratuita (Free Tier)".
  * **CTA Secundario:** "Ver Documentación Cuantitativa / Explorar Modelos".
  * **Badge de Confianza:** "Datos 100% Oficiales BMV • Cero Imputación Sintética • Validación Purgada Walk-Forward".
* **Sección de Propuesta de Valor ("Por qué el PPP Oficial"):**
  * Comparativa conceptual: El riesgo de operar con precios de "Último Hecho" (manipulables en subastas de cierre y con baja liquidez) frente a la estabilidad del **Precio Promedio Ponderado oficial regulado** por la BMV.
  * Rigor matemático: Demostración de modelos sin fuga temporal (*lookahead bias*), auditados con Brier Score y Log-Loss.
* **Sección de Características Clave:**
  * Ingesta y Respaldo Inmutable en Data Lakehouse en la Nube (AWS S3 + Lambda).
  * Motores de Inteligencia Artificial de 1ª Generación (Individuales) y 2ª Generación (Panel Agrupado Multiemisora).
  * Monitoreo Mark-to-Market en tiempo real ($t+1$ a $t+5$).
* **Sección de Planes y Precios (Pricing Table Freemium):**
  * Presentación de los tres niveles: *Explorer (Gratuito)*, *Professional (Trader/Analista)* y *Enterprise (Fondos/Institucional)*.
* **Footer Institucional:**
  * Enlaces a Aviso Legal Bursátil ("Los modelos son herramientas estadísticas cuantitativas, no asesoría financiera personalizada"), Términos de Servicio, Seguridad Criptográfica y Contacto Institucional.

---

## PILAR 2: SISTEMA DE ASISTENTE VIRTUAL Y MASCOTA ("PRISMI")

Un componente flotante fijo en la esquina inferior derecha de toda la aplicación que acompaña al usuario:

* **Identidad de la Mascota ("Prismi - La Gráfica Bailarina"):**
  * Un personaje animado y carismático con forma de **gráfica financiera viva y bailarina** (compuesta por barras/velas de cotización verdes y rojas con patitas, brazos y un estilo dinámico).
  * Baila de alegría cuando el mercado está al alza, realiza pasos de baile elegantes en la esquina inferior derecha para llamar la atención del usuario sin estorbar, y gesticula explicaciones con animaciones fluidas CSS/SVG.
* **Fase 1: Onboarding y Tutorial para Usuarios Nuevos (Primera Visita):**
  * Detección automática en `st.session_state`: Si el usuario no tiene cuenta o entra por primera vez, Prismi se despliega con un diálogo guiado paso a paso:
    * Paso 1: Bienvenida al ecosistema Prisma BMV y explicación rápida de qué es el target a 5 sesiones ($Y_t = \mathbb{I}(\text{PPP}_{t+5} > \text{PPP}_t)$).
    * Paso 2: Guía rápida para crear una cuenta (formulario de registro).
    * Paso 3: Selección guiada de su plan de suscripción según su perfil de inversión.
    * Paso 4: Pase directo al Dashboard Cuantitativo.
* **Fase 2: Asistente Operativo IA con Claude API (Post-Onboarding):**
  * Una vez autenticado, Prismi se convierte en un chat inteligente de soporte cuantitativo.
  * **Conectividad:** Conexión directa vía Anthropic API (`claude-3-5-sonnet` o compatible), con modo de contingencia local (*mocked fallback*) si la clave no está presente.
  * **Guardrails Estrictos de Dominio (Prompt del Sistema de Prismi):**
    * Solo responde dudas sobre el funcionamiento de Prisma BMV, interpretación de las probabilidades de los modelos, significado del PPP, sectores económicos, fórmulas de los retornos relativos (`ret_10_rel_panel`) y estado del boletín BMV.
    * **Filtro de Desconocimiento:** Si el usuario le pregunta sobre temas externos (cocina, fútbol, programación general, política, o análisis de acciones fuera de las 15 de la BMV), Prismi responde con un mensaje de frontera:
      *"Mi capacidad está restringida exclusivamente a la inteligencia cuantitativa de Prisma BMV y los modelos matemáticos del mercado accionario mexicano. No tengo información sobre temas externos a la plataforma."*
    * **Cero Consejos Financieros Ilegales:** No da órdenes de compra imperativas; explica probabilidades estadísticas: *"El modelo G2_V3 asigna un 56.35% de probabilidad de subida basado en reversión a la media relativa frente al panel."*

---

## PILAR 3: MODELO DE NEGOCIO FREEMIUM INSTITUCIONAL

Un esquema de precios viable, argumentado y adaptado a usuarios financieros:

* **Plan 1: "Explorer" (Gratuito / Freemium Permanente):**
  * **Público:** Estudiantes de finanzas, analistas junior, observadores de mercado.
  * **Acceso:**
    * Monitoreo diario del boletín oficial BMV de las 15 emisoras (datos del día anterior / diferidos).
    * Inferencia de 1ª Generación únicamente para `WALMEX *` (Modelo Control LogReg).
    * Acceso básico a Prismi (guía de onboarding y consultas básicas).
  * **Limitaciones:** Sin acceso al panel multiemisora G2, sin variables relativas ni alertas en tiempo real.
* **Plan 2: "Professional" ($49 USD / mes):**
  * **Público:** Traders activos, analistas de casa de bolsa, asesores de inversión independientes.
  * **Acceso:**
    * Monitoreo en tiempo real al cierre oficial de mercado (16:45 CDMX).
    * Acceso total a los modelos de 2ª Generación (Panel Multiemisora: WALMEX, GMEXICO, GFNORTE, AMX).
    * Modelos avanzados: Calibrado, Zona Neutral y Alta Discriminación Expandido.
    * Indicadores de reversión a la media (`ret_10_rel_panel`) y semáforo de consensos en vivo.
    * Asistente Prismi ilimitado impulsado por Claude API.
* **Plan 3: "Enterprise / Institutional" ($249 USD / mes o Contacto):**
  * **Público:** Fondos de inversión, tesorerías corporativas, family offices.
  * **Acceso:**
    * Todo lo de Professional más:
    * Acceso directo a las tablas del Data Lakehouse en AWS S3 y endpoints de consulta SQL en Amazon Athena.
    * Auditoría de hashes criptográficos SHA-256 de extremo a extremo.
    * Exportación masiva de datos en formatos Parquet, CSV y JSON con contratos de trazabilidad.
    * Soporte dedicado y calibración personalizada de zona neutral ($\tau$).

---

## PILAR 4: AUTENTICACIÓN, USUARIOS Y ESTADO DE SESIÓN

Flujo de acceso seguro y desacoplado:

* **Base de Datos de Usuarios Ligera / Session State:**
  * Almacenamiento seguro local cifrado (`usuarios.json` o SQLite cifrado con salt + hash SHA-256 de contraseñas) para persistencia sin costos de bases de datos externas.
* **Vistas de Autenticación:**
  * **Registro:** Nombre completo, correo corporativo, contraseña y selección de plan freemium.
  * **Inicio de Sesión:** Validación de credenciales y restauración del plan asignado en `st.session_state["usuario_actual"]`.
  * **Simulación de Pago:** Al seleccionar un plan de pago (Professional o Enterprise), se muestra una pasarela institucional simulada ("Modo Sandbox / Facturación Corporativa") sin cobro real, asignando inmediatamente los permisos correspondientes.
  * **Cerrar Sesión:** Botón visible en la barra superior para volver de inmediato a la Landing Page pública.

---

## PILAR 5: TERMINAL CUANTITATIVA PRIVADA (DASHBOARD)

Una vez logueado, el usuario entra a la Terminal Cuantitativa organizada en 3 módulos:

* **Módulo 1: Monitor de Mercado BMV en Vivo:**
  * Visualización de las 15 emisoras oficiales con sus precios PPP verificados.
  * Detección visual transparente de huecos bursátiles de cero imputación (`NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA`).
  * KPIs ejecutivos y desglose por sectores (Materiales, Financiero, Consumo, Telecomunicaciones, Infraestructura).
* **Módulo 2: Motor de Señales Prospectivas y Consenso IA:**
  * Tablero de control de señales para las 4 emisoras del panel.
  * Matriz de consenso (`CONSENSO_ALTO_SUBIDA`, `CONSENSO_ALTO_NO_SUBIDA`, `DIVERGENCIA_ALERTA`).
  * Desglose de probabilidades de los 6 modelos en competencia (3 de 1ª Gen y 3 de 2ª Gen).
  * Tarjeta de interpretación de reversión relativa (`ret_10_rel_panel`).
* **Módulo 3: Auditoría Temporal ($t+1$ a $t+5$) y Arquitectura Cloud:**
  * Gráficas de seguimiento temporal sesión por sesión respecto al precio base $t_0$.
  * Trazabilidad de efectividad en curso (`acierto_parcial_en_curso`) y retornos acumulados.
  * Panel de auditoría de infraestructura AWS (S3 Bronze, Silver, Gold y consultas Athena).

---

## PILAR 6: SKILLS AGÉNTICOS ESPECIALIZADOS POR MÓDULO

Para que el desarrollo agéntico se ejecute con máxima precisión, se definen los siguientes 5 skills de desarrollo:

### Skill 1: `fintech-ui-designer` (Diseño y Experiencia de Usuario)
* **Objetivo:** Garantizar que la interfaz sea oscura (*dark theme* institucional), elegante, de alta densidad visual, con tipografía limpia (Inter / Roboto Mono), usando componentes nativos de Streamlit estilizados con CSS inyectado de alto nivel.
* **Reglas:**
  * Cero aspecto de plantilla genérica; diseño tipo Bloomberg / Stripe Terminal.
  * Uso estricto de listas verticales formateadas y tarjetas de métricas elegantes.
  * Animación suave y ubicación flotante fija para la mascota Prismi.

### Skill 2: `auth-and-freemium-gatekeeper` (Control de Acceso y Modelo de Negocio)
* **Objetivo:** Gestionar el ciclo de vida de usuarios, el estado de sesión, la persistencia de cuentas y el bloqueo de funciones según el plan elegido (Explorer vs Professional vs Enterprise).
* **Reglas:**
  * Ningún dato de 2ª generación es accesible en el plan Explorer.
  * Las contraseñas deben almacenarse hasheadas con SHA-256 + salt.
  * El flujo de onboarding debe ser fluido y no intrusivo una vez completado.

### Skill 3: `market-data-engine` (Ingesta e Integridad BMV)
* **Objetivo:** Conectar la aplicación con los datos oficiales de `monitoreo_ppp_multiemisora_en_vivo.csv`, garantizando la auditoría SHA-256 de los boletines.
* **Reglas:**
  * Aplicar de forma estricta la política de cero imputación sintética (preservar huecos con etiquetas transparentes).
  * Utilizar `@st.cache_data` con tiempos de expiración controlados para máxima velocidad.

### Skill 4: `ai-consensus-visualizer` (Visualización Cuantitativa)
* **Objetivo:** Traducir los archivos de predicciones (`registro_senales_prospectivas_walmex.csv` y `registro_senales_prospectivas_panel_g2.csv`) en gráficos y semáforos ejecutivos.
* **Reglas:**
  * Mostrar siempre probabilidades en porcentaje continuo (ej. 53.59%) y su clasificación binaria.
  * Evidenciar las alertas de divergencia cuando los modelos lineales y de bosque discrepen.

### Skill 5: `claude-assistant-guardian` (Integración Segura de IA Conversacional)
* **Objetivo:** Configurar la conexión con la API de Claude y blindar el prompt del sistema para que Prismi nunca se salga de su dominio técnico ni invente información.
* **Reglas:**
  * Prompt estricto con política de denegación ante consultas ajenas a Prisma BMV.
  * Modo de simulación local cuando no haya API Key configurada, respondiendo preguntas frecuentes precalculadas del proyecto.

---

## PILAR 7: ROADMAP DE IMPLEMENTACIÓN Y ESTRUCTURA DE ARCHIVOS

```
D:\Universidad\7mo Semestre\Big Data\Proyecto final\
├── app.py                                   # Orquestador principal (Enrutador Landing/Terminal)
├── config_saas.py                           # Parámetros institucionales, planes y estilos CSS
├── core/
│   ├── auth.py                             # Gestor de usuarios, login, registro y planes
│   ├── data_provider.py                    # Lectura y caché de insumos PPP y señales
│   └── claude_bot.py                       # Cliente Claude API + Guardrails de Prismi
├── views/
│   ├── landing.py                          # Landing page pública institucional
│   ├── terminal_mercado.py                 # Módulo 1: Monitor de Mercado BMV
│   ├── terminal_senales.py                 # Módulo 2: Motor de Señales y Consenso
│   ├── terminal_auditoria.py               # Módulo 3: Seguimiento t+1 a t+5 y AWS
│   └── onboarding_modal.py                 # Mascota Prismi y modal de onboarding
└── data/ (o raíz)
    └── usuarios.json                       # Base de datos local segura de usuarios
```
