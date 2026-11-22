# Variante segura de captura: aún no desplegar ni reactivar

> Actualización del 21-11: ver
> [DESARROLLO_HISTORIAL_SEGURO_20261121.md](DESARROLLO_HISTORIAL_SEGURO_20261121.md)
> para la integración de historial confirmado, paginación y pruebas posteriores.
> Las secciones siguientes conservan la cronología de revisiones anteriores.

`infra/lambda/recolector_seguro/handler.py` es una variante nueva; **no es la
Lambda actualmente desplegada** y no se ha conectado al Scheduler. No llama
al código de inferencia o seguimiento de la Lambda activa. La guardia se
ejecuta obligatoriamente después de capturar Silver y Bronze; tanto con
ventanas aptas como no aptas la variante mantiene deshabilitadas las señales.
No modifica Gold ni la instantánea Silver compartida.

## Protección implementada

- Descarga únicamente el boletín BMV, sin contingencia Yahoo. Exige fecha
  inequívoca, encabezado reconocido, pares exactos y precios válidos; las
  filas contradictorias bloquean el corte.
- Valida precios y hash contra el HTML antes de escribir; las ausencias se
  describen como no encontradas en las tablas, no como inexistencia en BMV.
- Publica HTML y CSV diarios con `If-None-Match: *` y compara bytes en
  duplicados. Los contenidos distintos nunca sustituyen los existentes; un
  HTML divergente se guarda en cuarentena con SHA-256 completo.
- Fallos o resultados inválidos de guardia propagan error. Una interrupción
  después de Bronze o Silver puede dejar una captura parcial; el reintento
  idéntico la completa. No existe transacción entre objetos S3.
- Las pruebas locales simulan concurrencia, conflicto de Bronze/Silver,
  errores, reinicio y ejecución real de la guardia sobre S3 falso.

## Prueba aislada real en AWS

El 19-11 se desplegó una función **solo de pruebas**, sin Scheduler, con
Python 3.11 y la misma layer `AWSSDKPandas-Python311:35` del recolector activo.
Usa `LabRole`, que tiene permisos amplios; la separación de escrituras se
implementa en el adaptador de prueba, no en una política IAM mínima.
Todas sus llamadas de escritura se redirigen al bucket experimental bajo
`pruebas/recolector-seguro/c6aa72b3f4fd411eaeda2a4d8fa21da2/`.
La prueba lee, sin modificar, el HTML productivo conservado del 17-11.

Pasaron cinco llamadas concurrentes, duplicados idénticos, cuarentena de HTML
divergente, recuperación tras error simulado entre Bronze y Silver y rechazo de
un 404 simulado. Las operaciones condicionales se ejecutaron efectivamente
contra S3. También se procesó la copia del Bronze real: la guardia reportó
cinco coincidencias de PPP y hash para sus cinco emisoras, con emisión
deshabilitada. Reportó 20 Silver ausentes porque el entorno de prueba estaba
vacío: **no representa una auditoría de ausencia en producción**.
El listado del prefijo de prueba mostró solo Bronze, Silver y cuarentena;
no se escribió Gold. Se ejecutaron 51 pruebas Python locales seleccionadas.
Además, una consulta HTTP de solo lectura al boletín del 19-11 devolvió 404;
no se registró una captura de ese corte ni se utilizó fuente de contingencia.

El ZIP usado tiene SHA-256
`03d0ebc83d40287cccbc029ac8c30c610402d33702a0c38e7714e7fc90d30747`;
el handler de prueba y su plantilla están en este directorio. Se creó una
Lambda de laboratorio sin disparador; no se sustituyó ni invocó la original.
La prueba no acredita derechos de uso, permisos de mínimo privilegio ni
funcionamiento de la API con datos nuevos.

## Pendientes obligatorios

1. La prueba aislada de `IfNoneMatch` pasó para la versión anterior; faltan pruebas operativas de
   fallos reales y recuperación en el despliegue elegido. El bucket productivo
   consultado no reportó versionado habilitado: no se cambió esta configuración.
