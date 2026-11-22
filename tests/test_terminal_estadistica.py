import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import app
from core.supabase_auth import Usuario
from core.supabase_auth import usuario_actual
from core.terminal_api import estadistica
from tests.test_estadistica_descriptiva import datos


class TerminalEstadisticaTest(unittest.TestCase):
    def test_ruta_http_y_parametros(self):
        u = Usuario("1", "a@example.com", "A", "user", "explorer")
        h, p = datos()
        h["emisora"] = "WALMEX"
        p["emisora"] = "WALMEX"
        app.dependency_overrides[usuario_actual] = lambda: u
        try:
            with patch("core.terminal_api.pd.read_csv", side_effect=[h, p]):
                respuesta = TestClient(app).get("/api/terminal/estadistica", params={
                    "emisora": "WALMEX", "desde": "2025-01-01", "hasta": "2025-01-02",
                })
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta.json()["cobertura_historico"]["registros"], 2)
        finally:
            app.dependency_overrides.pop(usuario_actual, None)

    def test_acceso_y_fechas(self):
        u = Usuario("1", "a@example.com", "A", "user", "explorer")
        with self.assertRaises(HTTPException) as error:
            estadistica("GMEXICO", u=u)
        self.assertEqual(error.exception.status_code, 403)
        with self.assertRaises(HTTPException) as error:
            estadistica("WALMEX", date(2025, 2, 1), date(2025, 1, 1), u)
        self.assertEqual(error.exception.status_code, 422)

    def test_resultado_solo_emisora_autorizada(self):
        h, p = datos()
        h = pd.concat([h, h.assign(emisora="WALMEX")], ignore_index=True)
        p = pd.concat([p, p.assign(emisora="WALMEX")], ignore_index=True)
        u = Usuario("1", "a@example.com", "A", "user", "explorer")
        with patch("core.terminal_api.pd.read_csv", side_effect=[h, p]):
            r = estadistica("WALMEX", u=u)
        self.assertEqual(r["cobertura_historico"]["registros"], 4)
        self.assertEqual({fila["emisora"] for fila in r["serie_historica_verificada"]}, {"WALMEX"})

    def test_error_fuentes(self):
        u = Usuario("1", "a@example.com", "A", "user", "explorer")
        with patch("core.terminal_api.pd.read_csv", side_effect=FileNotFoundError):
            with self.assertRaises(HTTPException) as error:
                estadistica("WALMEX", u=u)
        self.assertEqual(error.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
