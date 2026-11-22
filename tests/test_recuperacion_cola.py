import unittest
from scripts.inspeccionar_fallo_recolector import preparar_reintento
from scripts.planificar_scheduler_seguro import FUNCION


class RecuperacionTest(unittest.TestCase):
    def evento(self, payload):
        return {"requestContext": {"functionArn": FUNCION + ":$LATEST", "condition": "RetriesExhausted"},
                "requestPayload": payload}

    def test_fecha_original_no_fecha_de_reproceso(self):
        result = preparar_reintento(self.evento({"instante_programado": "2026-11-20T01:00:00Z"}))
        self.assertEqual(result, {"fecha": "2026-11-19"})

    def test_no_reintenta_sintetico_sin_fecha_otro_destino_o_calendario(self):
        for payload in ({}, {"prueba_fallo_controlado": "x"}, {"fecha": "2027-01-04"}):
            with self.assertRaises(ValueError):
                preparar_reintento(self.evento(payload))
        ev = self.evento({"fecha": "2026-11-19"})
        ev["requestContext"]["functionArn"] = "otra"
        with self.assertRaises(ValueError):
            preparar_reintento(ev)
