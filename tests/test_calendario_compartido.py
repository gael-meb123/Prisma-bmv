import unittest
import importlib
from datetime import date
from unittest.mock import patch
from prisma.domain import calendario_bmv as calendario, bmv_core

guardia = importlib.import_module("infra.lambda.guardia_senales.handler")


class CalendarioTest(unittest.TestCase):
    def test_paridad_y_feriados(self):
        self.assertEqual(guardia.sesiones("2026-11-19"), bmv_core.ultimas_sesiones("2026-11-19", 21))
        self.assertNotIn("2026-11-16", guardia.sesiones("2026-11-19"))

    def test_variable_no_habilita_anio(self):
        with patch.dict("os.environ", {"FERIADOS_BMV_EXTRA": "2027-01-01"}):
            self.assertFalse(bmv_core.calendario_verificado(2027))
            with self.assertRaises(ValueError):
                calendario.es_sesion_bmv(date(2027, 1, 4))
            with self.assertRaises(ValueError):
                guardia.sesiones("2027-01-04")

    def test_ventana_no_cruza_anio_desconocido(self):
        with self.assertRaises(ValueError):
            guardia.sesiones("2026-01-02")
        with self.assertRaises(ValueError):
            bmv_core.sumar_sesiones("2026-12-31", 1)

    def test_cruce_con_calendario_sintetico_no_habilita_2027(self):
        with patch.dict(calendario.FERIADOS_BMV, {2027: frozenset({"2027-01-01"})}):
            ventana = guardia.sesiones("2027-01-04")
            self.assertEqual(len(ventana), 21)
            self.assertTrue(ventana[0].startswith("2026"))
            self.assertNotIn("2027-01-01", ventana)
        self.assertFalse(calendario.calendario_verificado(2027))
