from __future__ import annotations

import json
import unittest

import numpy as np
import pandas as pd

from higiene_etiquetas_dividendos import (
    EVENTOS_CORP_PATH,
    PANEL_AJUSTADO_PATH,
    REPORTE_FASE1_PATH,
)
from metodologia_ppp import FEATURE_NAMES
from monitor_prospectivo_segunda_generacion import (
    PANEL_PATH,
    REGISTRO_G2_PATH,
    hashes_protegidos_g2,
)


class TestFase1HigieneEtiquetas(unittest.TestCase):
    def test_resolucion_exclusiva_ppp_verificado(self) -> None:
        df_reg = pd.read_csv(REGISTRO_G2_PATH, dtype=str)
        corte_28 = df_reg[df_reg["fecha_senal"] == "2026-10-28"]
        self.assertGreater(len(corte_28), 0)
        # Dado que 2026-11-05 tiene fuente CONTINGENCIA_FUENTE_SECUNDARIA, debe quedar en PENDIENTE_RECONCILIACION
        self.assertTrue((corte_28["estado_resolucion"] == "PENDIENTE_RECONCILIACION").all())
        self.assertTrue(corte_28["target_y_observado"].isna().all())

    def test_catalogo_eventos_corporativos_15_emisoras(self) -> None:
        self.assertTrue(EVENTOS_CORP_PATH.exists())
        df_ev = pd.read_csv(EVENTOS_CORP_PATH)
        self.assertEqual(
            list(df_ev.columns),
            ["emisora", "fecha_ex", "tipo", "monto_mxn", "factor", "fuente"],
        )
        self.assertEqual(df_ev["emisora"].nunique(), 15)
        self.assertTrue(set(df_ev["tipo"].unique()).issubset({"DIVIDENDO", "SPLIT"}))
        divs = df_ev[df_ev["tipo"] == "DIVIDENDO"]
        self.assertTrue(((divs["factor"] > 0.5) & (divs["factor"] < 1.0)).all())

    def test_panel_ajustado_invarianza_sin_evento_y_reporte_fase1(self) -> None:
        self.assertTrue(PANEL_AJUSTADO_PATH.exists())
        self.assertTrue(REPORTE_FASE1_PATH.exists())

        df_orig = pd.read_csv(PANEL_PATH)
        df_adj = pd.read_csv(PANEL_AJUSTADO_PATH)
        self.assertEqual(len(df_orig), len(df_adj))

        # El PPP original jamás se toca
        np.testing.assert_allclose(
            pd.to_numeric(df_orig["ppp_t"], errors="coerce").to_numpy(),
            pd.to_numeric(df_adj["ppp_t"], errors="coerce").to_numpy(),
            rtol=0.0,
            atol=1e-12,
            equal_nan=True,
        )

        # En ventanas de 5 días sin evento corporativo, target_y_ajustado es idéntico a target_y
        mask_sin_ev = (
            (df_adj["ventana_con_evento"] == 0)
            & df_adj["target_y"].notna()
            & df_adj["target_y_ajustado"].notna()
        )
        self.assertGreater(int(mask_sin_ev.sum()), 9000)
        self.assertTrue(
            (
                df_adj.loc[mask_sin_ev, "target_y"].astype(int)
                == df_adj.loc[mask_sin_ev, "target_y_ajustado"].astype(int)
            ).all()
        )

        # En ventanas de 21 sesiones sin evento corporativo, las 8 features ajustadas coinciden con las originales
        mask_21_limpia = (df_adj["ventana_21_con_evento"] == 0) & df_adj["ret_10"].notna()
        self.assertGreater(int(mask_21_limpia.sum()), 8000)
        for col in FEATURE_NAMES:
            diff = np.max(
                np.abs(
                    df_adj.loc[mask_21_limpia, col].to_numpy(dtype=float)
                    - df_adj.loc[mask_21_limpia, f"{col}_adj"].to_numpy(dtype=float)
                )
            )
            self.assertLess(float(diff), 1e-12)

        rep = json.loads(REPORTE_FASE1_PATH.read_text(encoding="utf-8"))
        self.assertTrue(rep["integridad_archivos_protegidos_intacta"])
        self.assertEqual(rep["auditoria_etiquetas_panel"]["cambios_etiqueta_en_ventana_sin_evento"], 0)
        self.assertGreater(rep["auditoria_etiquetas_panel"]["cambios_etiqueta_en_ventana_con_evento"], 0)
        for m in ["V1", "V2", "V3", "V4", "V5"]:
            self.assertIn(m, rep["test_15_emisoras"])
            self.assertIn(f"{m}_ADJ", rep["test_15_emisoras"])
            self.assertEqual(rep["test_15_emisoras"][m]["n"], 1557)
            self.assertEqual(rep["test_15_emisoras"][f"{m}_ADJ"]["n"], 1557)
            self.assertIn(m, rep["test_4_emisoras_foco"])
            self.assertIn(f"{m}_ADJ", rep["test_4_emisoras_foco"])
            self.assertEqual(rep["test_4_emisoras_foco"][m]["n"], 1142)
            self.assertEqual(rep["test_4_emisoras_foco"][f"{m}_ADJ"]["n"], 1142)


if __name__ == "__main__":
    unittest.main()
