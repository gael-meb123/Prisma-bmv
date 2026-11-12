# Prisma BMV — Documentación del proyecto

> Plataforma de analítica cuantitativa para la Bolsa Mexicana de Valores (BMV).
> Última actualización: noviembre 2026.

---

## 1. Qué es Prisma BMV

Prisma BMV es una terminal web de análisis cuantitativo para emisoras del IPC de la Bolsa Mexicana de Valores. Su idea central es trabajar con el **PPP (Precio Promedio Ponderado)** oficial que publica la BMV en su boletín diario, en lugar del precio de cierre. El PPP pondera todo el volumen de la sesión y es más difícil de mover con pocas operaciones.

Sobre esos datos la plataforma ofrece:

- **Monitor de mercado:** las 15 emisoras del IPC con su PPP oficial, el PPP anterior y la variación. Si una emisora no aparece en el boletín se muestra con guion; no se imputan datos.
- **Verificación de integridad:** cada boletín tiene una huella **SHA-256** que se puede revisar desde la terminal («Ver evidencia»).
- **Panel G2 (inferencia):** cinco modelos oficiales de regresión logística agrupada y adaptativa (optimizados con Newton-Raphson IRLS en doble precisión `float64`) más el modelo campeón extendido con señal de subasta de cierre estiman la probabilidad de que el PPP ajustado por dividendos suba en 5 sesiones ($t+5$):
  - **V1** Calibrado (`G2_V1_POOLED_REL3_CALIBRADO`)
  - **V2** Zona Neutral (`G2_V2_POOLED_REL3_ZONA_NEUTRAL`)
  - **V3** Alta Discriminación (`G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO`)
  - **V4** Agotamiento Corto DM5 (`G2_V4_POOLED_REL3_MAS_VELOCIDAD_CORTA_DM5`)
  - **V5** Adaptativo por Régimen y Sector (`G2_V5_ADAPTATIVO_REGIMEN_Y_SECTOR`)
  - **Campeón extendido (`G2_V4_F1_GAP`):** incorpora la señal intradiaria `gap_uh_ppp = (ultimo_bmv_mxn - ppp_bmv_mxn) / ppp_bmv_mxn` del propio boletín oficial BMV (acierto fuera de muestra `52.60%` en 15 emisoras y `52.71%` en emisoras foco, `Rank IC = +0.0202`, `BSS = +0.499%`).
  - **Challengers V6 en Shadow (`G2_V6A_JERARQUICO`, `G2_V6B_DESCOMPUESTO`, `G2_V6C_RIDGE_CONTINUO`, `G2_LGBM_CHALLENGER`):** monitoreados fuera de muestra bajo regla pre-registrada de promoción.

  Si los cinco modelos oficiales coinciden, hay **consenso unánime**. Emisoras foco del panel: `WALMEX`, `GMEXICO`, `GFNORTE`, `AMX` y `FEMSA` (entrenados sobre el panel completo de 15 emisoras del IPC).
- **Higiene de etiquetas y gobernanza muestral:** ajuste del objetivo $Y_t = \mathbb{I}(\text{PPP}_{\text{adj}, t+5} > \text{PPP}_t)$ por 284 eventos corporativos verificados (282 dividendos y 2 splits) y separación estricta entre muestra de diseño (`IN_SAMPLE_DISENO < 2026-11-06`) y muestra prospectiva pre-registrada (`OUT_OF_SAMPLE_PRE_REGISTRADO >= 2026-11-06`).
- **Política de asignación de capital ¼-Kelly:** dimensionamiento continuo consciente de costos de transacción (20 bps round-trip, zona de abstención $p < 0.52$, tope 25% por emisora y 75% de exposición bruta), con Retorno Neto `+6.94%`, Sharpe Bruto `+1.42`, Sharpe Neto `+1.04` y Max Drawdown `-3.46%` en TEST.
- **Auditoría temporal:** cinco sesiones después, cada señal se compara con el PPP oficial verificado en $t+5$, sin borrar errores ni alterar coeficientes congelados.
- **Ficha de la señal:** resumen exportable e imprimible.
- **Prismi:** asistente cuantitativo interactivo que guía al usuario, responde preguntas sobre los 5 modelos G2, métricas de calibración y asignación ¼-Kelly, y ofrece un recorrido guiado por la aplicación.

