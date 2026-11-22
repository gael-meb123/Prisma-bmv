import io
import sys
import types
import unittest
from unittest.mock import patch

from prisma.data.repository import KEY_MODELOS, RepositorioS3, crear_repositorio
from prisma.settings import Settings


class S3:
    def __init__(self):
        self.clave = None

    def get_object(self, Bucket, Key):
        self.clave = Key
        return {"Body": io.BytesIO(b'{"G2": {}}')}


class RepositorioS3ConfigTest(unittest.TestCase):
    def test_clave_explicita_sin_cambiar_default(self):
        s3 = S3()
        with patch.dict(sys.modules, {"boto3": types.SimpleNamespace(client=lambda *a, **kw: s3)}):
            anterior = RepositorioS3("bucket", "us-east-1")
            anterior.modelos_g2()
            self.assertEqual(s3.clave, KEY_MODELOS)
            repo = crear_repositorio(Settings(fuente_datos="s3", s3_bucket="bucket",
                                             s3_modelos_key="modelos/registro_modelos_g2_oficial.json"))
            self.assertEqual(repo.modelos_g2(), {"G2": {}})
            self.assertEqual(s3.clave, "modelos/registro_modelos_g2_oficial.json")
            with self.assertRaises(ValueError):
                RepositorioS3("bucket", "us-east-1", "")


if __name__ == "__main__":
    unittest.main()
