"""Evita confundir el contrato CSV activo con el de la Lambda alternativa."""

import csv
import re
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.verificar_contrato_aws import columnas_ddl, comparar_contrato

ROOT = Path(__file__).resolve().parent.parent
DDL = ROOT / "infra/athena/11_gold_g2_lambda_activa_referencia.sql"
CSV = ROOT / "registro_senales_prospectivas_panel_g2.csv"


class ContratoGoldLambdaActivaTest(unittest.TestCase):
    def test_columnas_y_orden_coinciden_con_el_csv_local(self):
        sql = DDL.read_text(encoding="utf-8")
        columnas = re.findall(r"`([^`]+)`\s+(?:STRING|INT|DOUBLE)", sql)
        with CSV.open(encoding="utf-8-sig", newline="") as archivo:
            encabezado = next(csv.reader(archivo))
        self.assertEqual(columnas, encabezado)
        self.assertEqual(len(columnas), 42)

    def test_tipos_preservan_objetivos_decimales_y_booleanos_textuales(self):
        sql = DDL.read_text(encoding="utf-8")
        self.assertRegex(sql, r"`target_y_observado`\s+DOUBLE")
        self.assertRegex(sql, r"`acierto_direccional_t5`\s+STRING")
        self.assertRegex(sql, r"`acierto_parcial_en_curso`\s+STRING")

    def test_validador_detecta_columnas_desplazadas_y_archivos_incompatibles(self):
        columnas = columnas_ddl(DDL.read_text(encoding="utf-8"))
        tabla = {
            "StorageDescriptor": {
                "Columns": [{"Name": n, "Type": t} for n, t in columnas],
                "SerdeInfo": {"SerializationLibrary": "org.apache.hadoop.hive.serde2.OpenCSVSerde"},
            },
            "Parameters": {"skip.header.line.count": "1", "use.null.for.invalid.data": "true"},
        }
        encabezado = [n for n, _ in columnas]
        self.assertEqual(comparar_contrato(columnas, tabla, {"gold.csv": encabezado}), [])
        self.assertTrue(comparar_contrato(columnas, tabla, {"gold.csv": encabezado[1:]}))
        self.assertTrue(comparar_contrato(columnas, tabla, {}))
        tabla["StorageDescriptor"]["Columns"].pop(3)
        self.assertTrue(comparar_contrato(columnas, tabla, {"gold.csv": encabezado}))

    def test_herramientas_antiguas_bloquean_escrituras(self):
        for comando in [
            [sys.executable, str(ROOT / "scripts/crear_tablas_athena.py"), "--bucket", "dummy"],
            [sys.executable, str(ROOT / "scripts/bootstrap_lakehouse.py"), "--bucket", "dummy"],
        ]:
            resultado = subprocess.run(comando, capture_output=True, text=True)
            self.assertNotEqual(resultado.returncode, 0)
            self.assertIn("bloquead", resultado.stderr.lower())


if __name__ == "__main__":
    unittest.main()