2. La variante local ahora escribe un manifiesto inmutable solo después de
   completar la guardia. La API local puede descubrirlo con
   `CAPTURAS_SEGURAS_HABILITADAS=true`, verificar su hash y combinar fechas
   nuevas sin sustituir el histórico de la instantánea. La opción está
   desactivada por defecto, no se ha desplegado y la integración nueva no se
   ha probado todavía en AWS. Requiere lectura y listado S3, y actualmente
   recorre un máximo de 2.000 manifiestos por consulta; superar ese límite o
   encontrar un manifiesto corrupto provoca error cerrado, no una lista parcial.
3. Definir observabilidad, alarmas, reintentos y recuperación de conflictos,
   verificar permisos mínimos y restricciones de uso de los boletines.
4. El calendario admitido es solo 2026 y la guardia requiere 21 sesiones
   dentro de su calendario; no se debe extrapolar a 2027.
5. Revisar la configuración y los demás invocadores de la Lambda original:
   pausar el Scheduler no impide invocaciones manuales o externas.
6. La emisión de señales, el seguimiento y el catálogo IPC continúan
   bloqueados hasta validar procedencia, modelos, ajustes y alias. La guardia
   no certifica autenticidad independiente ni derechos de redistribución.

El archivo `scripts/empaquetar_recolector_seguro.py` genera un ZIP
reproducible sin desplegarlo. Requiere layer con NumPy y pandas. Antes de
apuntar el Scheduler a cualquier variante debe revisarse su contrato, ejecutar
pruebas aisladas y establecer cómo se realizará el cambio y su reversión.

## Bloqueo de credenciales del 20-11

Se empaquetó la nueva versión con manifiestos y API; el artefacto aislado
`artifacts/recolector-seguro/b8fbf8e5deaf0a4911e1f53dbbaf8d1e6a86687588a12e60b78b5263f68c903a.zip`
se subió antes del bloqueo. Al intentar actualizar la Lambda de prueba,
CloudFormation devolvió una denegación explícita por política de la
organización. Las comprobaciones posteriores de Lambda, Scheduler, S3 y
Budgets también devolvieron denegación explícita por la política de identidad
`voc-cancel-cred`. No se intentó eludir las políticas.

La última lectura correcta del Scheduler lo encontró `DISABLED` y apuntando a
la Lambda anterior; tras la denegación ya no se pudo verificar su estado. No se
ejecutó un cambio de Scheduler ni se desplegó la nueva API. Hay 53 pruebas
Python locales seleccionadas aprobadas, incluida la integración de
captura/manifiesto/API y rechazo de manipulación de Silver. Esas pruebas no
sustituyen la ejecución AWS de esta versión.

Para continuar se necesita que el propietario reactive el laboratorio o
restablezca autorización mediante el mecanismo normal del entorno. No debe
compartir contraseñas, claves, tokens ni códigos por chat. Con acceso
restablecido: ejecutar la nueva prueba aislada en AWS, verificar
permisos/observabilidad y condiciones de uso, desplegar la API con el flag
controlado, probar captura y consulta de extremo a extremo, y solo entonces
planificar el cambio seguro del destino y la activación del Scheduler.

## Reanudación tras renovar el laboratorio

Se volvió a verificar el acceso: el Scheduler seguía `DISABLED` y apuntaba a
`recolector-diario-bmv`. El gasto observado en Budgets fue USD 1.716 frente al
límite de USD 1.00; el importe puede actualizarse.

La versión `b8fbf8e5deaf0a4911e1f53dbbaf8d1e6a86687588a12e60b78b5263f68c903a`
se desplegó en la Lambda de prueba y pasó en AWS concurrencia, duplicados,
divergencia, recuperación, 404 simulado y descubrimiento de fechas y resumen.
El prefijo aislado fue
`pruebas/recolector-seguro/fb1fb1c28041458cbaa33ddffde758de/`. Se volvió a
procesar una copia del Bronze real del 17-11 sin emitir señales; las 20
ausencias corresponden al entorno de prueba vacío.

Posteriormente se detectó un caso no cubierto: si la fecha ya estaba en la
instantánea, la ruta de resumen podía leer el diario escrito antes de que la
guardia confirmase su manifiesto. La corrección local crea primero un marcador
inmutable de inicio. La API, con el flag habilitado, consulta el marcador
**después** de leer el diario legado y rechaza el resumen si todavía no se
descubrió el manifiesto, incluso ante el inicio concurrente de captura. El
marcador permanece para distinguir capturas de diarios históricos. Se agregaron
pruebas locales de solapamiento, carrera, marcador corrupto y acceso denegado;
pasaron 56 pruebas seleccionadas.

