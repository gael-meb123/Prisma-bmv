import unittest
import numpy as np
import pandas as pd
from scripts.auditar_formulas_panel import auditar


def panel():
    p = pd.DataFrame({"fecha": pd.date_range("2026-01-01", periods=23).strftime("%Y-%m-%d"),
                      "emisora": "A", "serie": "B", "posicion_sesion": range(23),
                      "ppp_ajustado": np.arange(10., 33.)})
    for n in (1, 5, 10, 20):
        p[f"ret_{n}_adj"] = p.ppp_ajustado / p.ppp_ajustado.shift(n) - 1
    for n in (5, 20):
        p[f"distancia_media_{n}_adj"] = p.ppp_ajustado / p.ppp_ajustado.rolling(n).mean() - 1
        p[f"volatilidad_{n}_adj"] = p.ret_1_adj.rolling(n).std(ddof=1)
    return p


class FormulasPanelTest(unittest.TestCase):
    def test_formulas_y_discrepancia(self):
        p = panel()
        r = auditar(p)
        self.assertTrue(all(x["difieren"] == 0 for x in r["resultados"].values()))
        self.assertEqual(r["resultados"]["ret_20_adj"]["comparables"], 3)
        p.loc[22, "ret_20_adj"] = 8
        self.assertEqual(auditar(p)["resultados"]["ret_20_adj"]["difieren"], 1)

    def test_no_usa_ventana_con_sesion_ausente(self):
        p = panel().drop(index=21)
        self.assertEqual(auditar(p)["resultados"]["ret_1_adj"]["comparables"], 20)
        with self.assertRaises(ValueError):
            auditar(pd.concat([p, p.iloc[:1]]))


if __name__ == "__main__":
    unittest.main()
