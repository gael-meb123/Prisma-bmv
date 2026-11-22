# Avance: fuentes, IPC y aplicación

## Fuentes y composición

La URL oficial del boletín BMV del 19-11-2026 continuó respondiendo HTTP 404.
La página de S&P para el índice devolvió HTTP 403 en este entorno. El buscador
disponible falló con HTTP 402, por lo que esta revisión no equivale a una
búsqueda exhaustiva. No se obtuvo composición oficial fechada ni evidencia
que confirme los alias. No se promovieron candidatas, datos ni modelos.

La diferencia de hash del 17 sigue sin explicación verificable; no se alteraron
Silver ni Gold. Que los precios coincidan no identifica el documento usado al
generar Gold. La ausencia de versionado en el bucket limita la reconstrucción.

Una comprobación adicional el 19-11 (después de las 21:30 CDMX) descargó dos
veces el boletín oficial del 17: los hashes de los bytes difirieron entre sí y
del HTML conservado en Bronze. El parser encontró las mismas 29 tablas y la
misma fecha en los tres; la comparación por líneas encontró diferencias en un
script `f5_cspm` añadido después de `</html>`. Esto demuestra que distintas
respuestas del servidor pueden tener tablas idénticas y hashes diferentes;
es una explicación **plausible**, no una identificación demostrada del HTML
que generó el hash de Gold, que sigue sin encontrarse. No se eliminaron scripts
ni se sustituyeron hashes como prueba de autenticidad.

## Panel histórico

El detalle reproducible de `scripts/auditar_panel_estadistico.py` identifica
las 13 filas con ventanas incompletas como AMX B entre 2023-03-28 y 2023-04-17.
El histórico registra AMX L hasta 2023-03-15 y AMX B desde 2023-03-16 en el
entorno de esa fecha. La coincidencia temporal **no acredita** continuidad,
ajustes corporativos ni validez de cálculos entre ambas series. No se
reclasificaron ni corrigieron datos.

## Sectores

La ruta `GET /api/terminal/sectores` agrega la instantánea reciente usada por
mercado. Distingue total, precio verificado, ausencia de precio y número de
variaciones disponibles; no incluye contingencias en medias ni convierte
faltantes a cero. La respuesta conserva información de fuente y cobertura.
El frontend local solicita la ruta en las secciones correspondientes. Esto no
completa el panel estadístico, las señales, el alta o las demás rutas.
La ruta quedó desplegada en la API aislada. En pruebas reales, el 17 devolvió
12 precios verificados y ninguna variación disponible en la instantánea; el
19 devolvió cero precios verificados y ninguna variación. En ambos casos no se
inventó una media. La respuesta GET permitió el origen Amplify configurado.
La modificación de React está solo en local y el build compiló.
