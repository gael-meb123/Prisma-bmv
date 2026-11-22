import copy
import csv
import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd

from prisma.data.repository import RepositorioAthena
from scripts.entorno_aislado import DDL, TABLE_NAME, columnas_ddl, migrar, plantilla, recursos, revertir


def tabla(location="s3://bucket-aislado/releases/bootstrap/", version="0"):
    return {
        "Name": TABLE_NAME, "VersionId": version, "TableType": "EXTERNAL_TABLE",
        "StorageDescriptor": {
            "Location": location,
            "Columns": [{"Name": n, "Type": t} for n, t in columnas_ddl(DDL.read_text(encoding="utf-8"))],
        },
    }


def csv_sintetico():
    out = io.StringIO(newline="")
    columnas = [n for n, _ in columnas_ddl(DDL.read_text(encoding="utf-8"))]
    w = csv.DictWriter(out, fieldnames=columnas)
    w.writeheader()
    w.writerow({"id_senal_g2": "SINTETICO_1", "emisora": "FICTICIA"})
    return out.getvalue().encode()


class SilverAthenaTest(unittest.TestCase):
    def repo(self, particiones):
        r = RepositorioAthena.__new__(RepositorioAthena)
        r._database = "default"
        r._particiones_silver = None
        r._glue = Mock()
        r._glue.get_table.return_value = {"Table": {"PartitionKeys": [{"Name": p} for p in particiones]}}
        r._athena = Mock()
        r._athena.ejecutar.return_value = SimpleNamespace(datos=pd.DataFrame([{"fecha": "2026-11-17"}]))
        return r

    def test_sin_particiones_no_referencia_anio_y_cachea(self):
        r = self.repo([])
        r._precios_crudos()
        r._precios_crudos()
        sql = r._athena.ejecutar.call_args.args[0]
        self.assertNotIn("anio", sql)
        self.assertIn("fecha >=", sql)
        self.assertEqual(r._glue.get_table.call_count, 1)

    def test_particionada_filtra_anio(self):
        r = self.repo(["anio", "mes"])
        r._precios_crudos()
        self.assertIn("anio >=", r._athena.ejecutar.call_args.args[0])

    def test_error_glue_no_se_silencia(self):
        r = self.repo([])
        r._glue.get_table.side_effect = RuntimeError("permiso denegado")
        with self.assertRaises(RuntimeError):
            r._precios_crudos()
        r._athena.ejecutar.assert_not_called()


class AisladoTest(unittest.TestCase):
    def test_plantilla_no_tiene_scheduler_ni_recursos_produccion(self):
        t = plantilla()
        self.assertEqual(len(t["Resources"]["GoldTable"]["Properties"]["TableInput"]["StorageDescriptor"]["Columns"]), 42)
        self.assertFalse(any("Scheduler" in r["Type"] for r in t["Resources"].values()))
        self.assertEqual(t["Resources"]["Bucket"]["DeletionPolicy"], "Retain")
        self.assertNotIn("recolector-diario-bmv", str(t))

    def test_migrar_y_revertir_con_version_optimista(self):
        glue, s3 = Mock(), Mock()
        original = tabla()
        glue.get_table.return_value = {"Table": original}
        resultado = migrar(s3, glue, "bucket-aislado", "db", "v1", csv_sintetico())
        self.assertEqual(resultado["filas"], 1)
        self.assertEqual(resultado["version_glue_anterior"], "0")
        self.assertEqual(s3.put_object.call_args.kwargs["IfNoneMatch"], "*")
        cambio = glue.update_table.call_args.kwargs
        self.assertEqual(cambio["VersionId"], "0")
        self.assertEqual(cambio["TableInput"]["StorageDescriptor"]["Location"], "s3://bucket-aislado/releases/v1/")
        actual = copy.deepcopy(original)
        actual["VersionId"] = "1"
        actual["StorageDescriptor"]["Location"] = "s3://bucket-aislado/releases/v1/"
        glue.get_table.return_value = {"Table": actual}
        glue.get_table_version.return_value = {"TableVersion": {"Table": original}}
        self.assertEqual(revertir(glue, "bucket-aislado", "db", "0"), "s3://bucket-aislado/releases/bootstrap/")
        self.assertEqual(glue.update_table.call_args.kwargs["VersionId"], "1")
        s3.delete_object.assert_not_called()

    def test_rechaza_fuera_de_aislamiento_antes_de_escribir(self):
        glue, s3 = Mock(), Mock()
        glue.get_table.return_value = {"Table": tabla("s3://produccion/gold/")}
        with self.assertRaises(ValueError):
            migrar(s3, glue, "bucket-aislado", "db", "v1", csv_sintetico())
        s3.put_object.assert_not_called()

    def test_rechaza_csv_invalido_y_stack_no_aislado(self):
        s3, glue = Mock(), Mock()
        with self.assertRaises(ValueError):
            migrar(s3, glue, "bucket-aislado", "db", "v1", b"id_senal_g2\nREAL\n")
        with self.assertRaises(ValueError):
            recursos(Mock(), "produccion")
        s3.put_object.assert_not_called()
        glue.update_table.assert_not_called()


if __name__ == "__main__":
    unittest.main()
