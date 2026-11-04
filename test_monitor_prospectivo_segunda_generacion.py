from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from monitor_prospectivo_segunda_generacion import (
    REGISTRO_G2_PATH,
    RESUMEN_G2_PATH,
    VENTANAS_G2_PATH,
    construir_serie_unificada_ppp,
    ejecutar_monitor_prospectivo_g2,
    extraer_ventanas_y_features_en_fecha,
    hashes_protegidos_g2,
    preparar_panel_entrenamiento_para_corte,
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
        # La suma de ret_10_rel_panel entre las emisoras elegibles de una misma fecha debe ser 0.0
        self.assertAlmostEqual(float(df_eleg["ret_10_rel_panel"].sum()), 0.0, places=12)

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


if __name__ == "__main__":
    unittest.main()