Prisma BMV no es asesoría de inversión.

---

## 2. Arquitectura

```
┌──────────────────────────┐     JWT (Bearer)     ┌──────────────────────────┐
│ Frontend React + Vite    │ ───────────────────▶ │ Backend FastAPI          │
│ localhost:5173           │                      │ localhost:8000/api       │
│                          │ ◀─────────────────── │ lee CSV con pandas       │
└───────────┬──────────────┘                      └───────────┬──────────────┘
            │ login / registro / RPC                          │ valida token y
            ▼                                                 ▼ lee perfil (service_role)
┌────────────────────────────────────────────────────────────────────────────┐
│ Supabase: Auth (usuarios, contraseñas, sesiones) + Postgres (profiles, RLS) │
└────────────────────────────────────────────────────────────────────────────┘
```

| Capa | Tecnología |
|---|---|
| Frontend | React 19, Vite, enrutamiento por hash, Plotly.js, lucide-react, `@supabase/supabase-js` |
| Backend | Python, FastAPI, Uvicorn, pandas, python-dotenv |
| Autenticación y datos de usuario | Supabase Auth + Postgres con Row Level Security |
| Asistente | API de Anthropic (Claude) vía `core/claude_bot.py` |
| Datos de mercado | CSV generados por el pipeline de datos (boletines BMV, señales G2) |

---

## 3. Estructura de archivos

### Backend (raíz del proyecto `C:\Users\diego\Desktop\Prisma-bmv`)

```
api.py                     API REST (FastAPI)
.env                       variables del backend (NO subir a git)
core/
  supabase_auth.py         validación de token, roles, planes, operaciones de admin
  claude_bot.py            respuestas de Prismi con Claude
  data_provider.py         carga de CSV (monitoreo, señales G2, serie WALMEX)
  auth.py                  [OBSOLETO] login local con usuarios.json — ver §12
scripts/
  _supabase.py             utilidades compartidas
  crear_usuario_demo.py    crea/actualiza demo@prismabmv.com
  prueba_permisos.py       pruebas automáticas de permisos (29 casos)
usuarios.json              [OBSOLETO] usuarios locales — ver §12
views/, test_saas_app_structure.py   versión anterior en Streamlit — ver §12
```

### Frontend (`frontend/src`)

```
App.jsx                    rutas, protección de la terminal, módulos
main.jsx                   monta <AccountProvider><App/></AccountProvider>
plans.mjs                  definición de planes y matriz de acceso
styles.css, public-ui.css, print.css
lib/supabase.mjs           cliente Supabase
services/api.mjs           cliente del backend (token, 401/403, mocks)
hooks/
  useAccount.jsx           sesión, perfil, rol, plan
  useCatalog.js            carga fechas, mercado, señales y serie
mocks/mockData.js          datos de respaldo si el backend no responde
pages/
  Landing.jsx              página principal
  Access.jsx               inicio de sesión y registro
  TerminalGate.jsx         bloqueo de la terminal sin sesión
  Plans.jsx                planes y botón de cambio simulado
  Admin.jsx                gestión de usuarios (solo admin)
  Information.jsx          Metodología, Fuentes, Estados
  Report.jsx               ficha de la señal
components/
  Header.jsx               navegación, plan, Admin, entrar/salir
  Guide.jsx + guide.css    Prismi: globo, chat, ofertas de tour
  Tour.jsx + tour.css      motor del recorrido guiado
  Mascot.jsx + mascot.css  Prismi en SVG animado
  PlanGate.jsx             aviso de emisora bloqueada por plan
  LoadingDialog.jsx, EvidenceDialog.jsx, PrismiPulse.jsx, UI.jsx
  MarketSelection/         módulo 1: monitor de mercado
  AnalysisPanel/           módulo 2: inferencia G2
  ComparisonAudit/         módulo 3: auditoría + gráfica Plotly
guide/
  tour.mjs                 pasos del recorrido y progreso guardado
  moments.mjs              mensajes de Prismi según pantalla y sesión
utils/presentation.mjs
```

---

## 4. Planes

Definidos en `frontend/src/plans.mjs` y replicados en `core/supabase_auth.py`. **El backend es la fuente de verdad.**

