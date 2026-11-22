# Continuidad de Prisma BMV

**Última actualización: 21 de noviembre de 2026.**
Este archivo permite continuar en otra conversación sin depender del historial del chat.
Los estados AWS descritos son los últimos observados: comprobarlos antes de modificar recursos.

## 1. Instrucción para quien continúe

Continúa el desarrollo de Prisma BMV desde este worktree y esta rama. Lee primero
este archivo y `docs/ENTREGA_Y_VALIDACION_USUARIO_20261121.md`. Revisa el estado Git
y las evidencias antes de editar. Hay muchos cambios acumulados **sin commit/push**:
no los descartes, reemplaces ni confundas con archivos temporales.

El objetivo es terminar la migración experimental a Cognito/API Gateway/Lambda/
Amplify y la captura segura BMV, preservando históricos y manteniendo bloqueadas
las señales que aún no tienen validación suficiente.

### Ubicación

- Worktree:
  `C:\Users\GAELMENDOZABALLARDO\.local\share\opencode\worktree\4a82ef\api-aws-aislada`
- Rama: `experimento/api-gateway-cognito`.
- Proyecto original a preservar:
  `D:\Universidad\7mo Semestre\Big Data\Proyecto final`.
- Windows/PowerShell.
- Temporal usado:
  `C:\Users\GAELMENDOZABALLARDO\AppData\Local\Temp\opencode`.

### Restricciones acordadas

- Conservar Supabase hasta completar y validar la migración.
- Preservar Bronze, Silver, Gold y catálogos; no sobrescribir históricos silenciosamente.
- Yahoo es observación secundaria: nunca PPP oficial BMV ni entrada de predicción.
- No activar Scheduler, señales, modelos o calendario 2027 por mera aprobación
  de pruebas de software: falta evidencia de los datos.
- No reactivar la Lambda antigua como reversión.
- No pedir contraseñas, claves AWS, tokens ni códigos por chat.
- Correo autorizado para pruebas humanas: `djlexus134@gmail.com`.
- El usuario autorizó costos AWS, uso de `LabRole` y pausa de la ingesta.
- El usuario informó autorización BMV por correo; conservarla y verificar su alcance.
- La versión React experimental es separada de la vista preliminar anterior.

## 2. Estado actual: ya está implementado y desplegado

### Cuentas y frontend

- Cognito tiene **registro público habilitado** en el pool principal experimental.
- Trigger posterior a confirmación crea perfil `user/explorer` mediante escritura
  condicional; no acepta privilegios del cliente ni reemplaza perfiles existentes.
- Registro, confirmación, reenvío, primer acceso, recuperación, verificación de
  correo y TOTP están implementados.
- Se probó SignUp real con identidad sintética, rechazo de código incorrecto,
  confirmación administrativa exclusivamente sintética, trigger, login SRP,
  `/api/me` y rechazo de código incorrecto de recuperación.
- **Validación humana completada el 21-11-2026 (`djlexus134@gmail.com`):**
  primer acceso, verificación de correo (`email_verified=true` confirmado en
  Cognito a las 16:49:33), recuperación de contraseña con código y consola
  DevTools sin aviso de Supabase. Registro público con un segundo correo
  humano sigue opcional.
- Se corrigió un timeout del trigger: 512 MB, timeout Lambda 5 s y SDK con
  tiempos acotados. Pasó en pool aislado y principal.
- El pool adicional de pruebas terminó con registro público deshabilitado.
  Se eliminaron únicamente las cuentas/perfiles sintéticos nuevos de esos ensayos.
- React publicado en Amplify, rama `react-demo`, **trabajo 12: SUCCEED**
  (incorpora Estadística descriptiva para los 35 componentes provisionales del
  IPC sobre `silver/ipc35_provisional/`, tarjeta de compuerta Yahoo con 35
  símbolos `.MX` verificados y selector `Panel base (15)` vs `IPC provisional (35)`
  en Mercado y Estadística; señales estrictamente bloqueadas).