Esta protección solo cubre la API modificada con el flag activado; otros
lectores de Silver y la API desplegada anteriormente no la respetan. Por ello
es obligatorio desplegar y verificar primero la API actualizada, y examinar
otros consumidores, antes de escribir capturas productivas. La corrección
posterior al ZIP `b8fb...` se empaquetó como
`ac5428abb4957da58dd91334a80946e4648f2bacabcf4fb8f740f10b7fdd093f`;
debe probarse por separado en AWS. No se ha activado el Scheduler.

### Condiciones de BMV y consumidores existentes

El [aviso legal de BMV](https://www.bmv.com.mx/es/Grupo_BMV/Aviso_legal)
consultado el 20-11-2026 exige autorización previa por escrito para reproducir
contenido y menciona expresamente el *parsing* como acción prohibida. La
disponibilidad pública del boletín no acredita permiso para extracción
automatizada ni redistribución. Antes de activar esa fuente debe verificarse
una autorización aplicable o elegirse una fuente con licencia adecuada; no se
afirma que esta nota sustituya asesoría jurídica. El aviso facilita como
contacto la Dirección de Información y Estadística de BMV, 55 5342-9000.

Se encontró además la tabla Athena definida en
`infra/athena/02_bmv_silver_ppp.sql`, que consulta directamente el prefijo
diario y no conoce marcadores o manifiestos. Por tanto, la protección agregada
a la API no garantiza publicación atómica para todos los consumidores: hay que
aislar la escritura o adaptar y validar esos lectores antes de activar la
captura productiva.

Para una fecha presente tanto en la instantánea como en una captura con
manifiesto, las series conservan la instantánea mientras que el resumen
prioriza el diario. Se agregó localmente una conciliación que rechaza la
consulta si el estado o el PPP difieren para la misma fecha, emisora y serie;
no reemplaza el histórico. La prueba local cubre coincidencia y discrepancia,
pero todavía se debe probar en AWS la versión que incluye esta conciliación y
revisar otros campos y diferencias de cobertura.

El artefacto que incluye tanto el marcador como la conciliación tiene SHA-256
`60c4f1ee86bd50ffc8124372026b966b23185ce4beea915d0acbce1234daa6c1`.
Se subió al bucket experimental; no se ha conectado al Scheduler ni se ha
desplegado en la API productiva.

La ejecución AWS del ZIP intermedio `ac5428...` devolvió `AssertionError`:
CloudWatch muestra dos invocaciones consecutivas y la segunda encontró que
los objetos de concurrencia ya existían. La primera terminó sin error en
CloudWatch, pero no se recibió su respuesta; el listado del prefijo confirma
que produjo los objetos de los escenarios de prueba. Esto no basta para
declarar aprobada la ejecución. Debe repetirse con un `run_id` nuevo y sin
reintentos automáticos del cliente, conservando los resultados y sin eliminar
la evidencia existente.

Para `60c4...`, la invocación con `run_id`
`6106835e930a4916acc1801fed845f02` agotó el tiempo de espera del cliente.
CloudWatch muestra una sola ejecución que terminó sin error en 7.6 segundos;
el prefijo aislado contiene la evidencia de los escenarios, incluido el
snapshot conflictivo. Como el cliente no recibió el resumen, se agregó un
registro explícito del resultado final a la función de prueba, empaquetado
como `ded58e694a105eaaa80b0cfd451282d193561a0f45f45b0418b89384bbe72a4d`.
La prueba repetida debe comprobar ese registro sin interpretar un timeout del
cliente como éxito o como fallo de la función.

La repetición del artefacto `ded58e...`, con `run_id`
`a0f49ea79875486ba98558a666853a08`, también agotó la espera del cliente, pero
CloudWatch registró explícitamente `PRUEBA_AISLADA_COMPLETADA` y los resultados
`OK` de concurrencia, duplicados, divergencia, API de fechas y resumen,
solapamiento parcial y conflicto, recuperación parcial, 404 simulado y
procesamiento del Bronze real. El log muestra una sola invocación, sin error,
con emisión deshabilitada. El prefijo aislado fue
`pruebas/recolector-seguro/a0f49ea79875486ba98558a666853a08/`. La prueba
ejecutó la API como código dentro de la Lambda aislada, no a través de la API
Gateway desplegada. No valida permisos mínimos, publicación en producción,
otros consumidores ni derechos de uso de BMV.

## Separación de consumidores Silver

El usuario informó que consultó a BMV por correo y recibió respuesta de que
no había inconveniente. No se ha revisado el correo ni su alcance: conservarlo
fuera del repositorio y verificar que cubra captura automatizada,
almacenamiento y la redistribución prevista.

La variante local escribe ahora su CSV en
`silver/recolector_seguro/precios_ppp/`, no en `silver/precios_ppp/`, de modo
que Athena y los consumidores existentes de este último prefijo no ven
capturas nuevas o parciales. La API modificada solo lee el nuevo prefijo por
manifiesto verificado. La guardia recibe exclusivamente el corte actual
aislado mediante un adaptador de lectura y sigue leyendo el resto de su
ventana del prefijo histórico. Por ello puede omitir cortes seguros de días
anteriores y producir falsos negativos; no es una reconciliación histórica ni
autoriza señales. Las pruebas locales incluyen preservación de un Silver
legado existente, ausencia de escrituras en ese prefijo y fallo parcial.

El artefacto de prueba aislada tiene SHA-256
`2a0438350a38ecbef15e0d86d082372ae912550ddea600b7a51e78a5abb1b55c`.
La API empaquetada tiene SHA-256
`7d28ebc5f0e2e27dfd524404a1c47de90b78f669af9735b1ee3691c7ae152fc9`.
Las pruebas AWS y validación de Gateway para esta revisión son independientes
de los resultados de artefactos anteriores.

La Lambda de prueba de la revisión `2a0438...` terminó en AWS con el registro
`PRUEBA_AISLADA_COMPLETADA` para `51ceb7ecdc114b5bbce094103cd113e8`;
incluyó `silver_legado_no_modificado: OK`, recuperación, concurrencia,
conflicto y API llamada como código. El cliente agotó la espera, pero
CloudWatch registró una ejecución completa sin error. Los 20 Silver ausentes
corresponden al entorno aislado, no a producción.

Se creó además el stack de laboratorio
`prisma-bmv-api-capturas-pruebas-2026`, con un bucket versionado aislado y
API Gateway limitado a salud, fechas y resumen. La primera prueba HTTP
devolvió 500 por ausencia de `PERFILES_TABLE` en la Lambda de prueba; se
corrigió la plantilla local y se está actualizando el stack. Se preservan los
objetos sintéticos del intento anterior y no se ha modificado la API existente.

Tras corregir la variable de prueba, la validación HTTP pasó: un corte parcial
no apareció, el manifiesto completo hizo visible la fecha y su resumen, y un
hash incorrecto devolvió 503. El bucket sintético conserva el manifiesto
intencionalmente inválido y no debe utilizarse como fuente real.
Posteriormente se actualizó el stack `prisma-bmv-api-aislada-2026` al artefacto
`7d28...` con `CapturasSegurasHabilitadas=true`. Se comprobó en su Gateway
existente que salud, lista de 54 fechas y resumen devolvieron 200 y los mismos
SHA-256 que antes del cambio; perfil y señales sin sesión devolvieron 401.
No se creó ninguna captura sintética ni manifiesto en el bucket productivo, y
el prefijo nuevo estaba vacío en la comprobación. Con el usuario sintético
existente se verificaron serie y estadística (200), emisora fuera de plan
(403), solicitudes sin token o con ID token (401), y señales y seguimiento
bloqueados (503). No se modificó la contraseña de la cuenta del usuario.
La primera captura productiva y las diferencias de cobertura aún requieren
validación.

### Secuencia de reversión prevista

- No cambiar ni activar `DisparadorDiarioBMV` hasta probar la Lambda nueva y
  confirmar el canal de alertas. Conservar su configuración actual completa
  antes de cualquier modificación.
- Ante un fallo, desactivar el Scheduler y dejarlo desactivado; no volver a
  activar la Lambda anterior, que puede reescribir datos y usar contingencias.
- Si la API experimenta una regresión, volver mediante CloudFormation al ZIP
  `c82f78fbb3ccb57c46350a9b100bc57fd4a8170fa846cbcb810da534813a3d65`
  y deshabilitar el descubrimiento. Eso deja de mostrar capturas nuevas, pero
  no elimina manifiestos ni modifica Bronze, Silver o Gold.
- Investigar los mensajes de la cola de fallos y las alertas antes de reintentar;
  no sobrescribir objetos existentes ni purgar la cola como medida de recuperación.

### Infraestructura de operación preparada, aún sin Scheduler

Se creó `prisma-bmv-recolector-seguro-operacion-2026` con la Lambda segura,
cola SQS cifrada y retenida por 14 días, dos reintentos asíncronos y alarmas
de errores, mensajes en cola y fallos de entrega. Usa `LabRole`: no es una
política de mínimo privilegio. La suscripción SNS a `djlexus134@gmail.com`
estaba en `PendingConfirmation` al revisarla; hasta confirmarla no se puede
afirmar que haya notificación por correo. No compartir el enlace de
confirmación ni credenciales por chat.

Se envió una invocación asíncrona con campo deliberadamente inválido para
probar el manejo de fallo. La validación rechaza ese evento antes de descargar
un boletín o escribir datos; Lambda aceptó la invocación (`202`). La
primera ejecución registró el rechazo previsto y la alarma de errores entró
en estado `ALARM`. En la lectura posterior la cola aún mostraba cero mensajes:
la presencia del mensaje tras los reintentos y la entrega real de alertas
todavía deben comprobarse. El Scheduler seguía `DISABLED` y apuntando a la
Lambda anterior en la última lectura.

### Resultado de la prueba de alertas y cola

La suscripción SNS a `djlexus134@gmail.com` figura confirmada. El fallo
controlado llegó a SQS con `RetriesExhausted`, tres intentos y `ValueError`,
como se esperaba. La alarma de cola pasó a `ALARM` y CloudWatch registró que
ejecutó correctamente la acción SNS.

Se verificó que el mensaje correspondía exactamente al evento de prueba; se
guardó una copia íntegra en el bucket aislado en
`evidencia/fallos-controlados/3fb8ff7cceb94dbd8876c1e8c911c416/acae5f9d0e974dbdb2dfe59a3eccd62511a88aedd6d0868f273d43fa6a0e896c.json`
y se comprobó su contenido antes de retirar **solo ese mensaje** de SQS.
No se purgó la cola. Tras la retirada una lectura no encontró ningún mensaje
disponible, aunque el contador aproximado todavía podía mostrar el valor previo
por consistencia eventual. La alarma puede tardar en regresar a `OK`.

Se publicó una notificación de prueba al tema SNS, con MessageId
`6c2ebba1-16e4-51b0-9814-d8db6a083fbc`. SNS aceptó el mensaje, pero se necesita
confirmación del destinatario para acreditar su recepción en el buzón. El
Scheduler seguía desactivado y apuntando a la función anterior.

## Verificación del 21-11

El usuario confirmó la recepción del correo de prueba y aportó una captura.
La suscripción SNS estaba confirmada, la cola mostraba cero mensajes y las
tres alarmas habían regresado a `OK`. El acceso AWS renovado funcionó; el
Scheduler seguía `DISABLED` apuntando a la Lambda original. El gasto mostrado
por Budgets era USD 2.232 frente a USD 1.00, sujeto a actualización.

Las consultas HTTP de solo lectura de los boletines 19-11 y 20-11 devolvieron
200 desde este equipo, pero el cuerpo era una página titulada «Sitio Grupo
BMV no disponible», no un boletín. El extractor rechazó ambas por fecha no
inequívoca y no se escribió ningún objeto. Un HTTP 200 no debe tratarse como
captura válida. Se preparó un diagnóstico adicional sin escrituras desde la
Lambda aislada para comprobar si la fuente se comporta igual desde AWS.

El diagnóstico desde AWS para el 20-11 también devolvió
`FUENTE_NO_VALIDADA`: el extractor no identificó una fecha inequívoca. No
hubo escrituras ni fuente de contingencia. La respuesta recibida en AWS no se
conservó, por lo que no se afirma que fuera exactamente la misma página de
mantenimiento observada desde el equipo local. El Scheduler no se activó ni
cambió de destino.
