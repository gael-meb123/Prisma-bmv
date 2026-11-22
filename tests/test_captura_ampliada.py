import tempfile
import unittest
from datetime import date
from pathlib import Path

from prisma.data.captura_ampliada import extraer, guardar
from prisma.domain.catalogo_ipc import catalogo_naftrac_20261117


CORTE = date(2026, 11, 17)
URL = "https://www.bmv.com.mx/docs-pub/rss/boletin20261117.html"
CABECERA = "<tr><th>Emisora</th><th>Serie</th><th>Último</th><th>Anterior</th><th>PPP</th></tr>"


def html_filas(*filas):
    contenido = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in fila) + "</tr>" for fila in filas)
    return f"<html><body>17 Nov 2026<table>{CABECERA}{contenido}</table></body></html>".encode()


class CapturaAmpliadaTest(unittest.TestCase):
    def setUp(self):
        self.catalogo = catalogo_naftrac_20261117()

    def capturar(self, raw):
        return extraer(raw, CORTE, self.catalogo, URL)

    def test_coincidencia_exacta_y_huecos_sin_imputacion(self):
        r = self.capturar(html_filas(
            ("GMEXICO", "B", "213.50", "220.49", "212.83"),
            ("GCARSO", "A1", "173.54", "170.51", "174.11"),
        ))
        self.assertEqual(len(r["filas"]), 35)
        por = {x["emisora_propuesta"]: x for x in r["filas"]}
        self.assertEqual(por["GMEXICO"]["ppp_bmv_mxn"], 212.83)
        self.assertEqual(por["GCARSO"]["estado_captura"], "PPP_OBSERVADO_MAPEO_PROVISIONAL")
        self.assertEqual(por["GCARSO"]["estado_mapeo"], "PROPUESTO_PENDIENTE_VERIFICACION")
        self.assertIsNone(por["WALMEX"]["ppp_bmv_mxn"])
        self.assertEqual(por["WALMEX"]["estado_captura"], "NO_ENCONTRADO_EN_TABLAS")
        self.assertEqual(len(r["sha256_boletin"]), 64)

    def test_vacio_o_conflicto_bloquean_sin_desplazar_celdas(self):
        r = self.capturar(html_filas(
            ("GMEXICO", "B", "213.50", "220.49", ""),
            ("WALMEX", "*", "55", "54", "55"),
            ("WALMEX", "*", "55", "54", "56"),
        ))
        por = {x["emisora_propuesta"]: x for x in r["filas"]}
        self.assertEqual(por["GMEXICO"]["estado_captura"], "FILA_INVALIDA_REQUIERE_REVISION")
        self.assertEqual(por["WALMEX"]["estado_captura"], "CONFLICTO_ENTRE_FILAS")
        self.assertIsNone(por["WALMEX"]["ppp_bmv_mxn"])

    def test_repeticion_identica_y_entidades_html(self):
        r = self.capturar(html_filas(
            ("PE&amp;OLES", "*", "10", "9", "9.5"),
            ("PE&amp;OLES", "*", "10", "9", "9.5"),
        ))
        fila = next(x for x in r["filas"] if x["emisora_propuesta"] == "PE&OLES")
        self.assertEqual(fila["apariciones"], 2)
        self.assertEqual(fila["ppp_bmv_mxn"], 9.5)

    def test_rechaza_fecha_distinta_sin_tablas_y_fecha_fuera_de_corte(self):
        raw = html_filas(("GMEXICO", "B", "10", "9", "9.5"))
        with self.assertRaises(ValueError):
            self.capturar(raw.replace(b"17 Nov 2026", b"16 Nov 2026"))
        with self.assertRaises(ValueError):
            self.capturar(b"<html>17 Nov 2026</html>")
        with self.assertRaises(ValueError):
            extraer(raw, date(2026, 11, 18), self.catalogo, URL)

    def test_no_sobrescribe_directorio(self):
        raw = html_filas(("GMEXICO", "B", "10", "9", "9.5"))
        r = self.capturar(raw)
        with tempfile.TemporaryDirectory() as temp:
            destino = Path(temp) / "captura"
            with self.assertRaises(ValueError):
                guardar(r, raw + b"alterado", destino)
            self.assertFalse(destino.exists())
            guardar(r, raw, destino)
            self.assertEqual((destino / "boletin.html").read_bytes(), raw)
            self.assertTrue((destino / "precios_provisionales.csv").exists())
            with self.assertRaises(FileExistsError):
                guardar(r, raw, destino)


if __name__ == "__main__":
    unittest.main()