- Chrome headless con seguridad web habilitada comprobó en el sitio público
  (usuario sintético, sin enviar correos) Estadística base + `IPC provisional (35)`
  para `VOLAR` (19 registros históricos, 12 PPP observados en Bronze, `2026-10-20`
  a `2026-11-20`, `Panel no disponible`), tarjeta de compuerta Yahoo, cero errores
  de consola y cero excepciones JS.
- Cuenta `djlexus134@gmail.com` promovida a **`rol: admin`** en DynamoDB el
  21-11-2026 (con autorización del usuario) para validar `#/admin` antes de
  retirar Supabase.
- Limpieza de recursos obsoletos de laboratorio completada el 21-11-2026:
  eliminados la rama Amplify `demo`, los stacks `prisma-bmv-registro-pruebas-trigger-2026`,
  `prisma-bmv-captura-aislada-2026` y `prisma-bmv-auth-registro-pruebas-2026`
  junto con el pool de pruebas vacío `us-east-1_v3pSALFxz`.
- Almacenamiento versionado `silver/ipc35_provisional/` inicializado con **19
  cortes Bronze (`2026-10-20` → `2026-11-20`)** y reporte automático de avance
  en `evidencias/operacion/avance_ventana_limpia.json` + `cortes/avance_YYYYMMDD.json`
  integrado en el recolector seguro desplegado (`49f704d7...`).
- Auditoría de las 13 filas `AMX B` (marzo–abril 2023) cerrada y archivada en
  `evidencias/auditorias/auditoria_amx_unificacion_serie_2023.json`: corresponde
  al cambio corporativo `AMX L → AMX B` del `2023-03-16` (verificado en boletines
  BMV del 15 y 16 de marzo de 2023), sin pérdida de precios; se documenta su
  exclusión en entrenamiento estricto de misma serie.
- Carga diferida de Terminal/Report + tree-shaking de Supabase en modo Cognito:
  JavaScript inicial ~417 kB, 128 kB gzip; el bloque grande de Plotly se
  descarga al abrir Terminal.

### Historial, guardia y estadística

- Lector compartido `infra/capturas_seguras.py`: valida manifiestos finales,
  rutas, tamaños, hashes, fechas y duplicados.
- Nuevos CSV en `silver/recolector_seguro/precios_ppp/`; Silver legado permanece
  en `silver/precios_ppp/`. Publicación confirmada por manifiesto inmutable en
  `silver/capturas_seguras/`.
- Guardia incorpora cortes seguros anteriores en su ventana de 21 sesiones.
  Rechaza corrupción/conflictos y no usa capturas previas incompletas.
- La API conserva **56 fechas**, último corte disponible **`2026-11-20`**
  (incluyendo las 8 capturas seguras confirmadas: 6 de octubre y `2026-11-18`
  + `2026-11-20`).
- Frontend Cognito recorre fechas y series con `paginado=true` hasta
  `siguiente=null`. Detecta cambios de snapshot, conflictos y cursores repetidos;
  no devuelve resultados parciales si falla una página.
- Página global: snapshot + una LIST + dos GET por captura; máximo 31 capturas.
  Página mensual también disponible mediante `mes=YYYY-MM`.
- Consulta de resumen por fecha evita listar todo el historial.
- Rutas legadas sin paginación conservan límite de 2.000 capturas. El frontend
  Cognito ya no depende de ese recorrido para fechas/series.
- Estadística consulta los meses del intervalo solicitado, muestra procedencia,
  SHA-256 e intervalo efectivo; exige acotar periodos que excedan 366 días.
- Panel ajustado no conectado ni declarado validado.

### Calendario y operación

- Calendario compartido en `prisma/domain/calendario_bmv.py`, usado por núcleo
  y guardia. `FERIADOS_BMV_EXTRA` ya no habilita años no validados.
