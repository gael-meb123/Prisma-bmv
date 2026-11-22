# Validación de 35 claves y disponibilidad de PPP

**Corte analizado:** 17 de noviembre de 2026. **Revisión:** 19 de noviembre
de 2026. Catálogo: `naftrac-2026-11-17-v1`.

## Resumen

Se cotejaron los 35 pares propuestos con las tablas visibles del boletín BMV y
con los símbolos de renta variable de la cartera NAFTRAC del mismo corte.

- **16/35** pares aparecen con PPP positivo en las tablas de cotizaciones del
  boletín; sus precios coinciden numéricamente con la columna `Price` de NAFTRAC
  para la misma fecha.
- **1/35**, `MEGA CPO`, aparece en **paquetes negociados**, pero esa tabla
  ofrece precios de operaciones de paquete, no un PPP diario. Se confirmó la
  presencia literal del par en esa sección, **no** su PPP.
- **18/35** no se observaron por par exacto en las tablas anteriores
  revisadas. Esto no significa que no cotizaran o que BMV no disponga del PPP.
- Los **35 símbolos de BlackRock** figuran en las posiciones de renta variable
  de NAFTRAC al corte. Esto verifica su presencia en la cartera, no que todos
  sean componentes oficiales del IPC.
- **Pertenencia oficial al IPC: pendiente para las 35.** No se obtuvo una lista
  oficial fechada. El estado del catálogo no se promovió.

La comprobación de precio para 16 observaciones es una comparación puntual,
no prueba que las fuentes sean independientes ni que `Price` siempre sea PPP.
Los 19 valores ausentes del PPP no se sustituyeron por precios del ETF ni
por cierres de Yahoo.

## Fuentes y trazabilidad

