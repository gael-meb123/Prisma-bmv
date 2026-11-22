import unittest
from scripts.auditar_panel_estadistico import auditar


class AuditoriaPanelTest(unittest.TestCase):
    def test_cuenta_ventana_y_excluye_estado_no_verificado(self):
        historico = [{"fecha": f"2026-01-{i:02}", "posicion_sesion": str(i), "emisora": "A", "serie": "*",
                      "estado_captura": "PPP_PUBLICADO_VERIFICADO", "ppp_bmv_mxn": "10"} for i in range(1, 22)]
        panel = [{"fecha": "2026-01-21", "posicion_sesion": "21", "emisora": "A", "serie": "*", "ppp_t": "10"}]
        self.assertEqual(auditar(historico, panel)["contadores"]["ventana_21_estados_verificados"], 1)
        historico[0]["estado_captura"] = "CONTINGENCIA_FUENTE_SECUNDARIA"
        resultado = auditar(historico, panel)
        self.assertEqual(resultado["contadores"]["ventana_21_con_faltante_o_no_verificado"], 1)
        self.assertEqual(resultado["ventanas_incompletas"][0]["estados"], {"CONTINGENCIA_FUENTE_SECUNDARIA": 1})

    def test_duplicado_no_es_ocultado(self):
        fila = {"fecha": "2026-01-01", "posicion_sesion": "1", "emisora": "A", "serie": "*"}
        with self.assertRaises(ValueError):
            auditar([fila, fila], [])


if __name__ == "__main__":
    unittest.main()
