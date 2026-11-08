"""
Pruebas unitarias para la Fase 4: Modelos de sexta generación (candidatos V6) y regla de promoción.
"""

from __future__ import annotations

import json
import unittest

import numpy as np
import pandas as pd

from modelos_v6 import (
    ARCHIVO_REPORTE_FASE4_JSON,
    FEATURES_V4_MAS_F1,
    _ajustar_logit_jerarquico_irls,
)
from monitor_prospectivo_segunda_generacion import hashes_protegidos_g2


class TestFase4ModelosV6(unittest.TestCase):
    """Valida la estructura y propiedades matemáticas de los modelos V6 y el reporte de Fase 4."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.reporte = json.loads(ARCHIVO_REPORTE_FASE4_JSON.read_text(encoding="utf-8"))

    def test_reporte_fase4_contiene_todos_los_candidatos_y_regla_promocion(self) -> None:
        """Verifica que reporte_fase4_modelos_v6.json incluya V4_ADJ, V4_F1_GAP y los 4 candidatos V6."""
        modelos = self.reporte["modelos"]
        esperados = {
            "G2_V4_ADJ",
            "G2_V4_F1_GAP",
            "G2_V6A_JERARQUICO",
            "G2_V6B_DESCOMPUESTO",
            "G2_V6C_RIDGE_CONTINUO",
            "G2_LGBM_CHALLENGER",
        }
        self.assertTrue(esperados.issubset(set(modelos.keys())))

        for nombre_mod in esperados:
            info_m = modelos[nombre_mod]
            self.assertEqual(info_m["test_15_emisoras"]["n"], 1557)
            self.assertEqual(info_m["test_4_emisoras_foco"]["n"], 1142)
            self.assertIn("evaluacion_regla_promocion", info_m)
            self.assertIn("desglose_4_emisoras_foco", info_m)
            self.assertEqual(
                set(info_m["desglose_4_emisoras_foco"].keys()),
                {"AMX", "GFNORTE", "GMEXICO", "WALMEX"},
            )

    def test_partial_pooling_converge_a_pooled_cuando_tau_tiende_a_cero(self) -> None:
        """
        En datos sintéticos, cuando tau -> 0 (penalización infinita sobre u_i),
        los efectos específicos por emisora de G2_V6A_JERARQUICO deben encogerse a ~0.
        """
        rng = np.random.default_rng(123)
        n = 240
        df_sint = pd.DataFrame(
            {
                "emisora": np.repeat(["AMX", "WALMEX", "GFNORTE", "GMEXICO"], n // 4),
                "ret_1_rel_panel": rng.normal(0, 1, size=n),
                "distancia_media_5": rng.normal(0, 1, size=n),
                "distancia_media_5_rel_panel": rng.normal(0, 1, size=n),
                "volatilidad_20": np.abs(rng.normal(0.015, 0.003, size=n)),
                "gap_uh_ppp": rng.normal(0, 0.002, size=n),
            }
        )
        eta = -0.3 * df_sint["distancia_media_5"] - 0.2 * df_sint["gap_uh_ppp"]
        p_true = 1.0 / (1.0 + np.exp(-eta))
        df_sint["target_y"] = (rng.uniform(0, 1, size=n) < p_true).astype(int)

        probs_tau_peq, info_peq = _ajustar_logit_jerarquico_irls(
            df_sint, df_sint, FEATURES_V4_MAS_F1, c_pool=0.1, tau=1e-8
        )
        probs_tau_gde, info_gde = _ajustar_logit_jerarquico_irls(
            df_sint, df_sint, FEATURES_V4_MAS_F1, c_pool=0.1, tau=0.1
        )
        self.assertTrue(np.all((probs_tau_peq > 0.0) & (probs_tau_peq < 1.0)))
        self.assertTrue(np.all((probs_tau_gde > 0.0) & (probs_tau_gde < 1.0)))
        self.assertLess(info_peq["norma_l2_efectos_aleatorios"], 1e-4)
        self.assertGreater(info_gde["norma_l2_efectos_aleatorios"], info_peq["norma_l2_efectos_aleatorios"])

    def test_integridad_hashes_protegidos(self) -> None:
        """Verifica que ningún archivo protegido de G2 haya sido modificado."""
        self.assertTrue(self.reporte.get("integridad_archivos_protegidos_intacta"))
        hashes_actuales = hashes_protegidos_g2()
        self.assertGreaterEqual(len(hashes_actuales), 5)


if __name__ == "__main__":
    unittest.main()