1. [Boletín BMV del 17-11-2026](https://www.bmv.com.mx/docs-pub/rss/boletin20261117.html),
   tablas «Mayor variación a la alza», «Mayor variación a la baja», «Más
   negociadas» y, solo para identidad, «Paquetes negociados». Son tablas
   seleccionadas, no una lista exhaustiva de precios ni de componentes.
2. [Posiciones NAFTRAC con fecha explícita 17-11-2026](https://www.blackrock.com/mx/intermediarios/productos/251895/ishares-naftrac-fund/1501904811835.ajax?fileType=csv&fileName=NAFTRAC_holdings&dataType=fund&asOfDate=20261117).
   Las filas de efectivo `MXN` y `USD` se excluyen. La URL sin `asOfDate`
   cambió al 18-11-2026 al volver a consultarla; no debe mezclarse con el
   reporte de la sesión anterior.
3. Captura local `precios_provisionales.csv`: fuente BMV, hash de la copia local
   `7dbe5e4f54129c70a037aa0e8010f8cf17b7abc5b8ab4b64be9ed165a5b7a044`.
   Athena aislado confirmó 35 pares, 16 PPP y una sola firma para su copia AWS.
   El hash de esa copia es distinto por el script dinámico descrito en
   `docs/ARQUITECTURA_AWS.md`; las filas extraídas coincidieron.

Las autorizaciones comunicadas por el usuario respecto de BMV no acreditan
automáticamente los derechos de conservación o redistribución de BlackRock o
Yahoo. El reporte es una evaluación técnica, no un dictamen jurídico.

## Resultado por clave

La columna **Evidencia BMV** significa:

- **PPP**: pareja literal observada con PPP válido en una tabla de cotización.
- **Paquete**: pareja literal observada solo en paquetes; sin PPP en las tablas
  de cotización examinadas.
- **No observada**: pareja no encontrada en esas tablas, no implica ausencia de
  cotización en el mercado.

`Precio NAFTRAC` indica solo si el precio para ese ticker fue publicado por el
fondo, no disponibilidad confirmada de PPP de BMV. Para los 16 casos con PPP,
el valor numérico de NAFTRAC coincide; no se muestran como PPP los demás precios
del fondo. Todas las equivalencias y la composición permanecen provisionales.

| # | Emisora propuesta | Serie propuesta | Ticker NAFTRAC | Evidencia BMV | PPP BMV MXN | Precio NAFTRAC |
|---:|---|---|---|---|---:|---|
| 1 | GMEXICO | B | GMEXICOB | PPP | 212.83 | Coincide |
| 2 | GFNORTE | O | GFNORTEO | PPP | 202.00 | Coincide |
| 3 | AMX | B | AMXB | PPP | 23.81 | Coincide |
| 4 | WALMEX | * | WALMEX* | PPP | 55.08 | Coincide |
| 5 | FEMSA | UBD | FEMSAUBD | PPP | 242.32 | Coincide |
| 6 | CEMEX | CPO | CEMEXCPO | PPP | 18.76 | Coincide |
| 7 | GAP | B | GAPB | PPP | 428.59 | Coincide |
| 8 | PE&OLES | * | PE&OLES* | PPP | 744.90 | Coincide |
| 9 | AC | * | AC* | PPP | 240.00 | Coincide |
| 10 | ASUR | B | ASURB | No observada | — | Publicado; sin cotejo PPP |
| 11 | BIMBO | A | BIMBOA | PPP | 71.44 | Coincide |
| 12 | VESTA | * | VESTA* | No observada | — | Publicado; sin cotejo PPP |
| 13 | GFINBUR | O | GFINBURO | PPP | 45.76 | Coincide |
| 14 | GRUMA | B | GRUMAB | PPP | 278.19 | Coincide |
| 15 | LIVEPOL | C-1 | LIVEPOLC.1 | No observada | — | Publicado; equivalencia pendiente |
| 16 | KOF | UBL | KOFUBL | No observada | — | Publicado; sin cotejo PPP |
| 17 | SIGMAF | A | SIGMAFA | No observada | — | Publicado; sin cotejo PPP |
| 18 | OMA | B | OMAB | No observada | — | Publicado; sin cotejo PPP |
| 19 | PINFRA | * | PINFRA* | No observada | — | Publicado; sin cotejo PPP |
| 20 | KIMBER | A | KIMBERA | PPP | 39.43 | Coincide |
| 21 | BBAJIO | O | BBAJIOO | No observada | — | Publicado; sin cotejo PPP |
| 22 | Q | * | Q* | No observada | — | Publicado; sin cotejo PPP |
| 23 | GENTERA | * | GENTERA* | No observada | — | Publicado; sin cotejo PPP |
| 24 | CHDRAUI | B | CHDRAUIB | No observada | — | Publicado; sin cotejo PPP |
| 25 | GCARSO | A1 | GCARSOA1 | PPP | 174.11 | Coincide |
| 26 | ALSEA | * | ALSEA* | PPP | 58.19 | Coincide |
| 27 | ALPEK | A | ALPEKA | No observada | — | Publicado; sin cotejo PPP |
| 28 | MEGA | CPO | MEGACPO | Paquete | — | Publicado; sin cotejo PPP |
| 29 | GCC | * | GCC* | No observada | — | Publicado; sin cotejo PPP |
| 30 | R | A | RA | No observada | — | Publicado; equivalencia pendiente |
| 31 | ORBIA | * | ORBIA* | No observada | — | Publicado; sin cotejo PPP |
| 32 | BOLSA | A | BOLSAA | No observada | — | Publicado; sin cotejo PPP |
| 33 | LACOMER | UBC | LACOMERUBC | No observada | — | Publicado; sin cotejo PPP |
| 34 | VOLAR | A | VOLARA | PPP | 15.14 | Coincide |
| 35 | LAB | B | LABB | No observada | — | Publicado; sin cotejo PPP |

## Acciones pendientes

1. Obtener la muestra oficial del IPC con fecha efectiva y series; contrastar
   los 35 pares y publicar otra versión del catálogo.
2. Confirmar expresamente la equivalencia de `RA` con `R` / `A` y de
   `LIVEPOLC.1` con `LIVEPOL` / `C-1`; ninguna se observó en el boletín
   revisado para este corte.
3. Solicitar una fuente BMV o autorizada de PPP diario exhaustivo e histórico,
   incluyendo cobertura, ajustes, licencia y condiciones de acceso. BMV ofrece
   [bases de datos históricas y de cierre](https://www.bmv.com.mx/en/information-products/databases),
   pero esa página no confirma que incluyan PPP por serie.
4. Con nuevos catálogos fechados, verificar otras sesiones sin proyectar la
   composición de esta instantánea. Validar Yahoo solo como fuente diferenciada
   y no como sustituto automático de PPP.
5. No usar esta muestra como habilitación de modelos, permisos ni consenso.
