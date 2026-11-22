# Candidatos para ampliación: contraste NAFTRAC / boletín BMV

**Estado: referencia provisional, no lista oficial del IPC.** Fecha de las
posiciones y del boletín comparados: 17 de noviembre de 2026. Consulta realizada
el 18 de noviembre de 2026.

## Fuentes y límites

- [Ficha de iShares NAFTRAC de BlackRock](https://www.blackrock.com/mx/intermediarios/productos/251895/ishares-naftrac-fund)
  indica que el fondo busca seguir el S&P/BMV IPC y reporta 35 valores
  subyacentes al 17-11-2026.
- [Descarga de posiciones del fondo](https://www.blackrock.com/mx/intermediarios/productos/251895/ishares-naftrac-fund/1501904811835.ajax?fileType=csv&fileName=NAFTRAC_holdings&dataType=fund)
  mostró 35 posiciones de renta variable y dos posiciones de efectivo. La
  composición de un ETF **no es la lista oficial del índice**: puede diferir
  por operaciones del fondo, fechas, efectivo o metodología.
- [Boletín BMV del 17-11-2026](https://www.bmv.com.mx/docs-pub/rss/boletin20261117.html)
  contiene tablas seleccionadas —alzas, bajas y más negociadas—, no la lista
  completa de componentes. Una ausencia no demuestra que no hubo cotización.
- La ficha oficial del índice de S&P devolvió 403 en este entorno y la página
  dinámica de BMV no devolvió las filas de componentes. **La lista oficial y la
  fecha de vigencia del índice siguen sin verificarse.**

Los identificadores siguientes son los *tickers de BlackRock*, no un catálogo
validado de pares emisora/serie BMV. En especial, se deben verificar
`LIVEPOLC.1` frente a `LIVEPOL C-1`, `RA` y las series de cada clave antes de
utilizarlos en el parser o en permisos. La autorización BMV comunicada por el
usuario no implica por sí sola derechos de redistribución de datos de BlackRock
o Yahoo; verificar las condiciones aplicables a cada fuente.

## Las 35 posiciones accionarias del fondo

Se excluyen `MXN` y `USD`, clasificados como efectivo. Los 15 nombres conocidos
se indican como coincidencias **provisionales por clave**, no como confirmación
de vigencia oficial del índice.

| Posiciones que corresponden provisionalmente al catálogo local de 15 | |
|---|---|
| GMEXICOB | GFNORTEO |
| AMXB | WALMEX* |
| FEMSAUBD | CEMEXCPO |
| GAPB | PE&OLES* |
| AC* | ASURB |
| BIMBOA | VESTA* |
| GFINBURO | GRUMAB |
| LIVEPOLC.1 | |

### 20 candidatos adicionales respecto al catálogo local

| Ticker tal como lo publica BlackRock | Ticker tal como lo publica BlackRock |
|---|---|
| KOFUBL | SIGMAFA |
| OMAB | PINFRA* |
| KIMBERA | BBAJIOO |
| Q* | GENTERA* |
| CHDRAUIB | GCARSOA1 |
| ALSEA* | ALPEKA |
| MEGACPO | GCC* |
| RA | ORBIA* |
| BOLSAA | LACOMERUBC |
| VOLARA | LABB |

No incorporar estos símbolos directamente a producción: falta validar su
identidad, serie, fuente y vigencia con BMV o un proveedor autorizado.

## Comparación puntual de precios

Para la misma sesión, la columna `Precio` de las posiciones del ETF coincide
numéricamente con el **PPP** del boletín BMV en estos ejemplos:

| Clave BMV | PPP boletín | Precio en posiciones NAFTRAC |
|---|---:|---:|
| GMEXICO B | 212.83 | 212.83 |
| GFNORTE O | 202.00 | 202.00 |
| WALMEX * | 55.08 | 55.08 |
| GCARSO A1 | 174.11 | 174.11 |
| KIMBER A | 39.43 | 39.43 |
| ALSEA * | 58.19 | 58.19 |
| VOLAR A | 15.14 | 15.14 |

Es una comprobación puntual de coincidencia; no demuestra independencia de las
fuentes ni que todos los precios del fondo siempre representen PPP. Por ejemplo,
el boletín también muestra para GMEXICO B un **último** de 213.50, distinto del
PPP de 212.83. El cierre de Yahoo u otras fuentes no debe sustituirse como PPP.

## Próximo paso

Obtener o contrastar la muestra oficial con fecha de vigencia y resolver series
y alias. En paralelo, desarrollar y probar el catálogo y la captura con
aislamiento de versiones y sin modificar producción. Registrar el alcance de la
autorización BMV y confirmar las condiciones de las fuentes secundarias antes de
utilizarlas para redistribución.
