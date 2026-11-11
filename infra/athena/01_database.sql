-- Prisma BMV - Generado a partir de prisma/domain/bmv_core.py (orden canónico de columnas).
-- OpenCSVSerde lee por POSICIÓN: no reordene columnas sin regenerar este archivo
-- (python scripts/crear_tablas_athena.py --solo-imprimir).
-- Sustituya ${BUCKET} por el nombre de su bucket (el script lo hace automáticamente).

CREATE DATABASE IF NOT EXISTS prisma_bmv
COMMENT 'Lakehouse Prisma BMV: capas Silver y Gold del PPP oficial';