- Solo 2026 admitido; cruce de año probado con calendario sintético, sin habilitar 2027.
- Scheduler real `DisparadorDiarioBMV` apunta a la Lambda segura y fue
  **habilitado (`ENABLED`) el 21-11-2026 con autorización explícita del usuario**
  después de completar diagnóstico sin escrituras, prueba aislada y primeras
  capturas productivas (`2026-11-18` y `2026-11-20`). Snapshots inmutables en
  S3: `evidencias/auditorias/scheduler_antes_activar_20261122T000052Z.json` y
  `evidencias/auditorias/scheduler_activado_20261122T000052Z.json`. Las señales
  siguen estrictamente deshabilitadas (`emision: NO_HABILITADA`). Atención:
  documentos antiguos aún mencionan `DISABLED` o el destino legado.
- Horario conservado: `cron(45 16 ? * MON-FRI *)`, `America/Mexico_City`.
- Entrada: `{"instante_programado":"<aws.scheduler.scheduled-time>"}`.
  Los reintentos conservan la fecha original en CDMX.
- Se ensayó habilitar/pausar/restaurar en un Scheduler aislado fechado en 2099.
  No invocó capturas y fue eliminado. Fue un ensayo de configuración, no de
  disparo automático productivo.
- Lambda segura: reintentos asíncronos, SQS de fallos y tres alarmas.
  Última lectura: alarmas `OK`, cero mensajes visibles/no visibles.
- En entregas anteriores se probó fallo real hacia SQS/SNS y el usuario confirmó
  recepción del correo de alerta. Mensaje sintético archivado antes de retirarlo.
- **Primeras capturas productivas nuevas completadas el 21-11-2026** tras salir
  BMV de mantenimiento, siguiendo el protocolo completo:
  - Diagnóstico sin escrituras desde Lambda (`fecha_fuente: 2026-11-20`): `BOLETIN_VALIDADO`.
  - Prueba aislada Lambda `run_id: a06703d2baa54b679d7a5ee9625edbd5`: 100 % `OK`.
  - Captura segura productiva **`2026-11-18`** (`CAPTURADO_SIN_SENALES`,
    `sha256: c44910ffde25de6d66335d16b0835c1ed3d0a36bad86b11e05527d380f70ea0b`).
  - Captura segura productiva **`2026-11-20`** (`CAPTURADO_SIN_SENALES`,
    `sha256: 96f779e7ddde021f72e7b469b7bad8fa1c774adb0df004e6ea2eaed8ae6eb4b9`),
    eliminando por completo `SILVER_AUSENTE` (ahora **0** en la ventana al 20-11,
    `COINCIDE_PPP_Y_HASH: 90`) e iniciando la ventana limpia hacia adelante en
    **1/21 sesiones** (`evidencias/auditorias/ventana_limpia_20261121T235834Z.json`).
  - Verificación posterior: API `200 OK` (56 fechas, `mes=2026-11` -> 2 capturas,
    `resumen` base 15 = 11 verificadas, `ipc35_provisional` = 35 filas con 3
    provisionales observadas y `senales: false`), SQS 0/0, 3 alarmas `OK`, y
    `DisparadorDiarioBMV` habilitado (`ENABLED`, `cron(45 16 ? * MON-FRI *)`,
    `America/Mexico_City`) con autorización del usuario para acumular 2/21 → 21/21.

## 3. Bloqueos reales y evidencia

### BMV / ventanas

BMV salió de mantenimiento el 21-11-2026 (`boletin20261118.html` y
`boletin20261120.html` entregaron HTTP 200 válidos con 3 tablas; `2026-11-04`,
`2026-11-05` y `2026-11-19` respondieron HTTP 404 en el RSS).

