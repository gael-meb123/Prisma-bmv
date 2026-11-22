# Prueba de página pública de Capitales BMV: 19-11-2026

## Resultado

Consulta manual de la fuente pública alrededor de las **09:58 UTC−6**.
La página [Capitales BMV](https://www.bmv.com.mx/es/mercados/capitales)
mostraba fecha **19/11/2026** e indica información con 20 minutos de
retraso. El endpoint de datos utilizado por esa página respondió HTTP 200;
el campo `datosEstadistica.fecha` era `null` en las 96 acciones, por lo que
la fecha proviene de la página y no está confirmada individualmente en el
payload. Las horas de operación visibles para las 35 claves eran 09:37–09:38.
Se trata de una muestra intradía, no de cierre.

| Prueba | Resultado |
|---|---:|
| Filas en el grupo `A` del endpoint | 96 |
| Pares exactos encontrados de las 35 referencias del 17-11 | 35 |
| PPP con valor `0` en las 96 filas | 96 |
| PPP positivo en esas filas | 0 |
| Fecha individual `null` en esas filas | 96 |

Los 35 pares incluyen `R / A` y `LIVEPOL / C-1`: se observan literalmente
en BMV hoy. Esto respalda que los pares existen en esta respuesta, pero por
sí solo no demuestra la equivalencia de esos pares con los alias NAFTRAC
`RA` y `LIVEPOLC.1`, ni su composición IPC en ninguna fecha.

No se considera `0` un PPP válido ni se reemplaza por el último precio,
importe/volumen, NAFTRAC o Yahoo. Existen otros campos de operación, pero no
se ha establecido por qué el PPP es cero ni si se completa más tarde.
No se ha demostrado que este endpoint permita consultar fechas históricas.

Se solicitó también el boletín público
`https://www.bmv.com.mx/docs-pub/rss/boletin20261119.html`: HTTP 404 en ese
momento. Esto **no** prueba que no vaya a publicarse después ni permite
cotejar PPP de esta sesión. No se compararon valores intradía de hoy con el
boletín del 17, porque corresponden a fechas distintas.

## Método y límites

Se usó una consulta GET a
`https://www.bmv.com.mx/es/Grupo_BMV/BmvJsonGeneric?idSitioPagina=4`,
referenciada por los scripts de la página de Capitales. La respuesta tiene
un prefijo `for(;;);` y un comentario al final, por lo que se decodificó
el objeto interno sin ejecutar el JavaScript. Se compararon `cveCorta` y
`cveSerie` con las parejas exactas de
`prisma/domain/catalogos/naftrac_2026-11-17_v1.json`; no se extrapoló la
composición de ese catálogo a la sesión actual. La respuesta no fue guardada
como dataset ni se realizó una carga en AWS.

La fuente es gratuita en esta consulta, pero eso no acredita derechos
ilimitados: el usuario manifestó contar con permiso. Se requiere comprobar
su alcance escrito para página, captura automatizada, almacenamiento y
visualización. El resultado es puntual y no establece disponibilidad futura,
completitud del mercado ni naturaleza final de los precios.

## Siguiente decisión técnica

1. Repetir una consulta puntual **después del cierre y del retraso indicado**;
   registrar hora, fecha visible, conteo y valores positivos. No asumir que
   el cambio de hora resolverá el campo cero.
2. Si el boletín de la misma fecha está disponible, comparar por par y mismo
   corte los PPP positivos, sin convertir ceros en precios. Documentar
   discrepancias y tiempos. La comparación entre dos productos de BMV no es
   independiente.
3. Si el PPP sigue en cero, consultar a BMV si el campo público se publica
   al cierre o existe otra fuente gratuita autorizada; evitar calcularlo a
   partir de importe/volumen sin definición y validación oficial.
4. En paralelo se puede avanzar con el diseño de un adaptador de captura y
   pruebas **con datos sintéticos**, conservando fecha y hora de observación,
   origen, último precio y PPP como campos distintos, con cero/no disponible
   como estado explícito. Sin incorporarlo a Silver productivo, predicciones
   o consenso hasta validar datos y permisos.
5. Para sesiones históricas y pertenencia IPC siguen siendo necesarios datos
   históricos adecuados y catálogos respaldados para cada corte; esta consulta
   no cubre ninguno de los dos requisitos.
