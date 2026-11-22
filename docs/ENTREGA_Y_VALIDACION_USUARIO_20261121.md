# Entrega y validación pendiente — 21-11-2026

## Resultado

Sitio actualizado: https://react-demo.d315dh37vi024o.amplifyapp.com/

Se completó la implementación y publicación de cuentas, consumidores paginados,
procedencia estadística y calendario compartido. Quedan validaciones humanas
de correo y bloqueos de fuentes/permisos. No se declara el proyecto listo para
emitir señales ni para recolectar automáticamente.

### Implementado y comprobado

- Registro público Cognito habilitado en el pool existente, con trigger probado
  primero en un pool separado. Perfil inicial `user/explorer`, escritura
  condicional y conservación de perfiles existentes.
- Prueba real con identidad sintética: SignUp, rechazo de código incorrecto,
  confirmación administrativa exclusivamente sintética, trigger, acceso SRP,
  `/api/me` 200 y rechazo de código incorrecto de recuperación.
  Esto **no acredita entrega de correos ni confirmación humana**.
- El primer ensayo detectó timeout del trigger a 128 MB. Se corrigió a 512 MB
  y tiempos SDK acotados; pasó en ambos pools. El pool de pruebas volvió a
  registro deshabilitado al terminar y las cuentas sintéticas nuevas fueron
  retiradas junto con sus perfiles.
- Cognito aceptó **un reenvío de invitación** a `djlexus134@gmail.com`;
  el estado observado antes de reenviar era `FORCE_CHANGE_PASSWORD`.
  No se marcó el correo humano como verificado.
- Frontend publicado en `react-demo`, trabajo **9, SUCCEED**. Chrome headless
  con seguridad web habilitada verificó login, mercado diario, estadística,
  verificación de correo y bloqueo de señales/ficha. Registro y recuperación
  visibles en otra prueba, sin enviar correos y sin errores JavaScript.
- El JavaScript inicial pasó de aproximadamente 5.34 MB a **632 kB** sin
  comprimir (183 kB gzip); Plotly/terminal se cargan al abrir esa sección.
  Es tamaño de artefactos, no una medición de velocidad en todos los equipos.
- Fechas y series del frontend consumen `paginado=true` hasta `siguiente=null`.
  Detectan cambios de instantánea, cursores repetidos y discrepancias.
  Un fallo posterior no devuelve un historial parcial. Se preservan 54 fechas.
- La API ofrece páginas globales de hasta 31 capturas y conserva el contrato
  legado. Cada página lee snapshot + una LIST + dos GET por captura. Las rutas
  legadas sin paginación aún tienen el límite anterior, pero el frontend
  Cognito ya no depende de ese recorrido para fechas/series.
- Estadística consulta solo meses del intervalo, valida todos los cortes
  pertinentes y muestra el intervalo efectivo. Pide acotar el rango cuando
  excede 366 días; no recorta silenciosamente una solicitud.
- Medición HTTP aislada: primera página válida 4.819 s (incluye arranque);
  siguientes consultas 0.404–0.499 s. En API experimental: fechas paginadas
  0.697 s y resumen por fecha 0.594 s. Son muestras individuales.
- Calendario de captura, núcleo y guardia centralizado en
  `prisma/domain/calendario_bmv.py`. Una variable de entorno ya no habilita
  años sin validar. Pruebas de cruce de año con calendario sintético y rechazo
  de 2027 real aprobadas.
- Recolector seguro y guardia aislada actualizados. Integración AWS
  `61442c668db34080bd4c9016ea6a2980`: historial confirmado, paginación,
  concurrencia, recuperación parcial, conflictos y preservación del legado.
- Scheduler ensayado en recurso aislado: habilitar, pausar y restaurar destino.
  El ensayo estaba fechado en 2099 y no invocó ninguna captura. Se retiró
  exclusivamente ese Scheduler de prueba.