- Guardia AWS actualizada al corte **`2026-11-20`** (tras incorporar los 6
  boletines de octubre y capturar productivamente `2026-11-18` y `2026-11-20`):
  - `SILVER_AUSENTE`: **0** (bajó de 7 → 1 → **0**).
  - `COINCIDE_PPP_Y_HASH`: **90** (subió de 55 → 85 → **90**).
  - `CAPTURA_SEGURA_CONFIRMADA`: **8 totales** (`20, 21, 22, 23, 26, 27 oct`,
    `18 nov` y `20 nov`).
  - Fuentes no oficiales históricas restantes en la ventana: **4, 5 y 19 de noviembre de 2026**.
  - Ventana limpia hacia adelante (desde `2026-11-20`): **1/21 sesiones**
    (`evidencias/auditorias/ventana_limpia_20261121T235834Z.json`).
  - Auditoría IPC-35 actualizada sobre **19 boletines Bronze** (`2026-10-20` →
    `2026-11-20`, 0 conflictos): `evidencias/auditorias/cobertura_ipc35_20261121T235840Z.json`.
  - Reportes inmutables en S3 (`s3://prisma-bmv-datalake-tunombre-2026/evidencias/`):
    - `evidencias/gobernanza/declaracion_fuentes.json` y `declaracion_fuentes_v2.json` (incluye decisión `LabRole` y alcance público objetivo).
    - `evidencias/auditorias/incorporacion_boletines_20261121T232236Z.json`
    - `evidencias/auditorias/cobertura_ipc35_20261121T235840Z.json` (y previa `...232307Z.json`).
    - `evidencias/auditorias/ventana_limpia_20261121T235834Z.json` (y previa `...232312Z.json`).
    - `evidencias/catalogo_ipc/provisional/naftrac_2026-11-17_v1.json`
    - `evidencias/eventos_corporativos/v1/muestra_prioritaria_g2_2024_2026.{json,csv}` (**33 eventos G2 2024–2026**, Ola 1) y `cola_historica_g2_2016_2023.json` (85 eventos, Ola 2).
    - `evidencias/calendario_bmv/2027/estado.json` (`PENDIENTE_FUENTE_OFICIAL`, compuerta bloqueada).
    - `evidencias/observaciones_yahoo/estado_permiso.json` (`EN_TRAMITE`, compuerta bloqueada; `_yahoo` en `infra/api_gateway_aislada/handler.py` ya incluye las 15 emisoras documentadas con flag deshabilitado hasta aprobar permiso).
  - Evidencia previa conservada: `docs/evidencia_guardia_20261121.json`.

### Panel y modelos

- Auditoría local: 9.879 filas enlazan con histórico y PPP base.
- 13 ventanas incompletas; fórmulas comparables sin diferencias relevantes.
- Esto no certifica autenticidad, ajustes corporativos, entrenamiento ni
  ausencia de fuga temporal.
- Falta composición IPC fechada y evidencia de alias `RA → R / A` y
  `LIVEPOLC.1 → LIVEPOL / C-1`.
- Catálogo NAFTRAC del 17-11 es provisional y de un solo corte, no composición
  oficial histórica.
- Evidencia: `docs/auditoria_pendientes_20261121.json`.

### Calendario, Yahoo y permisos

- Calendario oficial BMV (`https://www.bmv.com.mx/es/grupo-bmv/calendario-de-dias-festivos`)
  volvió en línea el 21-11-2026: confirma los 11 feriados de `FERIADOS_BMV[2026]`
  y confirma que **BMV aún no publica 2027** (`has_2027=false`). Mantener 2027
  bloqueado hasta su publicación oficial.
- Se obtuvo una respuesta real Yahoo de WALMEX.MX para observación del 19-11.
  Se validaron símbolo/MXN/fecha/cierre único y se archivó en el bucket aislado
  bajo `pruebas/yahoo/58d0a85721d53151a1ae4217535c0c10105fa8915c563d951846450de8d4c15f/`.
  Incluye respuesta y procedencia. No se publicó ni alimentó Silver/modelos.
- Publicación Yahoo sigue deshabilitada en API/frontend, pendiente de alcance
  de uso/redistribución aplicable.
- AWS denegó `iam:CreateRole` para `PrismaBMVRecolectorSeguroDedicado2026`.
  **Decisión del usuario (21-11-2026):** se adopta `LabRole` de forma explícita
  por restricción de la cuenta educativa AWS Academy; registrado en
  `evidencias/gobernanza/declaracion_fuentes_v2.json` dejando constancia de que
  `LabRole` **no equivale a mínimo privilegio**. Las propuestas
  `infra/iam/confianza_recolector_seguro.json` y
  `infra/iam/recolector_seguro_minimo.json` se conservan como referencia para
  cuentas fuera de Learner Lab.
