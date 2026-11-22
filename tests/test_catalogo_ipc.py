import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from prisma.domain.bmv_core import EMISORAS_15
from prisma.domain.catalogo_ipc import catalogo_naftrac_20261117, cargar_catalogo, DIRECTORIO


CORTE = date(2026, 11, 17)


class CatalogoIpcTest(unittest.TestCase):
    def setUp(self):
        self.catalogo = catalogo_naftrac_20261117()

    def test_version_fuente_y_particion_de_candidatos(self):
        c = self.catalogo
        self.assertEqual(c.version, "naftrac-2026-11-17-v1")
        self.assertEqual(c.fecha_corte, CORTE)
        self.assertIn("blackrock.com", c.fuente_url)
        actuales = {(x.emisora, x.serie) for x in c.componentes if x.origen == "ACTUAL_15"}
        nuevos = [x for x in c.componentes if x.origen == "CANDIDATO_20"]
        self.assertEqual(actuales, {(e, s) for e, s, _, _ in EMISORAS_15})
        self.assertEqual(len(nuevos), 20)
        self.assertEqual(len(c.componentes), 35)
        self.assertTrue(all(x.estado_composicion == "PROVISIONAL_NO_OFICIAL" for x in c.componentes))
        self.assertTrue(all(x.estado_mapeo == "PROPUESTO_PENDIENTE_VERIFICACION" for x in c.componentes))
        self.assertTrue(all(x.yahoo is None for x in nuevos))

    def test_alias_son_explicitos_por_fuente_y_preservan_puntuacion(self):
        c = self.catalogo
        livepol = c.resolver("blackrock", " livepolc.1 ", CORTE)
        self.assertEqual((livepol.emisora, livepol.serie), ("LIVEPOL", "C-1"))
        self.assertEqual(c.resolver("yahoo", "LIVEPOLC-1.MX", CORTE), livepol)
        self.assertIsNone(c.resolver("blackrock", "LIVEPOLC-1", CORTE))
        self.assertIsNone(c.resolver("yahoo", "KOFUBL.MX", CORTE))
        self.assertEqual(c.buscar_bmv("r", "a", CORTE).blackrock, "RA")
        self.assertIsNone(c.buscar_bmv("R", "*", CORTE))
        with self.assertRaises(ValueError):
            c.resolver("bmv", "RA", CORTE)

    def test_fuera_del_corte_se_rechaza(self):
        for fecha in (date(2026, 11, 16), date(2026, 11, 18)):
            with self.assertRaises(ValueError):
                self.catalogo.en_corte(fecha)
            with self.assertRaises(ValueError):
                self.catalogo.resolver("blackrock", "RA", fecha)

    def test_rechaza_duplicados_y_estado_oficial_inventado(self):
        original = json.loads((DIRECTORIO / "naftrac_2026-11-17_v1.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            ruta = Path(temp) / "catalogo.json"
            copia = json.loads(json.dumps(original))
            copia["componentes"][1]["blackrock"] = copia["componentes"][0]["blackrock"]
            ruta.write_text(json.dumps(copia), encoding="utf-8")
            with self.assertRaises(ValueError):
                cargar_catalogo(ruta)
            copia = json.loads(json.dumps(original))
            copia["estado_composicion"] = "OFICIAL"
            ruta.write_text(json.dumps(copia), encoding="utf-8")
            with self.assertRaises(ValueError):
                cargar_catalogo(ruta)


if __name__ == "__main__":
    unittest.main()
