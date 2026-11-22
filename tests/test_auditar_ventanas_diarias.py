import csv
import tempfile
import unittest
from pathlib import Path
from scripts.auditar_ventanas_diarias import auditar, sesiones_hasta


class VentanasDiariasTest(unittest.TestCase):
    def test_calendario_y_archivos_ausentes(self):
        sesiones = sesiones_hasta("2026-11-19")
        self.assertEqual(len(sesiones), 21)
        self.assertEqual(sesiones[-1], "2026-11-19")
        self.assertNotIn("2026-11-16", sesiones)
        with tempfile.TemporaryDirectory() as tmp:
            r = auditar(Path(tmp), "2026-11-19", ["WALMEX", "AMX"])
        self.assertEqual(len(r["emisoras"]["WALMEX"]["errores"]), 21)
        self.assertFalse(r["emisoras"]["WALMEX"]["apta_modelo_relativo"])

    def test_rechaza_fechas_ajenas_en_archivo_diario(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "2026" / "11" / "ppp_15_emisoras_20261119.csv"
            p.parent.mkdir(parents=True)
            cols = ["fecha", "emisora", "serie", "estado_captura", "ppp_bmv_mxn", "sha256_boletin", "url_fuente"]
            with p.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
                w.writerow(dict.fromkeys(cols, "otro"))
            with self.assertRaises(ValueError):
                auditar(Path(tmp), "2026-11-19", ["WALMEX"])


if __name__ == "__main__":
    unittest.main()