- Último gasto observado **USD 2.232**, presupuesto USD 1.00; puede actualizarse.

## 4. Lo que debe validar el usuario

**No hay confirmación humana registrada todavía. Preguntar por el resultado,
sin repetir automáticamente invitaciones ni cambiar su contraseña.**

1. **Completado (21-11-2026):** `djlexus134@gmail.com` está en `CONFIRMED` con
   `email_verified=true` (Cognito 16:49:33) y perfil `user/explorer` en
   DynamoDB; el usuario confirmó éxito en primer acceso, verificación de correo,
   recuperación de contraseña con código y ausencia del aviso de Supabase en
   DevTools (trabajo 10).
2. Usar la invitación más reciente en `#/acceso`; cambiar la contraseña temporal.
   Mínimo 12 caracteres, mayúscula, minúscula, número y símbolo.
3. Entrar a `#/seguridad`, solicitar código y verificar correo dentro de la aplicación.
4. Cerrar sesión y probar “¿Olvidaste tu contraseña?”, cambio y nuevo acceso.
5. Informar solo éxito/error de acceso, verificación y recuperación.
   No compartir códigos ni contraseñas.
6. No registrar otra vez el correo existente. Un registro humano nuevo puede
   probarse con otro correo/alias que controle, si desea acreditar ese flujo.
7. Facilitar originales BMV, calendario 2027, composición/alias y documentos
   corporativos en una carpeta local e indicar su ruta.
8. Pedir al administrador/docente un rol dedicado o permisos para crearlo y
   pasarlo a Lambda. No cambiar el LabRole compartido.

Guía detallada: `docs/ENTREGA_Y_VALIDACION_USUARIO_20261121.md`.

## 5. Recursos AWS

Cuenta `886457183564`, región `us-east-1`.
Rol autorizado: `arn:aws:iam::886457183564:role/LabRole`.

| Recurso | Identificador |
|---|---|
| React actual | https://react-demo.d315dh37vi024o.amplifyapp.com/ |
| Amplify | app `d315dh37vi024o`, rama `react-demo`, trabajo 12 (`demo` eliminada) |
| API experimental | https://j42hw8l6rl.execute-api.us-east-1.amazonaws.com |
| API de pruebas | https://qpjhzniemh.execute-api.us-east-1.amazonaws.com |
| Cognito principal | pool `us-east-1_mKU76i6gl`, cliente `3k7iv4ebko2us1bbk78v07cg09` |
| Tabla perfiles | `prisma-bmv-auth-aislado-2026-Perfiles-1JSFRU50XIG7B` |
| Cognito pruebas | pool `us-east-1_v3pSALFxz`, cliente `730sj9tfmfhk44ctctt0kaar9f` |
| Bucket productivo | `prisma-bmv-datalake-tunombre-2026` |
| Bucket artefactos/pruebas | `prisma-bmv-aislado-prueba-2026-bucket-pumqsjizexvp` |
| Bucket API sintética | `prisma-bmv-api-capturas-pruebas-2026-fuente-vtxqhzoldupn` |
| Lambda segura | `prisma-bmv-recolector-seguro-operacion-202-Funcion-soS1hmdqF61u` |
| Lambda pruebas captura | `prisma-bmv-recolector-seguro-pruebas-2026-Prueba-JvBDrsSBZZXP` |
| Guardia aislada | `prisma-bmv-guardia-senales-aislada-2026-Guardia-78j309F0yHDg` |
| Trigger principal | `prisma-bmv-registro-cognito-2026-Funcion-lVEnp8eHPvQT` |
| Trigger pruebas | `prisma-bmv-registro-pruebas-trigger-2026-Funcion-UBYXwvWcvI8h` |
| Scheduler | `DisparadorDiarioBMV`, grupo `default`, ENABLED (autorizado 21-11-2026; reversión siempre a DISABLED) |
| SQS fallos | `https://sqs.us-east-1.amazonaws.com/886457183564/prisma-bmv-recolector-seguro-operacion-2026-Fallos-lmhg8svxhDp1` |
| SNS alertas | `arn:aws:sns:us-east-1:886457183564:prisma-bmv-recolector-seguro-operacion-2026-Avisos-uH95rzMGg0KD` |

