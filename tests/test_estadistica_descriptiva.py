import unittest

import numpy as np
import pandas as pd

from prisma.data.estadistica_descriptiva import (
    VARIABLES_PANEL, _correlaciones, generar_reporte, resumen,
)
from prisma.domain.bmv_core import ESTADO_PUBLICADO


def datos():
    h = pd.DataFrame([
        {"fecha": f"2025-01-0{i}", "emisora": "AAA", "serie": "A",
         "sector_economico": "Sector", "estado_captura": estado,
         "ppp_bmv_mxn": precio, "variacion_ppp_vs_anterior_pct": variacion}
        for i, estado, precio, variacion in [
            (1, ESTADO_PUBLICADO, 10, 1), (2, ESTADO_PUBLICADO, 12, -2),
            (3, "CONTINGENCIA", 20, 5), (4, ESTADO_PUBLICADO, None, 0)]
    ])
    p = h[["fecha", "emisora", "serie", "sector_economico"]].copy()
    for variable in VARIABLES_PANEL:
        p[variable] = [1., 2., 3., np.nan]
        p[variable + "_adj"] = [2., 4., 6., np.nan]
    return h, p


class EstadisticaDescriptivaTest(unittest.TestCase):
    def test_resumen_y_muestra_pequena(self):
        r = resumen(pd.Series([1, 2, 3, 4, None, np.inf]))
        self.assertEqual((r["n_valido"], r["faltantes"]), (4, 2))
        self.assertEqual(r["media"], 2.5)
        self.assertEqual(r["q1"], 1.75)
        self.assertAlmostEqual(r["desviacion_estandar_muestral"], np.std([1, 2, 3, 4], ddof=1))
        self.assertIsNone(resumen(pd.Series([1]))["exceso_curtosis"])

    def test_cobertura_exclusion_y_frecuencias(self):
        h, p = datos()
        r = generar_reporte(h, p)
        self.assertEqual(r["cobertura_historico"]["registros"], 4)
        self.assertEqual(r["cobertura_panel"]["estados"]["CONTINGENCIA"], 1)
        tabla = r["estadisticas_historico_verificado"][0]
        self.assertEqual((tabla["n_total"], tabla["n_valido"]), (3, 2))
        totales = [x for x in r["frecuencias_direccion"] if x["agrupacion"] == "total"]
        self.assertEqual([x["n"] for x in totales], [1, 1, 1])
        self.assertEqual(sum(x["n"] for x in r["distribucion_variacion_pct"]["histograma"]), 3)
        self.assertEqual(len(r["serie_historica_verificada"]), 3)

    def test_filtros_y_panel_ajustado(self):
        h, p = datos()
        r = generar_reporte(h, p, desde="2025-01-02", hasta="2025-01-02", ajustado=False)
        self.assertEqual(r["cobertura_panel"]["registros"], 1)
        self.assertEqual(r["estadisticas_panel_verificado"][0]["media"], 2)
        vacio = generar_reporte(h, p, emisora="NO_EXISTE")
        self.assertEqual(vacio["cobertura_historico"]["registros"], 0)
        self.assertEqual(vacio["distribucion_variacion_pct"]["histograma"], [])
        with self.assertRaises(ValueError):
            generar_reporte(h, p, desde="2025-02-01", hasta="2025-01-01")

    def test_pares_completos_y_constantes(self):
        df = pd.DataFrame({"a": [1., 2., None, 4.], "b": [1., 2., 3., None], "c": [1.] * 4})
        r = _correlaciones(df, ["a", "b", "c"])
        ab = next(x for x in r if x["variable_1"] == "a" and x["variable_2"] == "b")
        self.assertEqual(ab["n_pares"], 2)
        self.assertAlmostEqual(ab["pearson"], 1)
        self.assertAlmostEqual(ab["spearman"], 1)
        ac = next(x for x in r if x["variable_1"] == "a" and x["variable_2"] == "c")
        self.assertIsNone(ac["pearson"])

    def test_duplicados_y_estado_ausente(self):
        h, p = datos()
        with self.assertRaises(ValueError):
            generar_reporte(pd.concat([h, h.iloc[:1]]), p)
        r = generar_reporte(h.iloc[:3], p)
        self.assertEqual(r["cobertura_panel"]["estados"]["SIN_ESTADO"], 1)
        self.assertEqual(len(r["serie_historica_verificada"]), 2)


if __name__ == "__main__":
    unittest.main()
