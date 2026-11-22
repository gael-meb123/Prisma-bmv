import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from api import app
from core.supabase_auth import Usuario, usuario_actual
from core.terminal_api import _CONSENSO_G2_MODELOS, consenso


def fila(emisora, modelo, clase=1, fecha="2026-11-12", objetivo="2026-11-20", prob=.51):
    return {"emisora": emisora, "modelo_g2": modelo, "fecha_senal": fecha,
            "fecha_objetivo_h5": objetivo, "prediccion_clase": clase, "probabilidad_subida": prob}


def datos(filas):
    return {"g2": pd.DataFrame(filas, columns=["emisora", "modelo_g2", "fecha_senal",
                                               "fecha_objetivo_h5", "prediccion_clase", "probabilidad_subida"]),
            "precios": pd.DataFrame({"fecha": ["2026-11-12"]})}


class ConsensoTest(unittest.TestCase):
    def setUp(self):
        self.u = Usuario("1", "a@example.com", "A", "user", "explorer")

    def consultar(self, filas, fecha=None, usuario=None):
        with patch("core.terminal_api._datos", return_value=datos(filas)):
            return consenso(fecha, usuario or self.u)

    def test_consenso_real_y_acceso(self):
        filas = [fila("WALMEX", m) for m in _CONSENSO_G2_MODELOS]
        filas += [fila("GMEXICO", m) for m in _CONSENSO_G2_MODELOS]
        resultado = self.consultar(filas)
        self.assertEqual([x["emisora"] for x in resultado["emisoras"]], ["WALMEX"])
        r = resultado["emisoras"][0]
        self.assertEqual((r["estado"], r["modelos_validos"], r["fecha_objetivo"]), ("subida", 5, "2026-11-20"))
        self.assertEqual(r["modelos"][0]["probabilidad"], .51)
        filas[0]["prediccion_clase"] = 0
        self.assertEqual(self.consultar(filas)["emisoras"][0]["estado"], "divergencia")
        for f in filas[:5]:
            f["prediccion_clase"] = 0
        self.assertEqual(self.consultar(filas)["emisoras"][0]["estado"], "no_subida")

    def test_faltantes_duplicados_invalidos_y_fechas(self):
        filas = [fila("WALMEX", m) for m in _CONSENSO_G2_MODELOS]
        self.assertEqual(self.consultar(filas[:-1])["emisoras"][0]["estado"], "incompleto")
        self.assertEqual(self.consultar(filas + filas[:1])["emisoras"][0]["estado"], "incompleto")
        invalido = [dict(f) for f in filas]
        invalido[0]["probabilidad_subida"] = float("nan")
        self.assertEqual(self.consultar(invalido)["emisoras"][0]["estado"], "incompleto")
        invalido[0]["probabilidad_subida"] = .5
        invalido[0]["fecha_objetivo_h5"] = "2026-11-21"
        self.assertEqual(self.consultar(invalido)["emisoras"][0]["estado"], "incompleto")
        r = self.consultar(filas, date(2026, 11, 11))["emisoras"][0]
        self.assertEqual((r["estado"], r["fecha_senal"]), ("sin_datos", None))

    def test_http_protegido_y_fecha(self):
        cliente = TestClient(app)
        self.assertEqual(cliente.get("/api/terminal/consenso").status_code, 401)
        app.dependency_overrides[usuario_actual] = lambda: self.u
        try:
            with patch("core.terminal_api._datos", return_value=datos([])):
                respuesta = cliente.get("/api/terminal/consenso?fecha=2026-11-11")
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta.json()["fecha_sesion"], "2026-11-11")
            self.assertEqual(respuesta.json()["emisoras"][0]["estado"], "sin_datos")
        finally:
            app.dependency_overrides.pop(usuario_actual, None)


if __name__ == "__main__":
    unittest.main()
