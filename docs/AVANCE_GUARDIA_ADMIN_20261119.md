# Guardia aislada y alta por invitación

## Guardia de señales

Se desplegó una Lambda **aislada**, sin Scheduler y sin conexión con el
recolector productivo, desde `infra/lambda/guardia_senales/`. Genera internamente
las 21 sesiones del calendario local de 2026 y aplica la regla conservadora de
estado, precio, serie, huella y URL por fecha. Rechaza años no contemplados y
emisoras que no pertenecen al panel de prueba. Su salida declara siempre
`emision: NO_HABILITADA`; no calcula predicciones ni escribe Gold o Silver.

Una invocación AWS con datos totalmente sintéticos permitió la elegibilidad de
dos ventanas con metadatos oficiales simulados; una segunda bloqueó la ventana
que incluía contingencia y la métrica relativa de la otra emisora. Ambas
declararon emisión deshabilitada. La Lambda comprueba **metadatos suministrados**:
no autentica el boletín, no valida ajustes o modelos, y utiliza `LabRole`
conforme a las restricciones del laboratorio, no mínimo privilegio.
También se invocó con 70 filas reales copiadas de los Silver diarios disponibles
para el corte 19-11: ninguna de las cinco ventanas pasó y la emisión permaneció
deshabilitada. Los resultados no demuestran que los días sin archivo local no
tengan boletín en otra fuente.

Esta guardia **no está integrada al recolector activo**. El Scheduler original
continúa `DISABLED`. No se reescribieron señales históricas ni se reanudó la
ingesta. Antes de integrarla hacen falta lectura confiable de fuentes, guardas
contra escrituras concurrentes o sobrescrituras y pruebas de extremo a extremo.

La guardia aislada se amplió con un modo de solo lectura de S3:
`{"fecha":"2026-11-19","modo":"auditoria_s3"}`. Este modo no acepta un bucket
elegido en el evento, carga los Silver diarios y los HTML Bronze de la ventana
y comprueba fecha, par, PPP y hash. Solo `NoSuchKey` se interpreta como
ausencia; los errores de acceso fallan cerrados. Datos oficiales sin evidencia
Bronze coincidente se bloquean. No escribe datos ni llama a modelos.
Una invocación real en AWS reportó 7 Silver diarios ausentes, 55 filas con
PPP y hash coincidentes con Bronze, cero ventanas aptas y
`emision: NO_HABILITADA`. Esto no certifica autenticidad independiente,
licencia, ajustes ni modelos. El artefacto desplegado es
`artifacts/guardia-senales/0c3db5c7a19a388252c115183f5cb8d54aa28de58d5641bf3853f8090cac6ddb.zip`.

`scripts/auditar_boletin_diario.py` contrasta por fecha, emisora y serie los
precios de Silver con tablas del HTML Bronze conservado, además de verificar
que URL y hash declarados coincidan. Para el 17-11-2026, 12 filas marcadas
verificadas coinciden en PPP y hash; tres filas con otros estados no se
evaluaron. Esto no identifica el HTML que produjo el hash diferente de Gold,
ni acredita autenticidad independiente, derechos, ventanas o modelos.

## Alta administrativa experimental

La API tiene `POST /api/admin/usuarios` protegida por JWT de acceso y rol
administrador. El flujo crea en Cognito con invitación suprimida, registra el
perfil y comprueba el rol del actor en una transacción de DynamoDB, y solo
después pide a Cognito que envíe la invitación. No recibe contraseñas del
administrador. Si el resultado de una etapa es incierto, no elimina una cuenta
ni reintenta automáticamente: informa que se revise el estado. Una respuesta
de aceptación de Cognito no prueba entrega ni verificación del correo.

Las pruebas locales cubren autorización, validación, orden de operaciones y
fallos simulados de perfil e invitación. Las pruebas reales con el usuario
sintético comprobaron `403` para un usuario normal, `422` para cuerpo inválido
y `409` para una cuenta existente, sin enviar invitaciones. El perfil sintético
se restauró a `user/explorer`. La creación exitosa de una cuenta nueva mediante
esta ruta, la entrega y los fallos reales no se han probado extremo a extremo;
la función debe tratarse como experimental. El correo de prueba existente
sigue sin verificarse hasta que la persona complete la verificación.

Una prueba de navegador anterior no mostró el rechazo de una cuenta duplicada
de forma estable. Se estabilizó la identidad de sesión y se impidió anunciar
una respuesta vacía como alta completada. La repetición con Chrome y CORS
normal mostró el formulario sin contraseña y el rechazo `409` de la cuenta
sintética existente; el perfil se restauró a `user/explorer`. No sustituye la
prueba de creación y entrega real de una cuenta nueva.

No se ha confirmado una lista IPC oficial fechada ni se activaron las
candidatas. Yahoo sigue sin conectarse a la ingesta o mostrarse en el sitio;
su intérprete local no valida los derechos de redistribución. El panel
estadístico ajustado tampoco se ha publicado.
