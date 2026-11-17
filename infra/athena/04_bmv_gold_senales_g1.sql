-- Prisma BMV - Generado a partir de prisma/domain/bmv_core.py (orden canónico de columnas).
-- OpenCSVSerde lee por POSICIÓN: no reordene columnas sin regenerar este archivo
-- (python scripts/crear_tablas_athena.py --solo-imprimir).
-- Sustituya ${BUCKET} por el nombre de su bucket (el script lo hace automáticamente).

-- 1ª generación: todas las columnas como STRING porque los registros históricos mezclan
-- formatos (p. ej. probabilidades con '%'). Use CAST/TRY_CAST en las consultas.
CREATE EXTERNAL TABLE IF NOT EXISTS prisma_bmv.bmv_gold_senales_g1 (
  `id_senal` STRING,
  `fecha_senal` STRING,
  `fecha_objetivo_h5` STRING,
  `emisora` STRING,
  `serie` STRING,
  `ppp_base_mxn` STRING,
  `cambio_diario_pct` STRING,
  `rol_modelo` STRING,
  `algoritmo` STRING,
  `n_entrenamiento` STRING,
  `prob_subida_h5` STRING,
  `prob_subida_pct` STRING,
  `prediccion_clase` STRING,
  `prediccion_etiqueta` STRING,
  `estado_consenso` STRING,
  `url_boletin_bmv` STRING,
  `sha256_boletin_bmv` STRING,
  `estado_resolucion` STRING,
  `fecha_resolucion_real` STRING,
  `ppp_t5_mxn` STRING,
  `retorno_real_h5_pct` STRING,
  `y_real_h5` STRING,
  `acierto` STRING,
  `log_loss_individual` STRING,
  `brier_individual` STRING,
  `timestamp_emision_utc` STRING,
  `estado_validez` STRING,
  `calendario_objetivo` STRING,
  `estado_consenso_original` STRING,
  `fecha_corte_datos` STRING,
  `fecha_emision_real` STRING,
  `estado_trazabilidad_emision` STRING,
  `version_features` STRING,
  `version_metodologia` STRING,
  `apta_evaluacion_prospectiva` STRING,
  `fecha_corte_entrenamiento` STRING,
  `timestamp_captura_datos_utc` STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '"', 'escapeChar' = '\\')
STORED AS TEXTFILE
LOCATION 's3://${BUCKET}/gold/senales_g1/'
TBLPROPERTIES ('skip.header.line.count' = '1');