Stacks principales: `prisma-bmv-auth-aislado-2026`,
`prisma-bmv-registro-cognito-2026`, `prisma-bmv-api-aislada-2026`,
`prisma-bmv-recolector-seguro-operacion-2026`.
Descubrir recursos/parámetros con CloudFormation, sin imprimir secretos.

El bucket sintético de API conserva deliberadamente un manifiesto corrupto
del 18-11: no “repararlo” ni usarlo como fuente real.

## 6. Artefactos, reversión y evidencias AWS

| Artefacto | SHA-256 |
|---|---|
| API | `762d336a44406746d1bdaa73b50b18cfb2c2812b5485e6efc48d5b9af7c816b8` |
| Recolector | `49f704d7ce00bd4ca4b46b7a1fafc60533ae46c34f406415edbb544bb603973c` |
| Guardia | `469b1be94a8a732f19075779d915945bd57cf410c1f0b95a44f6bcc6285bcf7c` |
| Trigger | `617ed60f2025cb071292d5c28d5242c0012488d58805c989b085df001eea4331` |
| ZIP frontend trabajo 12 | `dfefe69d628c3e2000ac716b264f0c3b30a08297afcfcd9682e39645aeb261dc` |

API/recolector/guardia: `artifacts/entrega/<sha>.zip` en bucket de artefactos.
Trigger: `artifacts/registro/<sha>.zip`.

- Integración AWS aprobada: run `61442c668db34080bd4c9016ea6a2980`,
  prefijo `pruebas/recolector-seguro/<run>/`.
- Respaldo Scheduler en bucket de pruebas:
  `operacion/scheduler/respaldo-3bfc166ba5084b8681184d041f98ab6e-6bf52e6891811bf67977293fea7fd0d6201bf49c41e569adcb515243abc0e314.json`.
- API anterior (reversión directa):
  `artifacts/entrega/34f8040548bfa2557b3216f3bffa9b9a2a229bc3c91d63a61ba095b38cecdc71.zip`
  (y previa `artifacts/api-gateway/506d277e4cb7befe22b4ebcb82a27d4a2b6bcccaaa71439a373f2adabc391cf6.zip`).
- Recolector anterior:
  `artifacts/recolector-seguro/6df2dc986521b7f2bbc9adcfee99e64da093feea117704be98b646a0143c2d21.zip`.
- Frontend anterior (trabajo 10) respaldado en temporal como
  `react-demo-job10-respaldo.zip`, hash
  `0958127ae7657b3b60575bacf4fdd79f76e82be0902e995b5c7d737d807762b9` (respaldos
  previos conservados: `react-demo-job9-respaldo.zip` y
  `react-demo-job8-respaldo-0.zip`).
- Registros temporales `despliegue-*.json` contienen ArtifactKey anterior y
  change set; el archivo puede decir PREPARADO aunque la operación ya terminó:
  verificar el estado CloudFormation. La salida final confirmó UPDATE_COMPLETE.
- Para revertir registro: plantilla con `RegistroPublico=false` y frontend
  anterior, sin borrar usuarios ni perfiles.
- Toda reversión del Scheduler conserva DISABLED; no reactivar el recolector antiguo.

## 7. Archivos y herramientas importantes

