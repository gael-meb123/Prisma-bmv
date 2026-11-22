import unittest
from unittest.mock import patch

import pandas as pd

from core.data_provider import obtener_fechas_mercado


class FechasMercadoTest(unittest.TestCase):
    def test_sin_archivo_no_inventa_fechas(self):
        with patch("core.data_provider.cargar_monitoreo_en_vivo", return_value=pd.DataFrame()):
            self.assertEqual(obtener_fechas_mercado(), [])

    def test_sin_columna_fecha_no_inventa_fechas(self):
        with patch("core.data_provider.cargar_monitoreo_en_vivo", return_value=pd.DataFrame({"emisora": ["WALMEX"]})):
            self.assertEqual(obtener_fechas_mercado(), [])

    def test_usa_fechas_disponibles(self):
        datos = pd.DataFrame({"fecha": ["2026-11-17", "2026-11-04", "2026-11-17"]})
        with patch("core.data_provider.cargar_monitoreo_en_vivo", return_value=datos):
            self.assertEqual(obtener_fechas_mercado(), ["2026-11-17", "2026-11-04"])
