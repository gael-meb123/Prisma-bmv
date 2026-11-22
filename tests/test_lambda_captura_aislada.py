import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from tests.test_captura_ampliada import html_filas

RUTA = Path(__file__).resolve().parent.parent / "infra/lambda/captura_ampliada_aislada/handler.py"
spec = importlib.util.spec_from_file_location("captura_aislada_handler", RUTA)
handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handler)


class Precondicion(Exception):
    response = {"Error": {"Code": "PreconditionFailed"}}


class S3:
    def __init__(self):
        self.objetos = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        assert kwargs["IfNoneMatch"] == "*"
        if (Bucket, Key) in self.objetos:
            raise Precondicion()
        self.objetos[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objetos[(Bucket, Key)])}

    def list_objects_v2(self, Bucket, Prefix, MaxKeys):
        keys = [k for b, k in self.objetos if b == Bucket and k.startswith(Prefix)]
        return {"Contents": [{"Key": k} for k in keys[:MaxKeys]], "IsTruncated": len(keys) > MaxKeys}


class LambdaCapturaAisladaTest(unittest.TestCase):
    def test_idempotencia_y_separacion_de_capas(self):
        s3 = S3()
        raw = html_filas(("GMEXICO", "B", "213.50", "220.49", "212.83"))
        args = ({"fecha": "2026-11-17"}, s3, lambda _: raw, "prisma-bmv-captura-aislada-test")
        primero = handler.ejecutar(*args)
        segundo = handler.ejecutar(*args)
        self.assertEqual(primero, segundo)
        self.assertEqual(len(s3.objetos), 4)
        self.assertEqual(primero["resumen"]["PPP_OBSERVADO_MAPEO_PROVISIONAL"], 1)
        self.assertTrue(primero["silver"].startswith("experimental/v1/silver/"))
        self.assertNotIn("gold", str(primero))

    def test_hash_diferente_no_produce_otro_silver(self):
        s3 = S3()
        raw = html_filas(("GMEXICO", "B", "213.50", "220.49", "212.83"))
        bucket = "prisma-bmv-captura-aislada-test"
        handler.ejecutar({"fecha": "2026-11-17"}, s3, lambda _: raw, bucket)
        with self.assertRaisesRegex(ValueError, "HASH_DIVERGENTE"):
            handler.ejecutar({"fecha": "2026-11-17"}, s3, lambda _: raw + b"<!-- distinto -->", bucket)
        self.assertEqual(len([k for _, k in s3.objetos if "/silver/" in k]), 1)
        informes = [json.loads(v) for (b, k), v in s3.objetos.items() if "/cuarentena/" in k and k.endswith(".json")]
        self.assertEqual(informes[0]["comparacion"], "FILAS_IGUALES")

    def test_cambio_de_precio_queda_en_cuarentena(self):
        s3, bucket = S3(), "prisma-bmv-captura-aislada-test"
        raw = html_filas(("GMEXICO", "B", "10", "9", "9.5"))
        handler.ejecutar({"fecha": "2026-11-17"}, s3, lambda _: raw, bucket)
        with self.assertRaisesRegex(ValueError, "HASH_DIVERGENTE"):
            handler.ejecutar({"fecha": "2026-11-17"}, s3, lambda _: raw.replace(b"9.5", b"9.6"), bucket)
        informes = [json.loads(v) for (b, k), v in s3.objetos.items() if "/cuarentena/" in k and k.endswith(".json")]
        self.assertEqual(informes[0]["comparacion"], "FILAS_DISTINTAS")
        self.assertIn("ppp_bmv_mxn", informes[0]["diferencias"][0]["campos"])

    def test_fallo_red_no_escribe(self):
        s3 = S3()
        with self.assertRaises(TimeoutError):
            handler.ejecutar({"fecha": "2026-11-17"}, s3, Mock(side_effect=TimeoutError()), "prisma-bmv-captura-aislada-test")
        self.assertEqual(s3.objetos, {})

    def test_interrupcion_y_recuperacion_misma_firma(self):
        class S3Falla(S3):
            fallo = True
            def put_object(self, Bucket, Key, Body, **kwargs):
                if "/silver/" in Key and self.fallo:
                    self.fallo = False
                    raise OSError("error simulado")
                super().put_object(Bucket, Key, Body, **kwargs)
        s3 = S3Falla()
        raw = html_filas(("GMEXICO", "B", "10", "9", "9.5"))
        args = ({"fecha": "2026-11-17"}, s3, lambda _: raw, "prisma-bmv-captura-aislada-test")
        with self.assertRaises(OSError):
            handler.ejecutar(*args)
        self.assertFalse(any("/manifiestos/" in k for _, k in s3.objetos))
        self.assertEqual(handler.ejecutar(*args)["estado"], "CAPTURA_EXPERIMENTAL")

    def test_bloqueo_incompleto_hash_diferente_va_a_cuarentena(self):
        s3, bucket = S3(), "prisma-bmv-captura-aislada-test"
        s3.objetos[(bucket, "experimental/v1/bloqueos/2026-11-17.json")] = b'{"sha256":"otra"}'
        raw = html_filas(("GMEXICO", "B", "10", "9", "9.5"))
        with self.assertRaisesRegex(ValueError, "HASH_DIVERGENTE"):
            handler.ejecutar({"fecha": "2026-11-17"}, s3, lambda _: raw, bucket)
        self.assertFalse(any("/silver/" in k for _, k in s3.objetos))
        informes = [json.loads(v) for (_, k), v in s3.objetos.items() if "/cuarentena/" in k and k.endswith(".json")]
        self.assertEqual(informes[0]["comparacion"], "NO_DISPONIBLE")

    def test_rechaza_bucket_fecha_y_evento_antes_de_descargar(self):
        descargar = Mock()
        for evento, bucket in [
            ({"fecha": "2026-11-17"}, "prisma-bmv-datalake-tunombre-2026"),
            ({"fecha": "2026-11-18"}, "prisma-bmv-captura-aislada-test"),
            ({"fecha": "2026-11-17", "bucket": "otro"}, "prisma-bmv-captura-aislada-test"),
        ]:
            with self.assertRaises(ValueError):
                handler.ejecutar(evento, S3(), descargar, bucket)
        descargar.assert_not_called()

    def test_rechaza_contenido_conflictivo_sin_sobrescribir(self):
        s3 = S3()
        bucket, key = "prisma-bmv-captura-aislada-test", "experimental/v1/test"
        handler._guardar_inmutable(s3, bucket, key, b"original", "text/plain")
        with self.assertRaises(ValueError):
            handler._guardar_inmutable(s3, bucket, key, b"otro", "text/plain")
        self.assertEqual(s3.objetos[(bucket, key)], b"original")


if __name__ == "__main__":
    unittest.main()
