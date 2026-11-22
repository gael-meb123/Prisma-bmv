# Historial seguro y siguientes entregas — 21-11-2026

> Estado posterior: [ENTREGA_Y_VALIDACION_USUARIO_20261121.md](ENTREGA_Y_VALIDACION_USUARIO_20261121.md).
> El registro y frontend ya fueron desplegados; este documento conserva la
> cronología de la entrega anterior.

## Implementado

- `infra/capturas_seguras.py`: lector compartido que valida ruta exacta,
  contrato, duplicados, tamaño y hash del CSV. No escribe ni usa caché.
- La guardia busca exactamente los 21 manifiestos de su ventana, sin listar
  el bucket. Usa los cortes confirmados, valida Bronze y rechaza conflicto con
  el CSV legado. El corte en curso solo entra por el adaptador privado del
  recolector. Nunca se usa un corte parcial anterior. Señales deshabilitadas.
- API: `GET /api/mercado/fechas?mes=2026-11&limite=20&despues=2026-11-18`.
  Responde `{fechas, siguiente, mes, orden, cobertura, solicitudes_s3}`.
  Orden ascendente; `siguiente=null` significa fin del **mes**, no del historial.
  Límite 1..31; un cursor debe pertenecer al mismo mes. Página corrupta devuelve
  503 sin resultados parciales. No garantiza snapshot transaccional entre páginas:
  una captura atrasada puede requerir volver a consultar el mes.
- Resumen con `?fecha=YYYY-MM-DD`: lookup directo de manifiesto/CSV sin LIST.
  Las rutas antiguas sin parámetros conservan su contrato y el límite global
  de 2.000 para compatibilidad; no se ha eliminado esa limitación de los
  consumidores que todavía solicitan todo el historial. El cliente frontend
  expone `getCapturasMes`; no se cambia silenciosamente la lista histórica a
  una página incompleta.

## Mediciones y pruebas

La prueba con más de 2.000 claves fuera del mes verifica que cada página de una
fecha usa **1 LIST + 2 GET**. Para N fechas: **1 LIST + 2N GET**. Consulta
directa de captura: **0 LIST + 2 GET**; el resumen agrega lectura de snapshot
y las lecturas legadas que corresponda. Guardia: máximo 84 GET en una ventana
de 21 fechas (histórico, manifiesto, CSV seguro y Bronze); ninguna LIST.
Son conteos medidos con cliente instrumentado, no facturación ni benchmark
de latencia de producción.

`python -m scripts.medir_lectura_manifiestos --list-usd-1000 0.005 --get-usd-1000 0.0004`
calcula un presupuesto con tarifas **de ejemplo introducidas por el operador**.
Con 20 fechas y 1.000 consultas: 1.000 LIST y 40.000 GET, USD 0.021 por esas
solicitudes; excluye Lambda, Gateway, transferencia y reintentos. Una página
puede leer hasta 31 MB de CSV: el límite de tamaño es una defensa, no un
objetivo de latencia. Medir tamaños reales antes de ampliar cuotas.

El ZIP aislado `6df2dc986521b7f2bbc9adcfee99e64da093feea117704be98b646a0143c2d21`
pasó en AWS con run `28af3538263945d0a5d157c68dc3ecb4`: historial confirmado,
paginación, concurrencia, recuperación, conflictos, 404 simulado y copia
Bronze real del 17-11. No hubo emisión ni escrituras en Silver legado.
La API de esta entrega se empaquetó como
`506d277e4cb7befe22b4ebcb82a27d4a2b6bcccaaa71439a373f2adabc391cf6`.
En API Gateway de laboratorio se verificaron: página válida del 19-11 (200,
1 LIST + 2 GET), página con hash corrupto del 18-11 (503), resumen por fecha
del 19-11 (200) y límite fuera de rango (422). No se alteró el objeto corrupto
conservado como evidencia de la prueba anterior.

Pasaron 85 pruebas Python seleccionadas, 11 pruebas Node de registro,
recuperación, email y TOTP, y `npm run build`. El build conserva el aviso de
bundle grande; no es una medición de rendimiento del navegador. El gasto AWS
observado durante esta entrega fue USD 2.232 frente a USD 1.00 de presupuesto;
los cargos pueden actualizarse.

## Cuentas

Registro, confirmación y reenvío implementados en el frontend, con
`VITE_COGNITO_SELF_SIGNUP=false` por defecto. El trigger crea por condición
atómica un perfil `user/explorer`; ignora privilegios declarados por el cliente.
Un reintento no reemplaza un perfil ni rebaja un admin. Recuperación de
contraseña no modifica perfiles. Si falla el trigger después de confirmación,
usar `python -m scripts.reparar_perfil_confirmado` tras revisar identidad y
tabla; requiere boto3 instalado y no altera contraseñas.

Despliegue pendiente:
1. Empaquetar con `scripts/empaquetar_registro_cognito.py`.
2. Desplegar `template_registro.yaml` contra un pool/tabla de prueba.
3. Configurar `RegistroPublico=true` y `PostConfirmacionArn` en la plantilla de
   identidad, después de probar el trigger y su permiso de invocación.
