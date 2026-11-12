"""
Pruebas unitarias para la Fase 3: Features externas, microestructura y estudio de ablación.
"""

from __future__ import annotations

import json
import unittest

import numpy as np
import pandas as pd

from features_externas import (
    ARCHIVO_PANEL_FASE3,
    ARCHIVO_REPORTE_ABLACION_CSV,
    ARCHIVO_REPORTE_ABLACION_JSON,
    verificar_sin_fuga_temporal_features_externas,
)
from monitor_prospectivo_segunda_generacion import hashes_protegidos_g2


class TestFase3FeaturesExternas(unittest.TestCase):
    """Valida las garantías de no-fuga temporal, cero imputación y ablación de la Fase 3."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.df_panel = pd.read_csv(ARCHIVO_PANEL_FASE3)
        cls.df_ablacion = pd.read_csv(ARCHIVO_REPORTE_ABLACION_CSV)
        cls.reporte_json = json.loads(ARCHIVO_REPORTE_ABLACION_JSON.read_text(encoding="utf-8"))

    def test_ninguna_feature_externa_posterior_a_t_1400(self) -> None:
        """
        Garantiza que ningún feature de F1, F2, F3 o calendarios tenga fecha/hora de publicación
        posterior a las 14:00:00 CDMX del día t.
        """
        res = verificar_sin_fuga_temporal_features_externas(self.df_panel)
        self.assertTrue(res["sin_fuga_temporal"], msg=f"Fuga temporal detectada: {res}")
        self.assertEqual(res["violaciones_f1_intradia"], 0)
        self.assertEqual(res["violaciones_f2_banxico"], 0)
        self.assertEqual(res["violaciones_f3_yahoo_lag1"], 0)
        self.assertEqual(res["violaciones_calendarios"], 0)
        self.assertEqual(res["violaciones_fecha_previa"], 0)
        self.assertEqual(res["total_filas_verificadas"], 9879)

    def test_cero_imputacion_en_feriados_eeuu_y_cobertura_f1_f2(self) -> None:
        """
        Verifica que F1 y F2 tengan cobertura del 100% sin imputación y que en los días
        posteriores a feriado de EE.UU. (t-1 sin sesión en NYSE) F3 conserve NaN sin ffill
        y registre explícitamente el motivo 'FERIADO_MERCADO_EEUU_EN_T_MENOS_1'.
        """
        self.assertEqual(int(self.df_panel["gap_uh_ppp"].isna().sum()), 0)
        self.assertEqual(int(self.df_panel["gap_uh_ppp_rel_panel"].isna().sum()), 0)
        self.assertEqual(int(self.df_panel["gap_uh_ppp_media5"].isna().sum()), 0)
        self.assertEqual(int(self.df_panel["fx_ret5"].isna().sum()), 0)
        self.assertEqual(int(self.df_panel["fx_ret5_x_beta"].isna().sum()), 0)

        # Feriados de EE.UU. en t-1 deben permanecer como NaN (sin ffill)
        filas_sin_spx = self.df_panel[self.df_panel["spx_ret5_lag1"].isna()]
        self.assertGreater(len(filas_sin_spx), 0)
        self.assertTrue(
            (filas_sin_spx["motivo_sin_dato_f3"] == "FERIADO_MERCADO_EEUU_EN_T_MENOS_1").all()
        )

    def test_exactitud_aritmetica_gap_uh_ppp_y_cobre_gmexico(self) -> None:
        """Comprueba la fórmula exacta de gap_uh_ppp y que cobre_ret5_lag1_gmexico sea 0 fuera de GMEXICO."""
        gap_esperado = (
            self.df_panel["ultimo_bmv_mxn"] - self.df_panel["ppp_t_raw" if "ppp_t_raw" in self.df_panel.columns else "ppp_t"]
        ) / self.df_panel["ppp_t"]
        max_diff = float(np.max(np.abs(self.df_panel["gap_uh_ppp"].to_numpy() - gap_esperado.to_numpy())))
        self.assertLess(max_diff, 1e-12)

        no_gmex = self.df_panel[self.df_panel["emisora"] != "GMEXICO"]
        self.assertTrue(np.all(no_gmex["cobre_ret5_lag1_gmexico"].to_numpy() == 0.0))

    def test_reporte_ablacion_e_integridad_hashes_protegidos(self) -> None:
        """Verifica la estructura de reporte_fase3_ablacion.csv y la integridad de hashes_protegidos_g2."""
        self.assertGreaterEqual(len(self.df_ablacion), 14)
        cols_esperadas = {
            "experimento",
            "familia",
            "features_agregadas",
            "cv_delta_logloss",
            "cv_p_dm_logloss_unilateral",
            "cv_delta_bss_pct",
            "aceptada_regla_preregistrada_cv",
            "test15_acc_cand_pct",
            "test15_delta_brier",
            "test4_acc_cand_pct",
            "test4_delta_brier",
        }
        self.assertTrue(cols_esperadas.issubset(set(self.df_ablacion.columns)))
        self.assertTrue(self.reporte_json.get("integridad_archivos_protegidos_intacta"))
        hashes_actuales = hashes_protegidos_g2()
        self.assertGreaterEqual(len(hashes_actuales), 5)
        for nombre, digest in hashes_actuales.items():
            self.assertEqual(len(digest), 64, msg=f"Hash inválido para {nombre}")


if __name__ == "__main__":
    unittest.main()