| ID | Nombre | Precio | Emisoras | Comparar | PDF | Consultas Prismi/día* |
|---|---|---|---|---|---|---|
| `explorer` | Explorer | $0 USD/mes | WALMEX | No | No | 5 |
| `professional` | Professional | $49 USD/mes | Las 15 del IPC | Sí | Sí | 100 |
| `enterprise` | Enterprise | $199 USD/mes | Las 15 del IPC | Sí | Sí | Ilimitadas |

\* La cuota de Prismi está definida pero **aún no se aplica** (pendiente, §12).

Emisoras del IPC: WALMEX, GMEXICO, GFNORTE, AMX, FEMSA, CEMEX, BIMBO, GAP, PE&OLES, AC, ASUR, GFINBUR, VESTA, LIVEPOL, GRUMA.

**Cambio de plan:** en modo demostración el propio usuario puede cambiar su plan desde `#/planes` o desde el selector del encabezado. Es un cambio simulado, sin cobro. Cuando haya pagos reales se elimina (§12).

---

## 5. Usuarios y roles

### Roles

| Rol | Puede |
|---|---|
| `user` | Usar la terminal según su plan. Cambiar su propio plan (modo demo). |
| `admin` | Todo lo anterior + ver todos los usuarios, crear usuarios, cambiar rol y plan de cualquiera. No puede quitarse su propio rol de admin. |

### Reglas

- Todo usuario nuevo nace como **`user` / `explorer`**, sin importar lo que mande el formulario.
- El registro es abierto desde `#/registro` y el admin también puede dar de alta usuarios desde `#/admin`.
- **Confirmación de correo desactivada** por ahora (Supabase → Authentication → Providers → Email → *Confirm email*). Se puede activar después sin cambiar código.
- Las contraseñas las guarda Supabase (bcrypt); la app nunca las ve.

### Cuentas actuales

| Correo | Rol | Plan |
|---|---|---|
| diego2883.azul@gmail.com | admin | explorer |
| demo@prismabmv.com | user | professional (se crea con `scripts/crear_usuario_demo.py` o desde `#/admin`) |

---

## 6. Base de datos (Supabase)

Script completo: `fase0_supabase.sql` (se ejecuta una vez en *SQL Editor*).

### Tabla `public.profiles`

| Columna | Tipo | Notas |
|---|---|---|
| `id` | uuid PK | referencia a `auth.users(id)`, borrado en cascada |
| `email` | text | |
| `nombre` | text | default `''` |
| `rol` | text | `user` \| `admin`, default `user` |
| `plan` | text | `explorer` \| `professional` \| `enterprise`, default `explorer` |
| `creado_en` | timestamptz | default `now()` |

### Funciones y trigger

| Objeto | Qué hace |
|---|---|
| `crear_perfil_al_registrar()` + trigger `al_crear_usuario` | Crea el perfil al insertar en `auth.users`. Solo toma `nombre` de los metadatos. |
| `es_admin()` | `security definer`; evita recursión de RLS al comprobar si el usuario es admin. |
| `cambiar_plan_demo(nuevo_plan)` | Única forma en que un usuario cambia **su** plan (nunca su rol). Ejecutable solo por `authenticated`. |

### Políticas RLS

| Política | Operación | Regla |
|---|---|---|
| `perfil_propio_o_admin_lee` | SELECT | su propio perfil, o todos si es admin |
| `admin_actualiza` | UPDATE | solo admin |
| — | INSERT / DELETE | sin política: nadie desde el cliente (el trigger crea, la cascada borra) |

Para hacer admin a alguien manualmente:

```sql
update public.profiles set rol = 'admin' where email = 'correo@ejemplo.com';
```

---

## 7. Backend (API)

Arranque: `uvicorn api:app --reload --port 8000` desde la raíz del proyecto.

### Autenticación

`core/supabase_auth.py` recibe `Authorization: Bearer <jwt>` y:

1. Valida el token con Supabase (`GET /auth/v1/user`). Funciona con cualquier algoritmo de firma y detecta tokens vencidos o revocados.
2. Lee rol y plan de `profiles` con la clave `service_role`.
3. Guarda el resultado en caché 30 s. Los cambios hechos desde el panel admin limpian la caché al instante.

