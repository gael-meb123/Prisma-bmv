import unittest

from scripts.diagnostico_aws_educativo import diagnosticar


class Cliente:
    def __getattr__(self, nombre):
        def llamar(**kwargs):
            if nombre == "get_table":
                raise PermissionError("no autorizado; no mostrar detalles")
            return {"Environment": {"Variables": {"SECRET": "no imprimir"}}}
        return llamar


class Session:
    def client(self, nombre, region_name):
        return Cliente()


class DiagnosticoTest(unittest.TestCase):
    def test_permiso_negado_no_es_exito_ni_muestra_secretos(self):
        r = diagnosticar(Session(), "us-east-1", "bucket", "default", "tabla", "f", "s")
        self.assertEqual(r["resultados"]["glue_get_table"]["estado"], "NO_VERIFICADO")
        self.assertEqual(r["resultados"]["s3_head_bucket"]["estado"], "LECTURA_OK")
        self.assertNotIn("SECRET", str(r))
        self.assertIn("No prueba permisos de escritura", r["limites"])


if __name__ == "__main__":
    unittest.main()