4. Habilitar flag frontend y probar registro, código incorrecto/vencido,
   reenvío, primer acceso, recuperación y acceso a `/api/me`.
5. Solo después trasladar configuración al pool real.

Las pruebas de callbacks no acreditan recepción de correo ni primer acceso
real. No se han renovado contraseñas de cuentas humanas ni se han solicitado
códigos por chat.

## Estadística y Yahoo

El reporte diferencia filas de instantánea con estado declarado de capturas
con hash validado; publica SHA-256 de instantánea y ausencia de validación de
ajustes corporativos. El frontend muestra esos datos. Esto no convierte al
panel ajustado en validado: no se conectó un panel de procedencia desconocida.

`GET /api/observaciones/yahoo?emisora=WALMEX&fecha=YYYY-MM-DD` es autenticado y
respeta el plan. Lee solo JSON conservado en
`observaciones/yahoo/WALMEX.MX/YYYY-MM-DD.json`, valida símbolo, moneda y fecha,
y entrega cierre secundario con hash, nunca `ppp_bmv_mxn`.
No descarga Yahoo, no escribe Silver ni alimenta guardia/inferencia.
Backend `YahooObservacionesHabilitadas=false`; frontend
`VITE_YAHOO_OBSERVACIONES=false`. Se requiere cargar una respuesta con
procedencia y autorización aplicables antes de habilitarlo. No se inventan
alias para otras emisoras.

## Operación y 2027

- `scripts/planificar_scheduler_seguro.py` produce planes JSON sin ejecutar
  AWS: preparar desactivado, activar destino seguro, pausar o restaurar
  desactivado. Guardar `get-schedule` completo antes de cambiar; comparar
  estado inmediatamente antes de `update-schedule` para evitar perder cambios
  concurrentes (Scheduler no ofrece CAS en ese endpoint).
- El evento programado conserva `<aws.scheduler.scheduled-time>` para que
  reintentos tras medianoche procesen la fecha original en CDMX.
- `python -m scripts.inspeccionar_fallo_recolector --evidencia archivo.json`
  valida función y evento y propone la fecha original. Eventos sin fecha,
  sintéticos, o calendarios no validados no se reencolan automáticamente.
  Archivar/verificar evidencia antes de retirar un mensaje, jamás purgar la cola.
- `infra/iam/recolector_seguro_minimo.json` es una **propuesta no aplicada**:
  GET de fuentes admitidas, PUT condicional solo en salidas seguras, cola y
  logs. Requiere log group precreado y probar 404 frente a 403 con el rol real.
  No restringir el `LabRole` compartido: usar un rol dedicado cuando el
  laboratorio permita crearlo. No afirmar mínimo privilegio mientras use LabRole.
- BMV devolvió mantenimiento para el calendario oficial. 2027 sigue
  `PENDIENTE_FUENTE_OFICIAL`, sin inventar feriados. Para validarlo: conservar
  documento oficial y hash, comprobar alcance/año, unificar guardia y núcleo,
  probar ventanas diciembre–enero y feriados, y entonces habilitar el año.
  No usar `FERIADOS_BMV_EXTRA` como prueba de autorización ni de calendario.

Esta entrega no activa el Scheduler ni modelos y no sustituye Supabase.

## Estado final del despliegue

- API experimental `prisma-bmv-api-aislada-2026`: actualizado al ZIP `506d...`,
  capturas habilitadas y observaciones Yahoo deshabilitadas. Salud y resumen
  por fecha: 200; se preservan las 54 fechas históricas. Página mensual vacía:
  200 con 1 LIST y 0 GET porque aún no hay capturas seguras productivas.
  Ruta Yahoo sin token: 401.
- Lambda segura de operación: actualizada a `6df2...`, `Active/Successful`.
  La nueva integración fue ejecutada en la Lambda de prueba aislada; no se
  realizó captura productiva ni emisión.
- Pruebas autenticadas con usuario sintético: serie y estadística 200;
  fuera de plan 403; sin token y con ID token 401; señales y seguimiento 503.
- Frontend compilado localmente, **no publicado en Amplify** en esta entrega.
  Trigger de registro y plantilla de identidad **no desplegados**; están
  implementados y probados localmente y las plantillas fueron validadas por
  CloudFormation. No se ha completado el ciclo real de correos Cognito.
- La propuesta IAM no se aplicó: la simulación del laboratorio devolvió un
  recurso genérico `${BucketName}/${KeyName}` en lugar de los recursos
  solicitados, por lo que no demuestra permisos mínimos.
- Respaldo del Scheduler y planes JSON guardados en el directorio temporal
  aprobado como `scheduler-respaldo-1b6051ba04e74a798152b3b0d9b51d78*.json`.
  Ningún plan aplicado; estado final `DISABLED`, destino anterior.

Pendientes para cerrar todos los puntos: ciclo real de registro/recuperación
Cognito y publicación de frontend; procedencia verificable del panel ajustado;
observaciones Yahoo reales autorizadas; calendario oficial 2027; ensayo de
permisos con rol dedicado. El endpoint global legado conserva su límite:
los consumidores de historial completo deben migrar explícitamente a
paginación antes de superar 2.000 capturas.
