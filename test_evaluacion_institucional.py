from __future__ import annotations

import json
import unittest

import numpy as np
import pandas as pd

from evaluacion_institucional import (
    REPORTE_EVAL_INSTITUCIONAL_PATH,
    block_bootstrap_diff,
    brier_skill_score,
    curva_calibracion,
    descomposicion_murphy,
    diebold_mariano,
    information_gain_bits,
    intervalo_wilson,
    n_efectivo,
    rank_ic_diario,
)


class TestEvaluacionInstitucional(unittest.TestCase):
    def test_intervalo_wilson_resultados_conocidos(self) -> None:
        # 4/4 aciertos al 95%: intervalo de Wilson exacto ~ [0.5101, 1.0]
        lo4, hi4 = intervalo_wilson(4, 4, alpha=0.05)
        self.assertAlmostEqual(lo4, 0.5101, places=3)
        self.assertAlmostEqual(hi4, 1.0, places=6)

        # 50/100 al 95%: simétrico alrededor de 0.5
        lo50, hi50 = intervalo_wilson(50, 100, alpha=0.05)
        self.assertAlmostEqual(lo50 + hi50, 1.0, places=6)
        self.assertAlmostEqual(lo50, 0.4038, places=3)

    def test_bss_murphy_e_information_gain_sinteticos(self) -> None:
        y = np.array([0, 0, 1, 1], dtype=int)
        p_perf = np.array([0.0, 0.0, 1.0, 1.0], dtype=float)
        p_mitad = np.array([0.5, 0.5, 0.5, 0.5], dtype=float)

        self.assertAlmostEqual(brier_skill_score(p_perf, y, 0.5), 1.0, places=9)
        self.assertAlmostEqual(brier_skill_score(p_mitad, y, 0.5), 0.0, places=9)

        # Para predicción perfectamente calibrada en 2 bins, REL = 0, RES = UNC = 0.25, Brier = 0
        m = descomposicion_murphy(p_perf, y, bins=2)
        self.assertAlmostEqual(m["confiabilidad"], 0.0, places=9)
        self.assertAlmostEqual(m["resolucion"], 0.25, places=9)
        self.assertAlmostEqual(m["incertidumbre"], 0.25, places=9)
        self.assertAlmostEqual(m["brier_murphy"], 0.0, places=9)

        # Ganancia de información de predicción casi determinista frente a moneda justa = ~1 bit
        ig = information_gain_bits(np.array([1e-9, 1e-9, 1.0 - 1e-9, 1.0 - 1e-9]), y, 0.5)
        self.assertAlmostEqual(ig, 1.0, places=5)
        self.assertAlmostEqual(information_gain_bits(p_mitad, y, 0.5), 0.0, places=9)

    def test_curva_calibracion_lambda_conocida(self) -> None:
        rng = np.random.default_rng(123)
        z = rng.normal(0.0, 0.8, size=4000)
        p_true = 1.0 / (1.0 + np.exp(-z))
        y = rng.binomial(1, p_true)

        # Caso 1: probabilidades bien calibradas -> lambda ~ 1.0, ECE bajo
        cal_ok = curva_calibracion(p_true, y, bins=10)
        self.assertGreater(cal_ok["lambda_calibracion"], 0.85)
        self.assertLess(cal_ok["lambda_calibracion"], 1.15)
        self.assertLess(cal_ok["ece"], 0.04)

        # Caso 2: modelo sobreconfiado con logit duplicado (2*z) -> lambda real ~ 0.5
        p_sobreconf = 1.0 / (1.0 + np.exp(-2.0 * z))
        cal_over = curva_calibracion(p_sobreconf, y, bins=10)
        self.assertAlmostEqual(cal_over["lambda_calibracion"], 0.5 * cal_ok["lambda_calibracion"], delta=0.08)

    def test_rank_ic_diebold_mariano_bootstrap_y_n_efectivo(self) -> None:
        # Rank IC monotónico perfecto en 10 fechas -> IC = 1.0
        filas = []
        for d in range(10):
            for i, em in enumerate(["A", "B", "C", "D", "E"]):
                filas.append(
                    {
                        "fecha": f"2026-01-{d+1:02d}",
                        "emisora": em,
                        "prob": 0.40 + 0.04 * i,
                        "ret_h5": -0.02 + 0.01 * i,
                    }
                )
        df_ic = pd.DataFrame(filas)
        res_ic = rank_ic_diario(df_ic)
        self.assertEqual(res_ic["n_fechas_ic"], 10)
        self.assertAlmostEqual(res_ic["ic_medio"], 1.0, places=9)

        # Diebold-Mariano y Block Bootstrap cuando pérdida A es sistemáticamente menor que B
        rng = np.random.default_rng(7)
        loss_b = rng.uniform(0.20, 0.30, size=300)
        loss_a = loss_b - 0.03 + rng.normal(0.0, 0.005, size=300)
        dm = diebold_mariano(loss_a, loss_b, lag=4)
        self.assertLess(dm["diff_media"], -0.025)
        self.assertLess(dm["dm_stat"], -5.0)
        self.assertLess(dm["p_valor_bilateral"], 1e-5)

        boot = block_bootstrap_diff(loss_a, loss_b, bloque=5, B=1000, seed=42)
        self.assertLess(boot["ic_superior"], -0.02)
        self.assertEqual(boot["prob_a_menor_perdida"], 1.0)

        # Serie con alta autocorrelación por bloques de 5 tiene N_efectivo < N
        y_auto = np.repeat(rng.integers(0, 2, size=100), 5)
        neff = n_efectivo(y_auto, lag=4)
        self.assertLess(neff, 0.5 * len(y_auto))

    def test_reporte_evaluacion_institucional_completo(self) -> None:
        self.assertTrue(REPORTE_EVAL_INSTITUCIONAL_PATH.exists())
        rep = json.loads(REPORTE_EVAL_INSTITUCIONAL_PATH.read_text(encoding="utf-8"))
        self.assertTrue(rep["integridad_archivos_protegidos_intacta"])
        self.assertIn("lambda_calibracion_v4", rep)
        self.assertIsNotNone(rep["lambda_calibracion_v4"]["train_cv_purgada_sin_fuga_orig"]["lambda_calibracion_cox"])
        self.assertIsNotNone(rep["lambda_calibracion_v4"]["test_15_emisoras_orig"])

        for bloque in [
            "test_15_emisoras",
            "test_4_emisoras_foco",
            "test_15_emisoras_ajustado_fase1",
            "test_4_emisoras_foco_ajustado_fase1",
        ]:
            self.assertIn(bloque, rep)
            for base_k in ["CLIMATOLOGIA", "SIEMPRE_SUBIDA", "MOMENTUM_INGENUO"]:
                self.assertIn(base_k, rep[bloque])


if __name__ == "__main__":
    unittest.main()
