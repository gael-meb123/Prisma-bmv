# Investigación de fuente BMV para PPP por serie

**Fecha de revisión:** 19-11-2026. **Estado:** candidata identificada;
prueba de datos reales y autorización específica pendientes.

## Prueba adicional de la página pública gratuita

El usuario indicó que ya cuenta con permiso y que el objetivo es no pagar.
El 19-11-2026, alrededor de las 08:21 UTC−6, se investigó la carga de
la página pública de Capitales:

- El JavaScript público `capitales.min.js` usa `urlMarketInfoCapital`,
  lee `cveCorta`, `cveSerie` y `datosEstadistica.ppp`, y los presenta
  como emisora, serie y PPP. La configuración pública apunta a
  `https://www.bmv.com.mx/es/Grupo_BMV/BmvJsonGeneric?idSitioPagina=4`.
- Una solicitud GET al endpoint respondió HTTP 200 con `success: true`, pero
  los cuatro grupos `A`, `CKDS`, `F` y `TO` eran listas vacías. El cuerpo
  incluye `for(;;);` y un comentario HTML; no es JSON puro tal como llega.
- Por tanto no se observó ninguna cotización ni se demostró cobertura real.
  La consulta se efectuó temprano; no se comprobó la causa de las listas
  vacías y no debe atribuirse automáticamente al horario.
- El código examinado no muestra un parámetro de fecha histórica para esta
  consulta. No se ha demostrado que permita solicitar el 17-11-2026 o que
  el valor disponible durante la sesión sea el PPP diario final.

El WSDL contiene la descripción del servicio y sus campos, no precios. Esta
página gratuita es una vía distinta al Web Service documentado con
credenciales. El permiso comunicado por el usuario se toma en cuenta; sigue
pendiente revisar su alcance escrito para esta página y los usos específicos.
No se desplegó un recolector ni se guardaron cotizaciones. La siguiente prueba
razonable es repetir una única consulta durante la sesión o después del cierre,
verificar la fecha y comparar solo con una fuente del mismo corte, sin asumir
la composición IPC de ese día.

## Resultado

BMV documenta el servicio de información de emisoras
`obtenQuoteEmisorasMC`. Su respuesta de ejemplo incluye campos separados
`CveEmisora`, `CveSerie`, `PPP` y `Fecha`, por lo que es una candidata
directa para consultar PPP por serie. La especificación indica retraso de
20 minutos, pero no demuestra que el servicio proporcione el PPP final de
cada sesión, consultas históricas ni todas las series buscadas.

La [especificación oficial de Web Services](https://www.bmv.com.mx/work/models/Grupo_BMV/Resource/1995/7/images/webservices_v2_eng.pdf)
(enlazada desde [Soluciones Web BMV](https://www.bmv.com.mx/en/information-products/web-services))
describe, en páginas 10–14:

- Solicitud por emisora y serie opcional, con usuario y contraseña/token.
- Respuesta XML con clave de emisora, serie, PPP, fecha y otros campos.
- Códigos para credenciales incorrectas, IP sin permisos, módulo restringido,
  cuota agotada y emisora no contratada, entre otros.
- Distinción entre serie con operación, sin operación, cancelada y no contratada.

La documentación es un contrato de ejemplo, **no** una respuesta real ni una
garantía de cobertura, vigencia, licencia o disponibilidad histórica.

## Pruebas realizadas

1. La [página pública de Capitales](https://www.bmv.com.mx/es/mercados/capitales)
   respondió HTTP 200. Anuncia «Series Operadas del Mercado de Capitales»,
   columnas `EMISORA`, `SERIE` y `PPP`, y retraso de 20 minutos. La respuesta
   inicial contenía «Cargando información», no filas de precios. No se ha
   establecido acceso autorizado de recolección para esta página ni la
   posibilidad de consultar el 17-11-2026.
2. Se descargó la especificación oficial: HTTP 200, PDF de 32 páginas.
3. Una solicitud GET al [WSDL de producción](https://mkdservices.bmv.com.mx/WSQEMC/WsqemcService?wsdl)
   devolvió HTTP 200, XML de 1.702 bytes y contiene el nombre del método
   documentado. Esta prueba comprueba acceso a metadatos, **no** consulta
   autenticada, disponibilidad de valores ni cobertura.
4. No se enviaron solicitudes SOAP con credenciales inexistentes o inventadas,
   ni se intentó eludir los controles. No se consultaron valores PPP de la
   fuente candidata, por lo que **no se pudo contrastar** ninguno de los
   16 PPP del boletín ni verificar los otros 19.

El [aviso legal de BMV](https://www.bmv.com.mx/es/aviso-legal) exige
autorización previa escrita para reproducir contenido y menciona expresamente
el parsing. El usuario comunicó autorización para recolectar boletines; no se
ha revisado si cubre la página de Capitales, el Web Service, almacenamiento,
automatización o redistribución. No se interpreta acceso público al WSDL como
autorización para recolectar datos. No se implementó un recolector nuevo.

## Alternativa para histórico

La página oficial de [bases de datos de BMV](https://www.bmv.com.mx/en/information-products/databases)
ofrece información histórica y de cierre y enumera «Daily Trades» y
«Closing Prices»; la página de [publicaciones en línea](https://www.bmv.com.mx/en/information-products/online-publications)
enumera precios de cierre mensuales y un boletín de valores. Son candidatos
para solicitar muestras, **no se ha demostrado que contengan PPP por serie**.
Un precio de cierre no se debe etiquetar como PPP sin definición documental.
El Web Service de emisoras y estos productos son ofertas distintas; las
condiciones y derechos de cada una deben confirmarse.

## Solicitud propuesta a BMV

Contacto publicado por BMV: **marketdatasales@grupobmv.com.mx**;
soporte: **marketdata@grupobmv.com.mx**.

Solicitar por escrito, sin asumir compra o suscripción:

1. Una muestra y diccionario de datos de PPP diario final por fecha, emisora
   y serie, incluyendo el 17-11-2026 y las 35 claves del catálogo provisional.
2. Cobertura real de las 19 claves sin PPP en el boletín parcial; confirmar
   específicamente `R / A` y `LIVEPOL / C-1` y sus alias.
3. Definición y cálculo del PPP, horario de consolidación, correcciones,
   moneda, precisión, ajuste por eventos corporativos y reglas de datos
   ausentes o series sin operación.
4. Historial disponible, formato, entrega, cuotas, costo y si el servicio
   `obtenQuoteEmisorasMC` o una base distinta permite ese histórico.
5. Autorización explícita para consulta automatizada, almacenamiento,
   procesamiento en AWS, uso académico o comercial y eventual visualización
   o redistribución; revisar además el alcance de la autorización existente.

## Criterio para aceptar la fuente

Con una muestra y autorización aplicable, comparar las 35 parejas exactas del
17-11-2026 contra el reporte previo: valores de los 16 PPP, estado y cobertura
de los 19 faltantes, fecha y moneda. Registrar discrepancias y naturaleza de
cada valor sin imputación. Probar posteriormente otras sesiones solo con
catálogos fechados respaldados. El cotejo entre dos productos BMV no constituye
validación independiente. No se promueven composición IPC, datos a producción,
modelos ni señales con la evidencia actual.
