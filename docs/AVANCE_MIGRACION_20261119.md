# Avance de migración: 19 de noviembre de 2026

## Seguridad y Cognito

- El pool Cognito tiene TOTP habilitado y MFA opcional. Se agregó al React
  local una pantalla para asociar un autenticador y confirmar el código antes
  de establecerlo como factor preferido, además del desafío `MFA_SETUP` en el
  acceso. La clave de alta se conserva en memoria y no se imprime.
- Una prueba real con el usuario sintético inició sesión, asoció y verificó
  TOTP, cerró sesión, inició con MFA y renovó el token. La preferencia MFA del
  usuario de prueba se restableció a deshabilitada y se comprobó el estado. Se
  renovó su contraseña aleatoria, sin guardarla.
- Recuperación de contraseña por correo, primer acceso y flujo visual aún no
  se han probado de extremo a extremo. La cuenta sintética usa un correo no
  entregable. El código de React no está publicado en Amplify.

## Concurrencia de la API

CloudWatch muestra un throttle de Lambda en el intervalo de la prueba anterior
y duración máxima de aproximadamente 8,1 segundos, pero no hay información
suficiente para atribuir el 503 observado a una causa concreta. Se desplegó un
cambio en la API aislada: 256 MB, timeout de 15 segundos y concurrencia
reservada de 4, frente a 128 MB, 10 segundos y 2 anteriores. Se reutilizan los
clientes AWS en ejecuciones calientes y se registran únicamente clases de
errores, sin cuerpos de solicitudes, tokens ni excepciones detalladas.

Una prueba con cuatro peticiones simultáneas de un usuario Explorer obtuvo
`200, 403, 200, 403`, entre 4,2 y 4,6 segundos. Es una muestra pequeña, no una
prueba de carga o un compromiso de disponibilidad. API Gateway mantiene su
límite de 2 solicitudes por segundo y ráfaga 5. El aumento de recursos puede
incrementar costos.

## Estadística parcial

Se desplegó `GET /api/terminal/estadistica` con autorizador Cognito y control
de emisora por plan. Usa la instantánea S3 reciente; calcula medidas,
frecuencias e histograma solo para registros con estado verificado y PPP
positivo. La respuesta advierte que no es el historial completo y devuelve
`cobertura_panel: null`, con panel ajustado y correlaciones no disponibles.
No equivale al contrato completo del FastAPI anterior. El React local muestra
esa ausencia sin sustituirla por ceros.

Con access token real de Explorer, WALMEX respondió `200` con 54 filas
registradas y panel ausente; AMX respondió `403`. Sin token, la ruta respondió
`401`. La serie devolvió 54 puntos hasta el 19-11-2026; ese último punto de
contingencia no se convierte en PPP verificado. ZIP de Lambda:
`artifacts/api-gateway/5073a2305a87012c5482070f59fd47be21c1d20c578d785da731b9d456be2349.zip`.

## Procedencia de señales

Se descargaron para lectura local las instantáneas S3 de Gold y Silver con
SHA-256 respectivamente
`cf3ca9c54aa9956a26e0fdde89a45f46642e2ad373be28a1be59542457155f45` y
`52272cfc05b7fb7a324b8a1ce3a4e92b3fbbcd652be0902f2ca72fca07b49795`.
`scripts/auditar_procedencia_senales.py` cruza cada señal con Silver por
fecha y emisora, informa ambigüedades y compara serie y hash sin modificar
ninguna fuente. Son 374 filas Gold y 754 Silver en esas instantáneas.

| Fecha de señal | Filas Gold asociadas a estado de contingencia |
|---|---:|
| 2026-11-04 | 24 |
| 2026-11-05 | 30 |
| 2026-11-19 | 30 |

Para el 19, las 30 filas tienen el mismo hash que Silver; la URL registrada
identifica una contingencia Yahoo con BMV 404. Silver carece de la serie en ese
corte, por lo que el cruce por emisora no verifica la clave exacta. En las
instantáneas analizadas ninguna de las 374 comparaciones acreditó coincidencia
de serie: es una diferencia o ausencia que requiere revisión, no prueba de que
todas sean erróneas. La coincidencia del hash tampoco demuestra la procedencia
de toda la ventana de características, entrenamiento, evaluación o resultado.
No se han reescrito Gold, Silver ni las señales históricas.

La URL del boletín del 19 continuaba devolviendo 404 al comprobarla. La ficha
oficial de S&P del índice respondió 403 y el buscador disponible devolvió 402;
no se ha obtenido una composición oficial fechada ni confirmado los alias.
Las 20 candidatas siguen provisionales, sin modelos adicionales.

## React y funciones pendientes

Se eliminaron algunos valores fijos visibles (incluido el PPP de ejemplo de
la portada), se etiquetó una ilustración como tal y se dejaron vacíos los
metadatos de señal ausentes. Esto **no completa la auditoría**: existen mocks,
gráficas y afirmaciones pendientes. La vista de Amplify continúa siendo la
vista preliminar de mercado; no se sustituyó por el React completo.
El React compiló localmente con Cognito, `VITE_REQUIRE_REAL_API=true` y la URL
HTTPS de la API aislada; la compilación no es una prueba de funcionamiento ni
demuestra que todos los mocks estén excluidos de la interfaz.

Pasaron 24 pruebas Python seleccionadas y 16 pruebas JavaScript seleccionadas;
no constituyen la suite completa ni una prueba integral de navegador.

Siguen pendientes la migración segura de señales, seguimiento, administración
y otros contratos, la conciliación oficial de boletines y Gold, la validación
de la composición IPC y una prueba integral en navegador. No deben habilitarse
señales cuya procedencia o ventanas no estén validadas.
