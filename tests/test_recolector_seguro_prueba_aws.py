import importlib
import sys
import unittest
from unittest.mock import patch

prueba = importlib.import_module("infra.lambda.recolector_seguro.prueba_aws")


class Cliente:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return {}


class AislamientoTest(unittest.TestCase):
    def test_diagnostico_fuente_solo_descarga_y_valida(self):
        with patch.dict(sys.modules, {"boto3": object()}), \
                patch.object(prueba.recolector, "descargar", return_value=b"contenido") as descarga, \
                patch.object(prueba.recolector, "_filas", return_value=[{}]) as valida:
            resultado = prueba.lambda_handler({"fecha_fuente": "2026-11-20"}, None)
            self.assertEqual(resultado["estado"], "BOLETIN_VALIDADO")
            self.assertTrue(resultado["sin_escrituras"])
            descarga.assert_called_once()
            valida.assert_called_once()
            with self.assertRaises(ValueError):
                prueba.lambda_handler({"fecha_fuente": "2026-11-21"}, None)

    def test_diagnostico_rechaza_pagina_no_valida(self):
        with patch.dict(sys.modules, {"boto3": object()}), \
                patch.object(prueba.recolector, "descargar", return_value=b"mantenimiento"), \
                patch.object(prueba.recolector, "_filas", side_effect=ValueError("Fecha no reconocida")):
            resultado = prueba.lambda_handler({"fecha_fuente": "2026-11-20"}, None)
            self.assertEqual(resultado["estado"], "FUENTE_NO_VALIDADA")
            self.assertTrue(resultado["sin_escrituras"])

    def test_lecturas_y_escrituras_solo_van_al_bucket_de_prueba(self):
        cliente = Cliente()
        s3 = prueba.RedirigirS3(cliente, "pruebas/recolector-seguro/abc/")
        s3.put_object(Bucket=prueba.ORIGEN, Key="bronze/test", Body=b"x", IfNoneMatch="*")
        s3.get_object(Bucket=prueba.ORIGEN, Key="silver/precios_ppp/test")
        for llamada in cliente.calls:
            self.assertEqual(llamada["Bucket"], prueba.DESTINO)
            self.assertTrue(llamada["Key"].startswith("pruebas/recolector-seguro/abc/"))
        with self.assertRaises(ValueError):
            s3.put_object(Bucket=prueba.ORIGEN, Key="gold/test", Body=b"x")
        with self.assertRaises(ValueError):
            s3.get_object(Bucket="otro", Key="bronze/test")
        self.assertEqual(len(cliente.calls), 2)


if __name__ == "__main__":
    unittest.main()
