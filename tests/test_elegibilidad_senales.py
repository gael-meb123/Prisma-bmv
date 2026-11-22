import unittest
from datetime import date, timedelta
from prisma.domain.elegibilidad_senales import evaluar_ventanas


class ElegibilidadTest(unittest.TestCase):
    def setUp(self):
        self.sesiones = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(21)]
        self.filas = [{"fecha": f, "emisora": e, "estado_captura": "PPP_PUBLICADO_VERIFICADO",
                       "serie": "B", "ppp_bmv_mxn": "10", "sha256_boletin": "a" * 64,
                       "url_fuente": f"https://www.bmv.com.mx/docs-pub/rss/boletin{f.replace('-', '')}.html"}
                      for e in ("A", "B") for f in self.sesiones]

    def test_ventanas_oficiales_con_dos_emisoras(self):
        r = evaluar_ventanas(self.filas, self.sesiones, ["A", "B"])
        self.assertTrue(r["A"]["apta_modelo_relativo"])
        self.assertTrue(r["B"]["apta_modelo_relativo"])

    def test_contingencia_bloquea_y_no_fabrica_media_de_panel(self):
        self.filas[0]["estado_captura"] = "CONTINGENCIA_FUENTE_SECUNDARIA"
        r = evaluar_ventanas(self.filas, self.sesiones, ["A", "B"])
        self.assertEqual(r["A"]["errores"][0]["motivo"], "FUENTE_NO_OFICIAL")
        self.assertFalse(r["A"]["apta_modelo_relativo"])
        self.assertTrue(r["B"]["ventana_apta"])
        self.assertFalse(r["B"]["apta_modelo_relativo"])

    def test_faltante_duplicado_precio_y_origen(self):
        self.filas[0]["ppp_bmv_mxn"] = "nan"
        self.filas[1]["url_fuente"] = "https://www.bmv.com.mx.ejemplo.org/"
        self.filas.append(dict(self.filas[2]))
        self.filas.pop(3)
        r = evaluar_ventanas(self.filas, self.sesiones, ["A", "B"])["A"]
        self.assertEqual({x["motivo"] for x in r["errores"]},
                         {"PRECIO_INVALIDO", "ORIGEN_NO_BMV", "AMBIGUA", "AUSENTE"})

    def test_rechaza_sesiones_ambiguas(self):
        with self.assertRaises(ValueError):
            evaluar_ventanas(self.filas, self.sesiones[:-1], ["A"])

    def test_rechaza_serie_ausente_cambio_de_serie_y_corte_fuente_distinto(self):
        self.filas[0]["serie"] = ""
        self.filas[1]["serie"] = "L"
        self.filas[2]["url_fuente"] = self.filas[3]["url_fuente"]
        r = evaluar_ventanas(self.filas, self.sesiones, ["A", "B"])["A"]
        self.assertEqual({x["motivo"] for x in r["errores"]},
                         {"SERIE_AUSENTE", "CAMBIO_DE_SERIE_NO_VALIDADO", "ORIGEN_NO_BMV"})


if __name__ == "__main__":
    unittest.main()
