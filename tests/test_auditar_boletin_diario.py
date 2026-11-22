import hashlib
import unittest
from scripts.auditar_boletin_diario import auditar


HTML = b"""<html><p>17 Nov 2026</p><table><tr><th>Emisora</th><th>Serie</th>
<th>\xc3\x9altimo</th><th>Anterior</th><th>PPP</th></tr>
<tr><td>AAA</td><td>B</td><td>11</td><td>9</td><td>10.00</td></tr></table></html>"""


def fila():
    return {"fecha": "2026-11-17", "emisora": "AAA", "serie": "B", "estado_captura": "PPP_PUBLICADO_VERIFICADO",
            "ppp_bmv_mxn": "10", "sha256_boletin": hashlib.sha256(HTML).hexdigest(),
            "url_fuente": "https://www.bmv.com.mx/docs-pub/rss/boletin20261117.html"}


class AuditoriaBoletinTest(unittest.TestCase):
    def test_coincidencia_y_cambios_no_son_validados(self):
        a = fila()
        self.assertEqual(auditar(HTML, [a], "2026-11-17")["resumen"]["COINCIDE_PPP_Y_HASH"], 1)
        self.assertEqual(auditar(HTML, [{**a, "ppp_bmv_mxn": "11"}], "2026-11-17")["resumen"]["PPP_DIFERENTE"], 1)
        self.assertEqual(auditar(HTML, [{**a, "sha256_boletin": "otro"}], "2026-11-17")["resumen"]["HASH_DIFERENTE"], 1)
        self.assertEqual(auditar(HTML, [{**a, "estado_captura": "CONTINGENCIA_FUENTE_SECUNDARIA"}], "2026-11-17")["resumen"]["NO_EVALUADO_NO_VERIFICADO"], 1)

    def test_rechaza_duplicados_y_fechas_distintas(self):
        with self.assertRaises(ValueError):
            auditar(HTML, [fila(), fila()], "2026-11-17")
        with self.assertRaises(ValueError):
            auditar(HTML, [{**fila(), "fecha": "2026-11-18"}], "2026-11-17")


if __name__ == "__main__":
    unittest.main()
