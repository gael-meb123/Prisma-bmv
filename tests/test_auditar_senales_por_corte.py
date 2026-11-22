import unittest
from scripts.auditar_senales_por_corte import auditar


class AuditoriaCorteTest(unittest.TestCase):
    def test_no_confunde_serie_contingencia_o_hash(self):
        gold = [{"fecha_senal": "2026-11-19", "emisora": "A", "serie": "B",
                 "ppp_base_t": "42", "sha256_boletin_base": "x"},
                {"fecha_senal": "2026-11-19", "emisora": "A", "serie": "C",
                 "ppp_base_t": "42", "sha256_boletin_base": "x"}]
        silver = [{"fecha": "2026-11-19", "emisora": "A", "serie": "B",
                   "ppp_bmv_mxn": "42.00", "estado_captura": "CONTINGENCIA_FUENTE_SECUNDARIA",
                   "sha256_boletin": "otro"}]
        c = auditar(gold, silver, "2026-11-19")["contadores"]
        self.assertEqual(c["clave_ausente"], 1)
        self.assertEqual(c["estado:CONTINGENCIA_FUENTE_SECUNDARIA"], 1)
        self.assertEqual(c["hash_distinto_o_ausente"], 1)
        self.assertEqual(c["precio_igual"], 1)

    def test_no_silencia_duplicados_ni_fechas_ajenas(self):
        gold = [{"fecha_senal": "2026-11-19", "emisora": "A", "serie": "B"}]
        fila = {"fecha": "2026-11-19", "emisora": "A", "serie": "B"}
        self.assertEqual(auditar(gold, [fila, fila], "2026-11-19")["contadores"]["clave_ambigua"], 1)
        with self.assertRaises(ValueError):
            auditar(gold, [{**fila, "fecha": "2026-11-17"}], "2026-11-19")


if __name__ == "__main__":
    unittest.main()