- Scheduler real **preparado y DISABLED**, ya apunta a la Lambda segura y fija
  la fecha original mediante `<aws.scheduler.scheduled-time>`. Mantiene
  16:45 CDMX de lunes a viernes. Respaldo archivado y releído en S3:
  `operacion/scheduler/respaldo-3bfc166ba5084b8681184d041f98ab6e-6bf52e6891811bf67977293fea7fd0d6201bf49c41e569adcb515243abc0e314.json`
  en el bucket de pruebas.
- Última comprobación: tres alarmas `OK`, cero mensajes visibles/no visibles
  en la cola. No se purgó ni retiró ningún mensaje operativo en esta entrega.
- 100 pruebas pytest + 5 subtests, 15 pruebas Node, build y pruebas AWS/browser
  aprobados. Lint sin errores; conserva un aviso previo de estado en efecto
  en Estadística. `git diff --check` sin errores de espacios.
- Último gasto observado: **USD 2.232**, presupuesto USD 1.00; puede actualizarse.

## Lo que debes hacer tú

### 1. Completar tu primer acceso

1. Revisa `djlexus134@gmail.com`, incluyendo spam, y usa **la invitación más
   reciente** de Cognito. El reenvío puede invalidar la contraseña temporal anterior.
2. Abre https://react-demo.d315dh37vi024o.amplifyapp.com/#/acceso .
3. Introduce el correo y la contraseña temporal recibida allí.
4. Cuando se solicite, elige tu propia contraseña: mínimo 12 caracteres con
   mayúscula, minúscula, número y símbolo.
5. Comprueba que puedes abrir Mercado y Estadística de WALMEX.

Resultado esperado: sesión iniciada y perfil Explorer. Si no recibes el
correo, informa solo “no llegó la invitación”; si falla, informa el texto
del error y el paso. No compartas contraseña temporal, definitiva ni tokens.

### 2. Verificar correo y recuperación

1. Con sesión iniciada, abre
   https://react-demo.d315dh37vi024o.amplifyapp.com/#/seguridad .
2. Pulsa **Enviar código al correo** y escribe el código recibido en esa página.
3. Debe aparecer **Correo verificado. Ya puedes usarlo para recuperar el acceso.**
4. Cierra sesión. En Acceso, pulsa **¿Olvidaste tu contraseña?**.
5. Solicita el código, completa el cambio en la aplicación e inicia sesión
   con la nueva contraseña.

Confirma únicamente si los tres pasos funcionaron: primer acceso,
verificación y recuperación. Los códigos se introducen solo en la aplicación.
La recuperación por correo no elimina un autenticador MFA configurado.

### 3. Probar registro nuevo (opcional para tu cuenta existente)

Tu correo ya tiene cuenta: no lo registres de nuevo. Para acreditar el ciclo
de registro público con correo real puedes usar otro correo que controles
(por ejemplo un alias propio) en `#/registro`, confirmar el código e iniciar
sesión. Debe recibir Explorer, nunca permisos administrativos.
No hace falta hacerlo para utilizar tu cuenta invitada.

### 4. Facilitar evidencia de datos

Puedes guardar los documentos en una carpeta local y señalar su ruta:

- **BMV:** conserva el correo de autorización y el alcance permitido; consigue
  el boletín oficial validable del 20-11 o el canal autorizado que BMV indique.
  La consulta actual del RSS sigue devolviendo mantenimiento.
- **Ventana actual:** faltan diarios del 20, 21, 22, 23, 26 y 27 de octubre y
  18 de noviembre de 2026; el 4, 5 y 19 de noviembre contienen fuentes no
  oficiales para las cinco emisoras auditadas. Si dispones de sus boletines
  oficiales, proporciona los originales. Se conciliarán sin sobrescribir.
- **Calendario 2027:** publicación oficial BMV (PDF/HTML o enlace accesible).
  No sustituirla por una lista calculada de feriados.
- **Panel/IPC:** documentos de eventos corporativos y factores de ajuste,
  composición IPC con fechas de vigencia y evidencia de los alias
  `RA → R / A` y `LIVEPOLC.1 → LIVEPOL / C-1`.
- **Yahoo:** si se quiere publicar sus observaciones, aportar el alcance de
  uso/redistribución aplicable a la fuente elegida. Ya se obtuvo una respuesta
  real de WALMEX y se archivó con URL/hash en pruebas; no se mezcló con PPP.

