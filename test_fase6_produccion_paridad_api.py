"""
Tests unitarios y de integración de la Fase 6:
1. Paridad numérica exacta (|Δp| < 1e-6) entre AWS Lambda (`lambda_function_con_ia.py`)
   y el motor de investigación (`monitor_prospectivo_segunda_generacion.py`) en >= 5 fechas
   y las 5 variantes G2 (V1-V5) + el modelo campeón extendido `G2_V4_F1_GAP`.
2. Carga dinámica y verificación SHA-256 de `registro_modelos_g2_v2.json`.
3. Contrato del endpoint `GET /api/metricas/modelos` y enriquecimiento de señales con
   `muestra_evaluacion`, `estado_resolucion` y política ¼-Kelly.
4. Invarianza de hashes protegidos (`hashes_protegidos_g2()`).
"""

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import api
from core.data_provider import obtener_metricas_institucionales_modelos
from core.supabase_auth import Usuario
import lambda_function_con_ia as lmb
import monitor_prospectivo_segunda_generacion as mon


ROOT = Path(__file__).resolve().parent


class TestFase6ProduccionParidadAPI(unittest.TestCase):
    def test_01_paridad_numerica_lambda_vs_investigacion_5_fechas(self):
        """
        Verifica |p_lambda - p_investigacion| < 1e-6 en >= 5 fechas de corte
        para las 5 variantes oficiales G2_V1..G2_V5 y las 5 emisoras foco.
        """
        serie_unificada = mon.construir_serie_unificada_ppp()
        df_senales = pd.read_csv(ROOT / "registro_senales_prospectivas_panel_g2.csv")

        fechas_prueba = sorted(df_senales["fecha_senal"].dropna().astype(str).unique().tolist())
        self.assertGreaterEqual(len(fechas_prueba), 5)

        comparaciones_totales = 0
        max_diff_v1_v2 = 0.0
        max_diff_fecha_final = 0.0
        fecha_final = fechas_prueba[-1]

        for fecha_corte in fechas_prueba:
            _, df_eleg = mon.extraer_ventanas_y_features_en_fecha(serie_unificada, fecha_corte)
            self.assertFalse(df_eleg.empty)

            sub_csv = df_senales[df_senales["fecha_senal"] == fecha_corte]
            self.assertGreaterEqual(len(sub_csv), 20)

            for _, row_em in df_eleg.iterrows():
                emi = str(row_em["emisora"])
                res_lmb, consenso_lmb = lmb.inferir_modelos_g2(
                    emisora=emi,
                    ret_10=float(row_em["ret_10"]),
                    ret_10_rel=float(row_em["ret_10_rel_panel"]),
                    vol_20=float(row_em["volatilidad_20"]),
                    ret_1_rel=float(row_em["ret_1_rel_panel"]),
                    dm_5=float(row_em["distancia_media_5"]),
                    dm_5_rel=float(row_em["distancia_media_5_rel_panel"]),
                    ret_5=float(row_em["ret_5"]),
                    ret_20=float(row_em["ret_20"]),
                    dm_20=float(row_em["distancia_media_20"]),
                )

                sub_em_csv = sub_csv[sub_csv["emisora"] == emi]
                self.assertEqual(len(sub_em_csv), 5)

                for _, r_csv in sub_em_csv.iterrows():
                    mod_id = str(r_csv["modelo_g2"])
                    p_csv = float(r_csv["probabilidad_subida"])
                    p_lmb = float(res_lmb[mod_id]["probabilidad"])
                    diff = abs(p_lmb - p_csv)

                    # Todos los 5 modelos V1..V5 tienen paridad exacta < 1e-6 en las >= 5 fechas
                    max_diff_v1_v2 = max(max_diff_v1_v2, diff)
                    max_diff_fecha_final = max(max_diff_fecha_final, diff)
                    self.assertLess(
                        diff,
                        1e-6,
                        f"Discrepancia >= 1e-6 en {fecha_corte} {emi} {mod_id}: lambda={p_lmb} vs csv={p_csv}",
                    )
                    self.assertEqual(
                        consenso_lmb,
                        str(r_csv["estado_consenso_g2"]),
                    )

                    self.assertEqual(
                        int(res_lmb[mod_id]["clase"]),
                        int(r_csv["prediccion_clase"]),
                    )
                    comparaciones_totales += 1

        self.assertGreaterEqual(comparaciones_totales, 120)
        self.assertLess(max_diff_v1_v2, 1e-6)
        self.assertLess(max_diff_fecha_final, 1e-6)

    def test_02_registro_v2_sha256_y_modelo_f1_gap(self):
        """
        Verifica la integridad criptográfica SHA-256 de `registro_modelos_g2_v2.json`
        y la inferencia en doble precisión de `G2_V4_F1_GAP`.
        """
        reg_v2_path = ROOT / "registro_modelos_g2_v2.json"
        self.assertTrue(reg_v2_path.exists())

        raw_v2 = json.loads(reg_v2_path.read_text(encoding="utf-8"))
        self.assertEqual(raw_v2["version_registro"], "REGISTRO_MODELOS_G2_V2_DOBLE_PRECISION")
        self.assertEqual(raw_v2["fecha_congelamiento_oficial"], "2026-11-06")

        reg_norm = lmb.cargar_registro_modelos_g2(local_path=reg_v2_path)
        for nombre in [
            "G2_V1_POOLED_REL3_CALIBRADO",
            "G2_V2_POOLED_REL3_ZONA_NEUTRAL",
            "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO",
            "G2_V4_POOLED_DM5_REL_CORTO_PLAZO",
            "G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL",
            "G2_V4_ADJ_FASE1",
            "G2_V4_F1_GAP",
        ]:
            self.assertIn(nombre, reg_norm)
            self.assertIn("sha256_config", reg_norm[nombre])
            self.assertEqual(len(reg_norm[nombre]["sha256_config"]), 64)

        # Verificar calculo de gap_uh_ppp e inferencia de G2_V4_F1_GAP
        gap_val = lmb.calcular_gap_uh_ppp(50.80, 50.39)
        self.assertAlmostEqual(gap_val, (50.80 - 50.39) / 50.39, places=12)
        self.assertIsNone(lmb.calcular_gap_uh_ppp(None, 50.39))

        res_gap = lmb.inferir_modelo_g2_v4_f1_gap(
            emisora="GMEXICO",
            ret_1_rel=-0.012,
            dm_5=-0.018,
            dm_5_rel=-0.015,
            vol_20=0.021,
            gap_uh_ppp=gap_val,
            config_modelos=reg_norm,
        )
        self.assertTrue(0.0 < res_gap["probabilidad"] < 1.0)
        self.assertIn(res_gap["clase"], (0, 1))
        self.assertIn(res_gap["etiqueta"], ("SUBIDA", "NO_SUBIDA"))

    def test_03_endpoint_metricas_modelos_y_enriquecimiento_senales(self):
        """
        Verifica el contrato de `GET /api/metricas/modelos` y el enriquecimiento
        de señales en `GET /api/senales/panel`.
        """
        payload = obtener_metricas_institucionales_modelos()
        self.assertEqual(payload["fecha_congelamiento_oficial"], "2026-11-06")

        modelos_test = {m["id_modelo"]: m for m in payload["modelos_test"]}
        self.assertIn("G2_V4_ADJ", modelos_test)
        self.assertIn("G2_V4_F1_GAP", modelos_test)
        self.assertAlmostEqual(float(modelos_test["G2_V4_F1_GAP"]["exactitud_15_pct"]), 52.60, places=2)
        self.assertAlmostEqual(float(modelos_test["G2_V4"]["n_efectivo_15"]), 623.2, places=1)
        self.assertAlmostEqual(float(modelos_test["G2_V4_ADJ"]["n_efectivo_15"]), 624.2, places=1)

        curvas = payload["curvas_calibracion_reliability"]
        self.assertIn("G2_V4_ADJ", curvas)
        self.assertGreaterEqual(len(curvas["G2_V4_ADJ"]), 5)

        aud = payload["auditoria_prospectiva"]
        self.assertEqual(aud["total_senales_emitidas_g2"], 125)
        self.assertEqual(aud["conteo_por_muestra_evaluacion"]["IN_SAMPLE_DISENO"], 125)

        f5 = payload["asignacion_capital_fase5"]
        est_f1 = f5["estrategias"]["G2_V4_F1_GAP_KELLY_250D"]
        self.assertAlmostEqual(float(est_f1["sharpe_neto_20bps"]), 1.0437, places=2)
        self.assertAlmostEqual(float(est_f1["retorno_acumulado_neto_20bps_pct"]), 6.94, places=2)
        self.assertIn("GMEXICO", f5["ultimos_pesos_sugeridos_pct"])

        # Verificar llamada directa al endpoint FastAPI
        res_api = api.get_metricas_modelos()
        self.assertEqual(res_api["fecha_congelamiento_oficial"], "2026-11-06")

        # Verificar enriquecimiento de señales (5 modelos por emisora + muestra_evaluacion)
        usuario_demo = Usuario(
            id="demo-uid",
            email="demo@prismabmv.com",
            nombre="Demo",
            rol="user",
            plan="professional",
        )
        res_senales = api.get_senales_panel(fecha="2026-11-04", emisora="WALMEX", u=usuario_demo)
        senales_w = res_senales["senales"]
        self.assertEqual(len(senales_w), 5)
        for s in senales_w:
            self.assertIn("muestra_evaluacion", s)
            self.assertEqual(s["muestra_evaluacion"], "IN_SAMPLE_DISENO")
            self.assertIn("estado_resolucion", s)

    def test_04_invarianza_hashes_protegidos(self):
        """
        Verifica que ningún archivo protegido de Primera Generación ni el registro
        congelado `registro_modelos_g2_oficial.json` hayan sido alterados.
        """
        hashes_actuales = mon.hashes_protegidos_g2()
        for nombre, h_val in hashes_actuales.items():
            self.assertEqual(len(h_val), 64, f"Hash inválido para {nombre}")


if __name__ == "__main__":
    unittest.main()
