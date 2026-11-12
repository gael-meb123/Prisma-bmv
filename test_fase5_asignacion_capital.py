"""
Pruebas unitarias para la Fase 5: Política de asignación de capital y backtest neto de costos.
"""

from __future__ import annotations

import json
import unittest

import numpy as np
import pandas as pd

from asignacion_capital import (
    ARCHIVO_CURVA_EQUITY_CSV,
    ARCHIVO_REPORTE_FASE5_JSON,
    calcular_pesos_tramo_kelly,
    deflated_sharpe_ratio,
    shrinkage_ledoit_wolf_cov,
)
from monitor_prospectivo_segunda_generacion import hashes_protegidos_g2


class TestFase5AsignacionCapital(unittest.TestCase):
    """Valida Ledoit-Wolf, 1/4-Kelly con banda muerta y volatilidad objetivo, DSR y reporte Fase 5."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.reporte = json.loads(ARCHIVO_REPORTE_FASE5_JSON.read_text(encoding="utf-8"))
        cls.df_curva = pd.read_csv(ARCHIVO_CURVA_EQUITY_CSV)

    def test_ledoit_wolf_simetrica_definida_positiva(self) -> None:
        """Verifica que la covarianza con shrinkage de Ledoit-Wolf sea simétrica y definida positiva."""
        rng = np.random.default_rng(42)
        ret_mat = rng.normal(0.0, 0.025, size=(120, 5))
        sigma_lw, delta = shrinkage_ledoit_wolf_cov(ret_mat)
        self.assertEqual(sigma_lw.shape, (5, 5))
        self.assertTrue(0.05 <= delta <= 1.0)
        self.assertTrue(np.allclose(sigma_lw, sigma_lw.T, atol=1e-12))
        eigvals = np.linalg.eigvalsh(sigma_lw)
        self.assertTrue(np.all(eigvals > 0.0))

    def test_banda_muerta_tope_30pct_y_volatilidad_objetivo_10pct(self) -> None:
        """
        Comprueba que:
          1) Probabilidades dentro de la banda muerta |p_tilde - 0.5| < 0.03 reciban peso 0.
          2) Ninguna emisora supere el tope de 30% y la volatilidad ex-ante anualizada no exceda 10%.
        """
        sigma = np.diag([0.0009, 0.0009, 0.0009, 0.0009, 0.0009])
        e_abs = np.full(5, 0.027)

        # Caso 1: todas dentro de la banda muerta (p = 0.52 => |p_tilde - 0.5| = 0.02 < 0.03)
        res_inactivo = calcular_pesos_tramo_kelly(
            probs_raw=np.array([0.52, 0.51, 0.49, 0.50, 0.525]),
            lambda_cal=1.0,
            e_abs_r5=e_abs,
            sigma_lw_5d=sigma,
            banda_muerta=0.03,
        )
        self.assertTrue(np.all(res_inactivo["pesos"] == 0.0))
        self.assertAlmostEqual(res_inactivo["efectivo"], 1.0, places=9)

        # Caso 2: señales altas en las dos primeras emisoras y dentro de banda en las otras tres
        res_activo = calcular_pesos_tramo_kelly(
            probs_raw=np.array([0.65, 0.62, 0.51, 0.48, 0.52]),
            lambda_cal=1.0,
            e_abs_r5=e_abs,
            sigma_lw_5d=sigma,
            banda_muerta=0.03,
        )
        w = res_activo["pesos"]
        self.assertGreater(w[0], 0.0)
        self.assertGreater(w[1], 0.0)
        self.assertEqual(w[2], 0.0)
        self.assertEqual(w[3], 0.0)
        self.assertEqual(w[4], 0.0)
        self.assertTrue(np.all(w <= 0.30 + 1e-12))
        self.assertLessEqual(float(np.sum(w)), 1.0 + 1e-12)
        self.assertLessEqual(res_activo["vol_ex_ante_anual"], 0.10 + 1e-9)

    def test_deflated_sharpe_ratio_penaliza_multiples_intentos(self) -> None:
        """Verifica que el DSR disminuya al aumentar el número de variantes probadas M."""
        rng = np.random.default_rng(7)
        ret = rng.normal(0.0005, 0.008, size=350)
        dsr_2 = deflated_sharpe_ratio(ret, num_variantes_probadas=2)
        dsr_50 = deflated_sharpe_ratio(ret, num_variantes_probadas=50)
        self.assertAlmostEqual(dsr_2["sharpe_anual"], dsr_50["sharpe_anual"], places=6)
        self.assertGreater(dsr_2["dsr_prob"], dsr_50["dsr_prob"])

    def test_reporte_fase5_y_curva_equity_integridad(self) -> None:
        """Comprueba la estructura de reporte_fase5_portafolio.json y curva_equity_fase5_portafolio.csv."""
        estrategias = self.reporte["estrategias"]
        self.assertIn("G2_V4_F1_GAP_KELLY_250D", estrategias)
        self.assertIn("G2_V4_ADJ_KELLY_250D", estrategias)
        self.assertIn("BENCHMARK_EQUIPONDERADO_5_EMISORAS", estrategias)

        e_f1 = estrategias["G2_V4_F1_GAP_KELLY_250D"]
        self.assertGreater(e_f1["sharpe_neto_20bps"], 0.5)
        self.assertGreater(e_f1["hit_rate_operaciones_5d_pct"], 53.7)
        self.assertLessEqual(e_f1["volatilidad_anualizada_pct"], 10.0)

        self.assertGreater(len(self.df_curva), 250)
        self.assertTrue(self.reporte.get("integridad_archivos_protegidos_intacta"))
        self.assertGreaterEqual(len(hashes_protegidos_g2()), 5)


if __name__ == "__main__":
    unittest.main()