Dependencias de FastAPI: `usuario_actual`, `requiere_admin`, y la función `exigir_emisora(usuario, emisora)`.

### Endpoints

| Método | Ruta | Acceso | Notas |
|---|---|---|---|
| GET | `/api/mercado/fechas` | Público | Fechas disponibles |
| GET | `/api/mercado/resumen?fecha=` | Público | KPIs + cotizaciones |
| GET | `/api/metricas/modelos` | Público | Métricas institucionales (`BSS`, `IC`, `ECE`, $\lambda_{\text{Cox}}$, $N_{\text{eff}}$), diagrama de confiabilidad, separación muestral y pesos ¼-Kelly |
| GET | `/api/me` | Sesión | Perfil verificado: id, email, nombre, rol, plan, emisoras |
| GET | `/api/senales/panel?fecha=&emisora=` | Sesión | Sin `emisora`: solo las de su plan (5 modelos G2 + estado de resolución y muestra). Emisora fuera del plan → **403** |
| GET | `/api/serie/{ticker}` | Sesión | Serie histórica verificada |
| POST | `/api/chat/prismi` | Sesión | Respuesta de Claude. Requiere `ANTHROPIC_API_KEY` |
| GET | `/api/admin/usuarios` | Admin | Lista de perfiles |
| POST | `/api/admin/usuarios` | Admin | Alta: nombre, email, password (mín. 8), rol, plan. Nace confirmado |
| PATCH | `/api/admin/usuarios/{id}` | Admin | Cambia rol, plan o nombre |

Códigos: **401** sin sesión o token inválido · **403** plan o rol insuficiente · **503** Supabase inaccesible · **500** falta una variable de entorno.

Se eliminaron `/api/auth/login` y `/api/auth/register`: el inicio de sesión lo hace el frontend directamente con Supabase.

CORS: orígenes tomados de `CORS_ORIGINS` (por defecto `http://localhost:5173`).

---

## 8. Frontend

### Rutas

| Ruta | Pantalla | Requiere |
|---|---|---|
| `#/` | Landing | — |
| `#/acceso` | Iniciar sesión | — |
| `#/registro` | Crear cuenta (mismo formulario en modo registro) | — |
| `#/planes` | Planes | — (cambiar plan requiere sesión) |
| `#/metodologia`, `#/fuentes`, `#/estados` | Información | — |
| `#/sistema` | Terminal: gráfica + 3 módulos | **Sesión** |
| `#/ficha` | Ficha de la señal | **Sesión** |
| `#/admin` | Gestión de usuarios | **Admin** |

Sin sesión, `#/sistema` y `#/ficha` muestran `TerminalGate` (qué incluye Explorer + botones de entrar y registrarse).

### Terminal (`#/sistema`)

- Izquierda: gráfica Plotly de la serie PPP.
- Derecha, tres módulos:
  1. **Selección de mercado:** tabla de emisoras + sello SHA-256.
  2. **Inferencia IA (G2):** KPIs, barras de V1/V2/V3, consenso, accesos a auditoría y ficha.
  3. **Auditoría temporal (t+5).**
- Elegir una emisora fuera del plan abre `PlanGate`.

### Sesión (`hooks/useAccount.jsx`)

Expone: `user`, `role` (id del plan), `userRole` (`user`/`admin`), `plan`, `profile`, `session`, `ready`, y las acciones `enter`, `register`, `leave`, `switchPlan`, `refreshProfile`.

- Escucha `onAuthStateChange` de Supabase.
- El perfil se pide a `/api/me` (no se confía en datos locales).
- Al iniciar o cerrar sesión, o al cambiar de plan, `App` se vuelve a montar (clave `idUsuario:plan`) para recargar los datos con los permisos nuevos.

### Cliente del backend (`services/api.mjs`)

- Adjunta el token de Supabase en cada petición.
- Sin sesión **no pide** rutas protegidas; devuelve `null` y se usan los mocks. Solo `/mercado/*` se pide sin token.
- **401 con token:** cierra sesión y manda a `#/acceso`.
- **403:** lanza `APIError` con el mensaje del backend.
- Backend apagado: usa `mocks/mockData.js`.
- Métodos: `api.me`, `getFechas`, `getMercado`, `getSenales`, `getSerie`, `chatPrismi`, `api.admin.listarUsuarios`, `crearUsuario`, `actualizarUsuario`.

