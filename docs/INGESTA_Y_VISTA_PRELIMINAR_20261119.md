# Ingesta y vista preliminar: 19 de noviembre de 2026

## Ejecución diaria

El Scheduler `DisparadorDiarioBMV` está habilitado para las 16:45 de lunes a
viernes en `America/Mexico_City`. CloudWatch registra una ejecución de
`recolector-diario-bmv` el 19-11-2026 a las 16:45 (22:45 UTC). Procesó las
fechas 4, 5 y 19 de noviembre. Para las tres, la URL del boletín BMV respondió
404 y el recolector registró `CONTINGENCIA_FUENTE_SECUNDARIA`. La URL del día
19 seguía devolviendo 404 cuando se comprobó después de la ejecución.

El recolector informó 14 emisoras de contingencia para el día 19. La
instantánea `silver/serie_unificada_reciente.csv` se modificó a las 22:45:34
UTC. La API devuelve 14 filas en ese corte, cero PPP marcados como verificados,
y precios y variaciones `null`. Son 14 filas registradas, no una prueba de
cobertura completa. No se reejecutó la Lambda: la ejecución también recalculó
inferencias G2 y modificó Gold. Esas inferencias requieren revisión de
procedencia antes de exponerse; no se deduce de los logs que sean válidas ni
que todas usaran exclusivamente datos oficiales.

La captura ampliada aislada utiliza un catálogo provisional con un solo corte
admitido: 17-11-2026. No se extrapoló al 19 ni se activaron modelos para las
candidatas.

## Publicación limitada en Amplify

La rama manual `demo` de la app `d315dh37vi024o` sirve
`https://demo.d315dh37vi024o.amplifyapp.com/`. El trabajo 3 terminó `SUCCEED`
y el sitio devolvió HTTP 200. El origen está permitido por el CORS de la API;
se comprobó el encabezado de respuesta para el resumen de mercado. La vista
publicada contiene exclusivamente `frontend/vista-preliminar/{index.html,
vista.css,vista.js}`. El ZIP no incluye variables de entorno, credenciales,
usuarios, pruebas ni el frontend React completo.

Esta **no es la aplicación React completa**: es una vista pública en
construcción, sin inicio de sesión ni acceso a señales, estadística o
administración. Consulta fechas y resumen en vivo, muestra la fecha y la última
modificación del objeto, identifica la cobertura como parcial y no representa
contingencias como PPP. Si la API falla muestra un error, no mocks. Pasaron dos
pruebas Node de fallo y contingencia y diez pruebas Python de la API. No se
completó una prueba visual ni interacción real en navegador; HTTP 200 y CORS no
la sustituyen.

El job 2, correspondiente a un intento manual fallido de cargar el ZIP, fue
cancelado. Ningún dato de mercado ni función de ingesta se modificó para
publicar la vista.

## Pendientes para la aplicación completa

- Implementar y probar en la API los contratos de estadística, señales,
  seguimiento, administración y demás rutas usadas por React, con permisos de
  Cognito/DynamoDB y errores explícitos.
- Terminar el alta TOTP y probar en navegador recuperación, MFA, primer cambio
  de contraseña, renovación de sesión y autorización. No se migraron usuarios
  ni contraseñas de Supabase.
- Auditar todos los valores fijos, ejemplos y afirmaciones del React existente;
  ejecutar pruebas integrales sin mocks ni credenciales en el bundle antes de
  sustituir la vista preliminar.
- Resolver límites y estabilidad: hubo un 503 en la prueba concurrente anterior,
  y CloudWatch registró un `Throttle` de Lambda durante el intervalo de prueba.
  La función está limitada a dos ejecuciones concurrentes; el dato no demuestra
  por sí solo que ese throttle causara aquel 503.
- Investigar la ausencia de los boletines y conciliar con una fuente oficial
  autorizada. Verificar el impacto de la contingencia en Silver y Gold y las
  señales ya emitidas, sin reescribir el historial sin una política aprobada.
- Validar composición IPC, alias, cobertura e historial antes de incorporar las
  candidatas o habilitar nuevos modelos. Falta validar Redistribución si procede.
- Asegurar permisos mínimos, monitoreo, control de costos, reversión y
  publicación atómica de la captura ampliada.