No basta con indicar que los datos “parecen correctos”: necesitamos conservar
la evidencia y comprobarla. Con esos archivos se puede ejecutar la validación
técnica restante, sin que tú tengas que modificar el código.

### 5. Permisos del laboratorio

Solicita al administrador/docente un rol dedicado o permiso para crearlo y
pasarlo a Lambda. AWS denegó `iam:CreateRole` para
`PrismaBMVRecolectorSeguroDedicado2026`.
La confianza y propuesta de política están en:

- `infra/iam/confianza_recolector_seguro.json`
- `infra/iam/recolector_seguro_minimo.json`

Necesitamos probar el rol real con S3, logs y SQS antes de adoptarlo.
Mientras tanto sigue el `LabRole` ya autorizado. No hace falta enviar claves
AWS por chat ni modificar ese rol compartido.

## Evidencia y bloqueos concretos

- `auditoria_pendientes_20261121.json`: 9.879 filas del panel enlazan con el
  histórico y PPP base; 13 ventanas incompletas. No se detectaron diferencias
  en las fórmulas comparables. Esto no valida los documentos corporativos,
  la autenticidad histórica ni el entrenamiento.
- `evidencia_guardia_20261121.json`: ventana 20-10 a 19-11, 7 diarios ausentes,
  55 coincidencias PPP/hash y **ninguna de las cinco emisoras apta**.
  Las fechas de fuentes no oficiales requieren conciliación, no imputación.
- Calendario oficial: la página BMV continúa mostrando “Sitio Grupo BMV no
  disponible”. 2027 permanece bloqueado.
- Yahoo: SHA-256
  `58d0a85721d53151a1ae4217535c0c10105fa8915c563d951846450de8d4c15f`,
  archivado bajo `pruebas/yahoo/<sha>/` del bucket aislado con procedencia.
  Backend y frontend de observaciones públicas siguen deshabilitados.

No se efectuó la primera captura productiva nueva ni se activó el Scheduler.
Aunque se complete el acceso humano, las señales seguirán bloqueadas hasta
validar fuentes, ventanas, ajustes y modelos.

## Artefactos y reversión

| Componente | SHA-256 desplegado |
|---|---|
| API experimental y de pruebas | `34f8040548bfa2557b3216f3bffa9b9a2a229bc3c91d63a61ba095b38cecdc71` |
| Recolector seguro y de pruebas | `8540eeecf199536f2a733136a067efd1079b6d5cd9f38af31e72af414ce8243b` |
| Guardia aislada | `469b1be94a8a732f19075779d915945bd57cf410c1f0b95a44f6bcc6285bcf7c` |
| Trigger Cognito | `617ed60f2025cb071292d5c28d5242c0012488d58805c989b085df001eea4331` |
| ZIP frontend trabajo 9 | `b8ea2284e0d77b82f95aa8562d65a188ef080b7667fd872b9391737acadb6665` |

`scripts/desplegar_artefacto_existente.py` conserva plantillas/parámetros y
registra el ArtifactKey anterior antes de ejecutar. Los registros están en
el directorio temporal aprobado bajo `despliegue-*.json`. API previa:
`artifacts/api-gateway/506d277e4cb7befe22b4ebcb82a27d4a2b6bcccaaa71439a373f2adabc391cf6.zip`.
Recolector previo:
`artifacts/recolector-seguro/6df2dc986521b7f2bbc9adcfee99e64da093feea117704be98b646a0143c2d21.zip`.

El ZIP del frontend anterior (trabajo 8) se descargó antes de publicar:
`react-demo-job8-respaldo-0.zip`, SHA-256
`32b7e8825bcac6fc25246dc9b64550a555bc386a2aa66349bdd4675b6a097b7f`.
Para revertir cuentas, deshabilitar `RegistroPublico` mediante la plantilla y
publicar el frontend anterior; no borrar usuarios/perfiles.
Toda reversión del Scheduler debe conservar `DISABLED`.

Cambios en la rama experimental, sin commit/push. Se conservaron Supabase,
la vista preliminar anterior, los históricos y el proyecto original.
