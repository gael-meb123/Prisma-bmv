-- Prisma BMV - Generado a partir de prisma/domain/bmv_core.py (orden canónico de columnas).
-- OpenCSVSerde lee por POSICIÓN: no reordene columnas sin regenerar este archivo
-- (python scripts/crear_tablas_athena.py --solo-imprimir).
-- Sustituya ${BUCKET} por el nombre de su bucket (el script lo hace automáticamente).

-- Huecos (NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA) llegan como campos vacíos: con
-- use.null.for.invalid.data = true Athena los entrega como NULL en las columnas DOUBLE.
-- Las particiones anio/mes se resuelven por proyección: no hace falta MSCK REPAIR TABLE.
CREATE EXTERNAL TABLE IF NOT EXISTS prisma_bmv.bmv_silver_ppp (
  `fecha` STRING,
  `emisora` STRING,
  `serie` STRING,
  `anillo_madurez` STRING,
  `sector_economico` STRING,
  `estado_captura` STRING,
  `ppp_bmv_mxn` DOUBLE,
  `ultimo_bmv_mxn` DOUBLE,
  `anterior_bmv_mxn` DOUBLE,
  `variacion_ppp_vs_anterior_pct` DOUBLE,
  `evidencia_exacta` STRING,
  `url_fuente` STRING,
  `sha256_boletin` STRING
)
PARTITIONED BY (`anio` INT, `mes` INT)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '"', 'escapeChar' = '\\')
STORED AS TEXTFILE
LOCATION 's3://${BUCKET}/silver/precios_ppp/'
TBLPROPERTIES (
  'skip.header.line.count' = '1',
  'use.null.for.invalid.data' = 'true',
  'projection.enabled' = 'true',
  'projection.anio.type' = 'integer',
  'projection.anio.range' = '2016,2035',
  'projection.mes.type' = 'integer',
  'projection.mes.range' = '1,12',
  'projection.mes.digits' = '2',
  'storage.location.template' = 's3://${BUCKET}/silver/precios_ppp/${anio}/${mes}/'
);
