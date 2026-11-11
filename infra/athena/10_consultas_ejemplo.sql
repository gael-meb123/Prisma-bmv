-- Prisma BMV - Consultas de referencia para Amazon Athena (Trino).
-- Filtre siempre por anio/mes en Silver: la proyección de particiones limita lo que se escanea.

-- 1. Boletín de una sesión, con huecos visibles.
SELECT emisora, serie, estado_captura, ppp_bmv_mxn, variacion_ppp_vs_anterior_pct, sha256_boletin
FROM prisma_bmv.bmv_silver_ppp
WHERE anio = 2026 AND mes = 10 AND fecha = '2026-10-30'
ORDER BY emisora;

-- 2. Cobertura: huecos documentados por emisora en el año.
SELECT emisora,
       COUNT(*) FILTER (WHERE estado_captura = 'PPP_PUBLICADO_VERIFICADO')          AS con_ppp,
       COUNT(*) FILTER (WHERE estado_captura = 'NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA') AS huecos
FROM prisma_bmv.bmv_silver_ppp
WHERE anio = 2026
GROUP BY emisora
ORDER BY huecos DESC;

-- 3. Consenso del panel G2 en la última fecha de señal.
SELECT emisora, modelo_g2, ROUND(probabilidad_subida * 100, 2) AS prob_pct,
       prediccion_etiqueta, estado_consenso_g2, ROUND(ret_10_rel_panel * 100, 2) AS rel_pp
FROM prisma_bmv.bmv_gold_senales_g2
WHERE fecha_senal = (SELECT MAX(fecha_senal) FROM prisma_bmv.bmv_gold_senales_g2)
ORDER BY emisora, modelo_g2;

-- 4. Marcador por modelo: aciertos parciales y resolución en t+5.
SELECT modelo_g2,
       COUNT(*)                                                     AS senales,
       COUNT_IF(acierto_parcial_bool)                               AS aciertos_parciales,
       COUNT_IF(estado_resolucion = 'RESUELTA_T+5')                  AS resueltas,
       SUM(acierto_direccional_t5)                                  AS aciertos_t5,
       ROUND(AVG(brier_observado_t5), 4)                            AS brier_medio_t5
FROM prisma_bmv.v_senales_g2_tipadas
GROUP BY modelo_g2
ORDER BY modelo_g2;

-- 5. Trazabilidad: de una señal al boletín exacto que la originó.
SELECT g.id_senal_g2, g.ppp_base_t, s.ppp_bmv_mxn, g.sha256_boletin_base, s.sha256_boletin
FROM prisma_bmv.bmv_gold_senales_g2 g
JOIN prisma_bmv.bmv_silver_ppp s
  ON s.fecha = g.fecha_senal AND s.emisora = g.emisora
 AND s.anio = CAST(substr(g.fecha_senal, 1, 4) AS INT) AND s.mes = CAST(substr(g.fecha_senal, 6, 2) AS INT)
WHERE g.fecha_senal >= '2026-10-28';
