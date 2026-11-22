import json
import unittest
from datetime import datetime, timezone

from prisma.data.capitales_bmv_experimental import interpretar


def respuesta(filas, ok=True):
    obj = {"success": ok, "response": {"resultado": {"A": filas}}}
    return "for(;;);(" + json.dumps(obj) + ")\n<!-- tiempo -->"


def fila(ppp=0):
    return {"cveCorta": "R", "cveSerie": "A",
            "datosEstadistica": {"ppp": ppp, "precioUltimoHecho": 42,
                                 "fecha": None, "hora": "09:38"}}


class CapitalesTest(unittest.TestCase):
    def setUp(self):
        self.ahora = datetime(2026, 11, 19, tzinfo=timezone.utc)

    def test_cero_no_es_ppp_y_ultimo_separado(self):
        f = interpretar(respuesta([fila()]), self.ahora)[0]
        self.assertIsNone(f["ppp"])
        self.assertEqual(f["ultimo"], 42)
        self.assertIsNone(f["fecha_fuente"])
        self.assertEqual(f["estado_ppp"], "NO_DISPONIBLE_O_INVALIDO")

    def test_positivo_sigue_sin_validar(self):
        self.assertEqual(interpretar(respuesta([fila(42.1)]), self.ahora)[0]["estado_ppp"],
                         "OBSERVADO_NO_VALIDADO")

    def test_rechaza_fallos_duplicados_y_zona_ausente(self):
        for texto in (respuesta([fila(), fila()]), respuesta([fila()], False), "basura",
                      respuesta([{"cveCorta": "R"}])):
            with self.assertRaises((ValueError, TypeError)):
                interpretar(texto, self.ahora)
        with self.assertRaises(ValueError):
            interpretar(respuesta([]), datetime(2026, 11, 19))


if __name__ == "__main__":
    unittest.main()