---

## 9. Prismi y el recorrido guiado

### Prismi

Mascota SVG animada (`Mascot.jsx`): un billete con capa y un emblema de gráficas al alza en el pecho. Tiene expresiones (`happy`, `idle`, `thinking`, `unsure`, `surprised`), poses (`idle`, `wave`, `point-left`, `point-right`, `point-up`, `fly`, `cheer`), parpadeo, mirada y respeta `prefers-reduced-motion`.

`Guide.jsx` vive en la esquina inferior derecha:

- **Globo contextual** según la pantalla (`guide/moments.mjs`).
- **Chat:** con sesión responde con Claude; sin sesión usa respuestas locales básicas. Las preguntas sobre cuenta, sesión o registro siempre se responden localmente.
- **Sabe si hay sesión:** sin sesión muestra «Iniciar sesión» y «Crear cuenta» en el globo y en el chat; al entrar saluda por nombre y menciona el plan.
- **Icono de mapa:** repite el recorrido que corresponde a la pantalla actual.

### Recorrido guiado (`Tour.jsx` + `guide/tour.mjs`)

Prismi vuela hasta cada elemento, lo resalta y lo explica con texto que se escribe solo. Navega entre rutas y cambia de módulo por sí mismo. Teclado: Esc cierra, flechas navegan.

| Parte | Cuándo se ofrece | Pasos |
|---|---|---|
| `public` | Primera visita, sin sesión | hola, PPP, pilares, planes, **acceso** (señala «Iniciar sesión»; al hacer clic termina y lleva al login) |
| `terminal` | Primera vez en la terminal con sesión | bienvenida, gráfica, módulos, monitor, sello, elegir emisora, KPIs, modelos, acciones, auditoría, final |
| `full` | Primera visita, ya con sesión | parte pública + «entrar a la terminal» + parte de la terminal (15 pasos) |

Los pasos se anclan a atributos `data-tour` en el código: `hero`, `por-que-ppp`, `capacidades`, `planes`, `cta-sistema`, `login`, `fases`, `grafica`, `monitor`, `sello`, `emisora-walmex`, `kpis`, `modelos`, `acciones`, `auditoria`.

Progreso guardado en `localStorage`:

| Clave | Significado |
|---|---|
| `prisma.tour.public.done` | Parte pública vista |
| `prisma.tour.terminal.done` | Parte de terminal vista |
| `prisma.tour.done` | Clave antigua: cuenta como ambas vistas |
| `prisma.guide.choice` / `prisma.guide.choice.terminal` | Si aceptó el tour o prefirió preguntar |

Para volver a ver las ofertas, en la consola del navegador:

```js
Object.keys(localStorage).filter(k => k.startsWith("prisma.")).forEach(k => localStorage.removeItem(k))
```

Eventos internos: `prisma:tour-start` (`detail.part`), `prisma:tour-done`, `prisma:tour-phase` (`select` | `analysis` | `audit`).

---

## 10. Configuración

### `.env` del backend (raíz del proyecto)

```
SUPABASE_URL=https://TU-PROYECTO.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...        # SECRETA: solo backend, nunca al frontend ni a git
CORS_ORIGINS=http://localhost:5173
ANTHROPIC_API_KEY=...                 # solo para el chat de Prismi con Claude
BANXICO_TOKEN=...                     # token SIE Banxico (SF43718 FIX USD/MXN, opcional con fallback local)
```

`api.py` debe cargarlo al inicio:

```python
from dotenv import load_dotenv
load_dotenv()
```

### `.env` del frontend (`frontend/`)

```
VITE_SUPABASE_URL=https://TU-PROYECTO.supabase.co
VITE_SUPABASE_ANON_KEY=...            # pública
VITE_API_URL=http://localhost:8000
```

### Dependencias

- Backend: `fastapi`, `uvicorn`, `pandas`, `pydantic`, `python-dotenv`, SDK de Anthropic.
- Frontend: `npm install` + `@supabase/supabase-js`.

### Puesta en marcha

1. Crear el proyecto en Supabase, correr `fase0_supabase.sql`, desactivar *Confirm email* y crear la cuenta admin.
2. Llenar los dos `.env`.
3. Backend: `uvicorn api:app --reload --port 8000`.
4. Frontend: `cd frontend && npm run dev`.
5. (Opcional) `python scripts\crear_usuario_demo.py`.

