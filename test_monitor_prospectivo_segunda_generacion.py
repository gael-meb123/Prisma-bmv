from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from monitor_prospectivo_segunda_generacion import (
    FECHA_CONGELAMIENTO_G2,
    REGISTRO_G2_PATH,
    REGISTRO_MODELOS_OFICIAL_PATH,
    RESUMEN_G2_PATH,
    VENTANAS_G2_PATH,
    calcular_sha256_config_modelo,
    clasificar_muestra_evaluacion,
    construir_serie_unificada_ppp,
    ejecutar_monitor_prospectivo_g2,
    extraer_ventanas_y_features_en_fecha,
    hashes_protegidos_g2,
    preparar_panel_entrenamiento_para_corte,
    verificar_integridad_registro_modelos_g2,
)
from metodologia_ppp import CORTE_TRAIN, ROOT


class TestMonitorProspectivoSegundaGeneracion(unittest.TestCase):
    def test_serie_unificada_y_ventanas_21_sin_imputacion(self) -> None:
        serie = construir_serie_unificada_ppp()
        df_est, df_eleg = extraer_ventanas_y_features_en_fecha(serie, "2026-10-29")
        self.assertEqual(len(df_est), 15)
        self.assertEqual(
            sorted(df_eleg["emisora"].tolist()),
            ["AMX", "GFNORTE", "GMEXICO", "WALMEX"],
        )
        # La suma de variables relativas intrapanel entre las emisoras elegibles de una misma fecha debe ser 0.0
        self.assertAlmostEqual(float(df_eleg["ret_10_rel_panel"].sum()), 0.0, places=12)
        self.assertAlmostEqual(float(df_eleg["ret_1_rel_panel"].sum()), 0.0, places=12)
        self.assertAlmostEqual(float(df_eleg["distancia_media_5_rel_panel"].sum()), 0.0, places=12)

    def test_purga_estricta_entrenamiento_por_corte(self) -> None:
        panel_csv = ROOT / "dataset_panel_15_emisoras_features.csv"
        tr_congelado = preparar_panel_entrenamiento_para_corte(
            panel_csv, "2026-10-29", "TRAIN_CONGELADO"
        )
        self.assertEqual(len(tr_congelado), 8122)
        self.assertTrue((tr_congelado["fecha_objetivo_h5"] <= CORTE_TRAIN).all())

        tr_exp = preparar_panel_entrenamiento_para_corte(
            panel_csv, "2026-10-28", "HISTORIA_PURGADA_HASTA_CORTE"
        )
        self.assertGreater(len(tr_exp), 8122)
        self.assertTrue((tr_exp["fecha"] < "2026-10-28").all())
        self.assertTrue((tr_exp["fecha_objetivo_h5"] <= "2026-10-28").all())

    def test_idempotencia_timestamps_e_integridad_archivos_protegidos(self) -> None:
        self.assertTrue(REGISTRO_G2_PATH.exists())
        self.assertTrue(VENTANAS_G2_PATH.exists())
        self.assertTrue(RESUMEN_G2_PATH.exists())

        reg1 = pd.read_csv(REGISTRO_G2_PATH, dtype=str)
        self.assertGreaterEqual(len(reg1), 24)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            reg_tmp = tmp / "reg.csv"
            ven_tmp = tmp / "ven.csv"
            res_tmp = tmp / "res.json"
            reg1.to_csv(reg_tmp, index=False)

            ejecutar_monitor_prospectivo_g2(
                fechas_solicitud=sorted(reg1["fecha_senal"].unique().tolist()),
                registro_path=reg_tmp,
                ventanas_path=ven_tmp,
                resumen_path=res_tmp,
            )
            reg2 = pd.read_csv(reg_tmp, dtype=str)
            pd.testing.assert_frame_equal(reg1, reg2)

        res_json = json.loads(RESUMEN_G2_PATH.read_text(encoding="utf-8"))
        self.assertTrue(res_json["integridad_archivos_protegidos_intacta"])
        eval_t5 = res_json["evaluacion_oficial_resuelta_t5"]
        # Como 2026-11-05 sigue en CONTINGENCIA_FUENTE_SECUNDARIA, la ventana 2026-10-28 -> 2026-11-05
        # queda en PENDIENTE_RECONCILIACION y no contamina evaluacion_oficial_resuelta_t5
        self.assertEqual(eval_t5["G2_V4_POOLED_DM5_REL_CORTO_PLAZO"]["n_resueltas_t5"], 0)
        eval_prov = res_json["evaluacion_pendiente_reconciliacion_t5"]
        self.assertEqual(
            eval_prov["G2_V4_POOLED_DM5_REL_CORTO_PLAZO"]["tasa_acierto_provisional_t5_pct"],
            100.0,
        )
        self.assertEqual(
            eval_prov["G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL"]["tasa_acierto_provisional_t5_pct"],
            100.0,
        )
        self.assertLess(
            eval_prov["G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL"]["brier_provisional_medio_t5"],
            eval_prov["G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO"]["brier_provisional_medio_t5"],
        )

    def test_congelamiento_pre_registro_y_muestra_evaluacion(self) -> None:
        hashes_cfg = verificar_integridad_registro_modelos_g2()
        self.assertEqual(len(hashes_cfg), 5)

        reg_json = json.loads(REGISTRO_MODELOS_OFICIAL_PATH.read_text(encoding="utf-8"))
        for mod_id, cfg in reg_json.items():
            self.assertEqual(cfg["fecha_congelamiento"], FECHA_CONGELAMIENTO_G2)
            self.assertEqual(cfg["estado"], "SHADOW")
            self.assertEqual(calcular_sha256_config_modelo(cfg), cfg["sha256_config"])

        # Si se altera cualquier parámetro de un modelo congelado, la verificación debe fallar
        with tempfile.TemporaryDirectory() as tmpdir:
            corrupt_path = Path(tmpdir) / "corrupt.json"
            reg_corrupt = json.loads(json.dumps(reg_json))
            reg_corrupt["G2_V4_POOLED_DM5_REL_CORTO_PLAZO"]["c_val"] = 0.05
            corrupt_path.write_text(json.dumps(reg_corrupt), encoding="utf-8")
            with self.assertRaises(ValueError):
                verificar_integridad_registro_modelos_g2(corrupt_path)

        # Todas las señales previas a 2026-11-06 deben quedar marcadas como IN_SAMPLE_DISENO
        df_senales = pd.read_csv(REGISTRO_G2_PATH, dtype=str)
        self.assertIn("muestra_evaluacion", df_senales.columns)
        previas = df_senales[df_senales["fecha_senal"] < FECHA_CONGELAMIENTO_G2]
        self.assertGreater(len(previas), 0)
        self.assertTrue((previas["muestra_evaluacion"] == "IN_SAMPLE_DISENO").all())
        self.assertEqual(clasificar_muestra_evaluacion("2026-11-05"), "IN_SAMPLE_DISENO")
        self.assertEqual(clasificar_muestra_evaluacion("2026-11-06"), "OUT_OF_SAMPLE_PRE_REGISTRADO")


if __name__ == "__main__":
    unittest.main()
