-- Contrato del CSV producido por lambda_function_con_ia.py observado en AWS.
-- IMPORTANTE: no corresponde al contrato de prisma/domain/bmv_core.py.
-- Aplicar SOLO después de verificar el encabezado y el formato de todos los CSV
-- del prefijo; OpenCSVSerde lee por posición. No modifica los archivos en S3.
-- Plantilla para crear una tabla NUEVA en la base observada; IF NOT EXISTS no
-- corrige una tabla existente. Para actualizar Glue preservar sus propiedades.
-- REPLACE COLUMNS en Athena fue rechazado para este OpenCSVSerde.
CREATE EXTERNAL TABLE IF NOT EXISTS default.bmv_gold_senales_g2 (
  `id_senal_g2` STRING,
  `generacion_modelo` STRING,
  `fecha_senal` STRING,
  `muestra_evaluacion` STRING,
  `fecha_objetivo_h5` STRING,
  `calendario_objetivo` STRING,
  `emisora` STRING,
  `serie` STRING,
  `sector_economico` STRING,
  `modelo_g2` STRING,
  `modo_entrenamiento` STRING,
  `n_train_panel` INT,
  `fin_etiquetas_train_panel` STRING,
  `c_regularizacion` DOUBLE,
  `tau_zona_neutral` DOUBLE,
  `ppp_base_t` DOUBLE,
  `ret_10` DOUBLE,
  `media_ret_10_panel_corte` DOUBLE,
  `ret_10_rel_panel` DOUBLE,
  `volatilidad_20` DOUBLE,
  `probabilidad_subida` DOUBLE,
  `prediccion_clase` INT,
  `prediccion_etiqueta` STRING,
  `estado_consenso_g2` STRING,
  `estado_resolucion` STRING,
  `sesiones_transcurridas` INT,
  `fecha_parcial_reciente` STRING,
  `ppp_parcial_reciente` DOUBLE,
  `retorno_parcial_pct` DOUBLE,
  `acierto_parcial_en_curso` STRING,
  `ppp_t5_observado` DOUBLE,
  `target_y_observado` DOUBLE,
  `acierto_direccional_t5` STRING,
  `brier_observado_t5` DOUBLE,
  `inicio_ventana_21` STRING,
  `fin_ventana_21` STRING,
  `sha256_boletin_base` STRING,
  `url_fuente_base` STRING,
  `version_features` STRING,
  `version_metodologia` STRING,
  `version_monitor_g2` STRING,
  `timestamp_emision_utc` STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '"')
STORED AS TEXTFILE
LOCATION 's3://${BUCKET}/gold/senales_g2/'
TBLPROPERTIES ('skip.header.line.count' = '1', 'use.null.for.invalid.data' = 'true');
