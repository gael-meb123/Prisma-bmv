-- Prisma BMV - Vistas de conveniencia sobre las tablas externas.

-- Señales G2 con fecha tipada y acierto parcial como booleano.
CREATE OR REPLACE VIEW prisma_bmv.v_senales_g2_tipadas AS
SELECT
  *,
  CAST(fecha_senal AS DATE)        AS fecha_senal_d,
  CAST(fecha_objetivo_h5 AS DATE)  AS fecha_objetivo_d,
  CASE lower(acierto_parcial_en_curso) WHEN 'true' THEN TRUE WHEN 'false' THEN FALSE END AS acierto_parcial_bool
FROM prisma_bmv.bmv_gold_senales_g2;