---

## 11. Pruebas

### Automáticas

```
python scripts\prueba_permisos.py
```

Con el backend corriendo. Crea un usuario Explorer temporal y lo borra al final; opcionalmente prueba admin y demo. Cubre 29 casos: 401 sin sesión, 403 de Explorer en GMEXICO, filtrado por plan, bloqueo de admin, RLS (solo su perfil, sin UPDATE ni INSERT directos), RPC de plan, y permisos del admin y del demo.

### Manual (5 minutos)

1. Sin sesión, `#/sistema` → pantalla de bloqueo.
2. Crear cuenta → queda en Explorer.
3. WALMEX abre; GMEXICO muestra el aviso de plan.
4. Como admin, en `#/admin` subir ese usuario a Professional.
5. El usuario nuevo ya abre GMEXICO.
6. «Salir» → `#/sistema` vuelve a la pantalla de bloqueo.

---

## 12. Pendientes y decisiones abiertas

| Tema | Estado |
|---|---|
| Retirar `core/auth.py` y `usuarios.json` | Pendiente. Aún los importan `views/landing.py`, `views/asistente_widget.py` y `test_saas_app_structure.py` (versión Streamlit). Falta decidir si esa versión se elimina. |
| Cuota diaria de Prismi (`maxQueriesPerDay`) | Definida, no aplicada. Se agregará después. |
| Cambio de plan simulado | Activo en modo demo. Con cobro real: `drop function public.cambiar_plan_demo(text);` y quitar el selector. |
| Confirmación de correo | Desactivada. Se activa en Supabase cuando se requiera. |
| Visitante sin sesión ve mocks en panel/serie | Hoy sí (vitrina). Alternativa: pedir registro. Sin decidir. |
| Aviso de plan momentáneo | Antes de cargar el perfil, `role` vale `explorer`; un Professional podría ver el aviso por un instante. Solo visual. |
| `config_saas.py` | Precio de Enterprise a $199 para igualar `plans.mjs`. |
| Arreglos heredados | `views/terminal_auditoria.py` (`ppp_oficial_bmv` → `ppp_bmv_mxn`), rutas fijas en scripts de reconstrucción, fechas fijas `2026-10-30` en `Header.jsx`/`useCatalog`, `requirements.txt`. |
| Limpieza de CSS | Reglas `.tour-*` del proyecto anterior (ATLAS) en `styles.css`; inofensivas. |

---

## 13. Historial de cambios de este ciclo

1. **Recorrido guiado con Prismi.** Nueva mascota (billete superhéroe), motor de tour que vuela entre secciones, resalta y explica; atributos `data-tour` en Landing, MarketSelection, AnalysisPanel y App.
2. **Arreglo de clics bloqueados.** `styles.css` desactivaba los clics dentro de `.guide`; `guide.css` deja el contenedor transparente a clics y reactiva todo lo de adentro.
3. **Fase 0 — Supabase.** Tabla `profiles`, trigger, `es_admin`, RLS y `cambiar_plan_demo`. Cuenta admin creada.
4. **Fase 1 — Planes unificados.** `profesional` → `professional` en frontend; precios $0/$49/$199.
5. **Fase 2 — Backend con token.** `core/supabase_auth.py`, endpoints protegidos y filtrados por plan, endpoints de admin, `/api/me`, CORS por variable. Se agregó `python-dotenv`.
6. **Fase 3 — Frontend con Supabase.** Cliente Supabase, `useAccount` real, login/registro, `api.mjs` con token y manejo de 401/403, `Plans` con RPC, `Header` con sesión y enlace Admin.
7. **Fase 4 — Panel admin** en `#/admin`.
8. **Terminal protegida y tour en dos partes.** `TerminalGate`, ruta `#/registro`, Prismi consciente de la sesión, recorrido público/terminal/completo, remontaje de la app al cambiar sesión o plan.
9. **Fases 5 y 6 — Scripts.** Creación del usuario demo y pruebas automáticas de permisos.
10. **Sin peticiones protegidas sin sesión.** `api.mjs` ya no genera 401 en el log al cargar sin sesión.
