import unittest
from scripts.auditar_procedencia_senales import auditar


class AuditoriaTest(unittest.TestCase):
    def test_contingencia_no_se_confunde_con_oficial_y_falta_no_es_cero(self):
        gold = [
            {"fecha_senal": "2026-11-19", "emisora": "A", "serie": "B", "sha256_boletin_base": "x"},
            {"fecha_senal": "2026-11-19", "emisora": "B", "serie": "*", "sha256_boletin_base": "x"},
        ]
        silver = [{"fecha": "2026-11-19", "emisora": "A", "serie": "",
                   "estado_captura": "CONTINGENCIA_FUENTE_SECUNDARIA", "sha256_boletin": "x"}]
        r = auditar(gold, silver)
        self.assertEqual(r["estados_por_fecha"]["2026-11-19"],
                         {"CONTINGENCIA_FUENTE_SECUNDARIA": 1, "SIN_CORRESPONDENCIA": 1})
        self.assertEqual(r["comprobaciones_por_fecha"]["2026-11-19"]["serie_distinta_o_ausente"], 1)
        self.assertEqual(r["comprobaciones_por_fecha"]["2026-11-19"]["hash_coincidente"], 1)

    def test_rechaza_ambiguo_como_coincidencia(self):
        gold = [{"fecha_senal": "2026-11-19", "emisora": "A"}]
        silver = [{"fecha": "2026-11-19", "emisora": "A"}, {"fecha": "2026-11-19", "emisora": "A"}]
        self.assertEqual(auditar(gold, silver)["estados_por_fecha"]["2026-11-19"], {"AMBIGUO": 1})


if __name__ == "__main__":
    unittest.main()
