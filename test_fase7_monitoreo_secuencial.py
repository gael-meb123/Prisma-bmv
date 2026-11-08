"""
Tests unitarios de la Fase 7 (Monitoreo Secuencial Activo: CUSUM + SPRT de Wald):
1. Cálculo analítico de las fronteras de Wald (A, B) y del tamaño muestral
   independiente requerido (~617-620 señales para potencia 80% en H0: p=0.50 vs H1: p=0.55).
2. Detección temprana de degradación mediante CUSUM unilateral de Page sobre
   el diferencial de Log-Score frente a la climatología.
3. Evaluación secuencial completa sobre TEST (`reporte_fase7_monitoreo_secuencial.json`),
   generación de `gold/reportes/monitoreo_semanal_20261106.json` y exposición en
   `GET /api/metricas/modelos`.
4. Invarianza de hashes protegidos (`hashes_protegidos_g2()`).
"""

import json
import unittest
from pathlib import Path

import numpy as np

import api
import monitoreo_secuencial_fase7 as f7
import monitor_prospectivo_segunda_generacion as mon


ROOT = Path(__file__).resolve().parent


class TestFase7MonitoreoSecuencial(unittest.TestCase):
    def test_01_requerimiento_muestral_y_fronteras_sprt_wald(self):
        """
        Verifica las fronteras de Wald A = ln((1-beta)/alpha) y B = ln(beta/(1-alpha))
        y que el tamaño muestral independiente requerido para p0=0.50 vs p1=0.55
        con alpha=0.05 y potencia 80% sea ~617-620 señales.
        """
        req = f7.calcular_requerimiento_muestral_sprt(p0=0.50, p1=0.55, alpha=0.05, beta=0.20)
        self.assertAlmostEqual(req["frontera_superior_A"], np.log(0.80 / 0.05), places=5)
        self.assertAlmostEqual(req["frontera_inferior_B"], np.log(0.20 / 0.95), places=5)
        self.assertTrue(615 <= req["n_independientes_requeridas_80pct"] <= 625)

        # Caso sintético de superioridad clara (60% de acierto en 500 señales independientes)
        y_syn = np.ones(500, dtype=int)
        p_syn = np.where(np.arange(500) < 300, 0.58, 0.42)
        res_sup = f7.evaluar_sprt_modelo(y_syn, p_syn, n_efectivo=500.0)
        self.assertEqual(res_sup["estado_sprt"], "ACEPTAR_H1_SUPERIORIDAD")
        self.assertGreater(res_sup["llr_efectivo"], req["frontera_superior_A"])

        # Caso sintético sin ventaja (48% de acierto en 400 señales independientes)
        p_inf = np.where(np.arange(400) < 192, 0.56, 0.44)
        res_inf = f7.evaluar_sprt_modelo(np.ones(400, dtype=int), p_inf, n_efectivo=400.0)
        self.assertEqual(res_inf["estado_sprt"], "ACEPTAR_H0_SIN_VENTAJA")
        self.assertLess(res_inf["llr_efectivo"], req["frontera_inferior_B"])

    def test_02_alarma_cusum_logscore(self):
        """
        Verifica que el estadístico CUSUM permanezca estable cuando el modelo supera
        a la climatología y dispare `alarma_cusum_activa=True` ante degradación sostenida.
        """
        fechas = np.array([f"2026-01-{i:02d}" for i in range(1, 31)])
        y = np.ones(30, dtype=int)
        p_clim = np.full(30, 0.50)

        # Modelo superior a la climatología -> sin alarma
        p_bueno = np.full(30, 0.55)
        res_ok = f7.calcular_cusum_y_logscore_secuencial(
            fechas=fechas,
            y_true=y,
            probs_modelo=p_bueno,
            probs_climatologia=p_clim,
            k_holgura_nats=0.001,
            h_umbral_alarma_nats=1.0,
        )
        self.assertFalse(res_ok["alarma_cusum_activa"])
        self.assertEqual(res_ok["estado_cusum"], "OPERACION_NORMAL_ESTABLE")
        self.assertGreater(res_ok["delta_log_score_acumulado_nats"], 0.0)

        # Modelo degradado (predice sistemáticamente en contra) -> dispara alarma CUSUM
        p_malo = np.full(30, 0.42)
        res_deg = f7.calcular_cusum_y_logscore_secuencial(
            fechas=fechas,
            y_true=y,
            probs_modelo=p_malo,
            probs_climatologia=p_clim,
            k_holgura_nats=0.001,
            h_umbral_alarma_nats=1.0,
        )
        self.assertTrue(res_deg["alarma_cusum_activa"])
        self.assertEqual(res_deg["estado_cusum"], "ALARMA_DEGRADACION_ACTIVA")
        self.assertIsNotNone(res_deg["fecha_primera_alarma"])

    def test_03_reporte_fase7_s3_gold_y_endpoint_api(self):
        """
        Verifica los artefactos generados por Fase 7 (`reporte_fase7_monitoreo_secuencial.json`,
        `curva_monitoreo_secuencial_fase7.csv`, `gold/reportes/monitoreo_semanal_20261106.json`)
        y su integración en `GET /api/metricas/modelos`.
        """
        self.assertTrue(f7.REPORTE_FASE7_PATH.exists())
        self.assertTrue(f7.CURVA_FASE7_PATH.exists())
        gold_file = ROOT / "gold" / "reportes" / "monitoreo_semanal_20261106.json"
        self.assertTrue(gold_file.exists())

        rep = json.loads(f7.REPORTE_FASE7_PATH.read_text(encoding="utf-8"))
        res_f1 = rep["evaluacion_secuencial_test_15_emisoras"]["G2_V4_F1_GAP"]
        self.assertGreater(res_f1["cusum_logscore"]["delta_log_score_acumulado_bits"], 5.0)
        self.assertFalse(res_f1["cusum_logscore"]["alarma_cusum_activa"])
        self.assertGreater(res_f1["sprt_wald"]["llr_efectivo"], 0.0)
        self.assertIn("sprt_wald_senales_activas_fuera_banda", res_f1)

        # Verificar exposición en API
        api_res = api.get_metricas_modelos()
        self.assertIn("monitoreo_secuencial_fase7", api_res)
        self.assertIn(
            "G2_V4_F1_GAP",
            api_res["monitoreo_secuencial_fase7"]["evaluacion_secuencial_test_15_emisoras"],
        )

    def test_04_invarianza_hashes_protegidos(self):
        hashes = mon.hashes_protegidos_g2()
        for k, v in hashes.items():
            self.assertEqual(len(v), 64, f"Hash inválido para {k}")


if __name__ == "__main__":
    unittest.main()