| Frente | Archivos |
|---|---|
| Captura | `infra/lambda/recolector_seguro/handler.py`, `prueba_aws.py` |
| Guardia | `infra/lambda/guardia_senales/handler.py`, `infra/lambda_guardia_adapter.py` |
| Lectura confirmada | `infra/capturas_seguras.py` |
| API | `infra/api_gateway_aislada/handler.py`, `template.yaml` |
| Paginación frontend | `frontend/src/services/historyPages.mjs`, `api.mjs` |
| Cognito | `infra/auth_aws_aislado/post_confirmacion.py`, `template.yaml`, `template_registro.yaml` |
| Acceso | `frontend/src/lib/auth.mjs`, `cognitoRegistration.mjs`, `cognitoRecovery.mjs`, `frontend/src/pages/Access.jsx`, `Security.jsx` |
| Estadística | `frontend/src/components/terminal/Estadistica.jsx`, `prisma/data/estadistica_descriptiva.py` |
| Yahoo | `prisma/data/yahoo_secundario.py`, `frontend/src/components/terminal/ObservacionSecundaria.jsx` |
| Calendario | `prisma/domain/calendario_bmv.py`, `bmv_core.py` |
| Catálogo | `prisma/domain/catalogo_ipc.py` (incluye `cargar_catalogo_versionado`), `prisma/domain/catalogos/` |
| Evidencias S3 | `prisma/data/evidencias_s3.py`, `scripts/inicializar_evidencias_s3.py`, `incorporar_boletines_seguros_s3.py`, `auditar_cobertura_ipc35_s3.py`, `conciliar_eventos_corporativos.py`, `verificar_ventana_limpia_s3.py`, `validar_calendario_2027_s3.py`, `verificar_habilitacion_yahoo.py` |
| Despliegue | `scripts/desplegar_artefacto_existente.py`, `scripts/publicar_react_experimental.py`, `scripts/empaquetar_*.py` |
| Operación | `scripts/planificar_scheduler_seguro.py`, `ensayar_scheduler_seguro.py`, `inspeccionar_fallo_recolector.py` |
| Diagnóstico | `scripts/reporte_pendientes_validacion.py`, `reparar_perfil_confirmado.py` |

Configuración de build publicada:

```text
VITE_AUTH_PROVIDER=cognito
VITE_COGNITO_POOL_ID=us-east-1_mKU76i6gl
VITE_COGNITO_CLIENT_ID=3k7iv4ebko2us1bbk78v07cg09
VITE_API_URL=https://j42hw8l6rl.execute-api.us-east-1.amazonaws.com
VITE_REQUIRE_REAL_API=true
VITE_COGNITO_SELF_SIGNUP=true
VITE_YAHOO_OBSERVACIONES=false
```

Atención: la variable correcta es `VITE_COGNITO_POOL_ID`, no `...USER_POOL_ID`.
El frontend se publica manualmente; las variables no se obtuvieron de una
configuración de build automática de la rama Amplify.

## 8. Pruebas y entorno de ejecución

Última verificación: **115 pruebas pytest + 11 subtests, 37 Node**, lint
(0 errores), build y pruebas AWS/HTTP/Chrome sobre trabajo 12 + API/Recolector
IPC-35 + `silver/ipc35_provisional/` (19 cortes) + limpieza de recursos de
laboratorio aprobados. Plan de precios y modelos: `docs/PLAN_CIERRE_PRECIOS_Y_MODELOS_IPC35.md`.
Hay avisos conocidos: paquete grande de Plotly, un setState en efecto de
Estadística y aviso de compatibilidad del plugin anyio/pytest.

Python principal tenía numpy/pandas pero no pytest/boto3. Se instalaron
dependencias auxiliares únicamente en el temporal aprobado:

```powershell
$env:PYTHONPATH="$env:LOCALAPPDATA\Temp\opencode\prisma-validacion-deps"
python -m pytest -q tests/test_dominio.py tests/test_calendario_compartido.py tests/test_recolector_seguro.py tests/test_recolector_seguro_prueba_aws.py tests/test_historial_seguro.py tests/test_api_gateway_aislada.py tests/test_admin_api_gateway_aislada.py tests/test_lambda_guardia_senales.py tests/test_post_confirmacion.py tests/test_plan_scheduler_seguro.py tests/test_recuperacion_cola.py tests/test_api_observaciones.py tests/test_auditar_panel_estadistico.py tests/test_auditar_formulas_panel.py tests/test_catalogo_ipc.py
```

Desde `frontend`:

```powershell
node --test src/services/historyPages.test.mjs src/lib/cognitoRegistration.test.mjs src/lib/cognitoRecovery.test.mjs src/lib/emailVerification.test.mjs src/lib/totp.test.mjs
npm run build
```

Configurar las variables anteriores antes de compilar para publicar.

Pruebas que **sí modifican recursos sintéticos**, ejecutar solo si hace falta:

- `scripts/probar_registro_cognito_aislado.py --principal-sintetico` crea y
  elimina una identidad aleatoria `@example.invalid`; confirma administrativamente
  solo esa identidad. Sin el flag apunta al pool de pruebas, cuyo registro ahora
  está deshabilitado: prepararlo explícitamente antes de repetir.
- `scripts/probar_serie_aws_aislada.py --renovar-solo-usuario-sintetico`
  cambia contraseña únicamente de `prisma-prueba-2026@example.invalid`.
  Variante `--senales-bloqueadas` verifica 503/403/401.
- `scripts/probar_react_local_aws.py --solo-usuario-sintetico` usa Chrome CDP.
  En el último ensayo se configuraron `APP_ORIGIN` al sitio público,
  `DEBUG_URL=http://127.0.0.1:19347` y `CORS_LOCAL_DESHABILITADO=false`.
  **Ese Chrome fue cerrado al terminar**; no asumir que sigue disponible.

Los clientes Lambda pueden agotar su tiempo aunque la ejecución termine:
revisar resultado/CloudWatch antes de repetir; usar run_id nuevo y cliente sin
reintentos automáticos para no duplicar pruebas.

## 9. Primeros pasos de la siguiente conversación

1. Leer este archivo, la guía de entrega y `git status`; conservar el trabajo.
2. Preguntar al usuario si completó acceso, correo y recuperación. Revisar
   estado Cognito solo si es necesario; no reenviar otra invitación por defecto.
3. Comprobar sesión AWS con `aws sts get-caller-identity` y estado de
   Scheduler/API cuando se vaya a trabajar con ellos. Si expiró el laboratorio,
   el usuario renueva credenciales en su entorno, no en el chat.
4. Procesar los documentos que aporte el usuario: conservar originales y hashes,
   auditar las fechas faltantes y conciliar conflictos sin sobrescribir.
5. Completar validación de eventos corporativos, composición/alias y modelos.
   La coincidencia aritmética ya comprobada no sustituye esta validación.
6. Cuando BMV entregue un boletín válido: diagnóstico sin escrituras → prueba
   aislada → captura segura productiva → consulta API/frontend → revisión de
   cola/alertas. Solo entonces evaluar programación.
7. Cuando haya fuente oficial 2027: conservar evidencia, actualizar calendario
   compartido y la restricción explícita de año del recolector, probar límites
   diciembre/enero y actualizar paquetes antes de habilitar ese año.
8. Adoptar permisos mínimos solo cuando el laboratorio permita un rol dedicado
   probado. No afirmar que LabRole es de mínimo privilegio.
9. Actualizar esta continuidad y la guía con resultados nuevos. No hacer
   commit/push ni activar señales por inferencia de que “todo ya está listo”.

## Prompt breve para pegar en una nueva conversación

> Continúa Prisma BMV leyendo `CONTINUAR_PRISMA_BMV.md` en el worktree
> `C:\Users\GAELMENDOZABALLARDO\.local\share\opencode\worktree\4a82ef\api-aws-aislada`.
> La rama es `experimento/api-gateway-cognito`; hay cambios sin commit que debes
> preservar. La API IPC-35, registro Cognito (validación humana completada) y
> frontend trabajo 11 ya están publicados. El Scheduler `DisparadorDiarioBMV`
> está ENABLED sobre el recolector seguro acumulando la ventana limpia (1/21
> desde 2026-11-20), con señales, calendario 2027 y Yahoo aún bloqueados.
> No pidas credenciales/códigos por chat ni habilites señales sin validar datos.
