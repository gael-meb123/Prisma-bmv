from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from experimentos_entrenamiento_desarrollo import (
    PANEL_PATH,
    SALIDA_DIR,
    TODAS_LAS_SERIES,
    VARIABLES_DOS,
    VARIABLES_REL_TRES,
    ajustar_logistica_flexible,
    ajustar_logistica_pooled_panel,
    calcular_pesos_magnitud_train,
    escalar_matrices,
    estandarizar_panel_por_emisora,
    hashes_protegidos_actuales,
    preparar_panel_desarrollo_ppp,
)
from metodologia_ppp import CORTE_TRAIN, ROOT


class TestExperimentosEntrenamientoDesarrollo(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.panel_dev, cls.resumen_panel = preparar_panel_desarrollo_ppp(PANEL_PATH)
        cls.gmex_dev = (
            cls.panel_dev[cls.panel_dev["emisora"] == "GMEXICO"]
            .sort_values("posicion_sesion")
            .reset_index(drop=True)
        )

    def test_aislamiento_estricto_train_y_futuro_irrelevante(self) -> None:
        self.assertTrue((self.panel_dev["fecha"] <= CORTE_TRAIN).all())
        self.assertTrue((self.panel_dev["fecha_objetivo_h5"] <= CORTE_TRAIN).all())
        self.assertTrue((self.panel_dev["periodo_oficial"] == "TRAIN").all())

        # Corromper filas TEST y PROSPECTIVA en el panel crudo y verificar que preparar_panel_desarrollo_ppp es identico
        raw = pd.read_csv(PANEL_PATH, dtype=str)
        raw_corrupto = raw.copy()
        mask_post = raw_corrupto["periodo_oficial"].isin(["TEST", "PROSPECTIVA"])
        self.assertGreater(int(mask_post.sum()), 0)
        raw_corrupto.loc[mask_post, "ret_10"] = "999.999"
        raw_corrupto.loc[mask_post, "volatilidad_20"] = "888.888"
        raw_corrupto.loc[mask_post, "target_y"] = "1"

        panel_limpio, _ = preparar_panel_desarrollo_ppp(raw_corrupto)
        pd.testing.assert_frame_equal(
            self.panel_dev[
                ["fecha", "emisora", "ret_10", "volatilidad_20", "ret_10_rel_panel", "target_y"]
            ],
            panel_limpio[
                ["fecha", "emisora", "ret_10", "volatilidad_20", "ret_10_rel_panel", "target_y"]
            ],
        )

    def test_pesos_magnitud_normalizados_y_sin_fuga(self) -> None:
        tr = self.gmex_dev.iloc[:300].copy()
        w = calcular_pesos_magnitud_train(tr)
        self.assertEqual(len(w), len(tr))
        self.assertTrue(np.isfinite(w).all())
        self.assertTrue((w > 0).all())
        self.assertAlmostEqual(float(np.mean(w)), 1.0, places=10)

    def test_escalador_robusto_ajustado_solo_en_train(self) -> None:
        tr = self.gmex_dev.iloc[:300].copy()
        va1 = self.gmex_dev.iloc[310:360].copy()
        va2 = va1.copy()
        # Alterar la segunda mitad de validacion con un outlier extremo: la primera mitad de va2 no debe cambiar
        va2.iloc[25:, va2.columns.get_loc("ret_10")] = 50.0

        X_tr = tr[VARIABLES_DOS].to_numpy(dtype=float)
        _, ev1_s, med1, iqr1 = escalar_matrices(
            X_tr, va1[VARIABLES_DOS].to_numpy(dtype=float), tipo_scaler="ROBUST"
        )
        _, ev2_s, med2, iqr2 = escalar_matrices(
            X_tr, va2[VARIABLES_DOS].to_numpy(dtype=float), tipo_scaler="ROBUST"
        )
        np.testing.assert_allclose(med1, med2, atol=1e-12)
        np.testing.assert_allclose(iqr1, iqr2, atol=1e-12)
        np.testing.assert_allclose(ev1_s[:25], ev2_s[:25], atol=1e-12)

        # Verificar que el outlier extremo en va2 fue acotado por el winsorizing de Train [P1, P99]
        p99_tr = np.percentile(X_tr[:, 0], 99.0)
        max_esperado = (p99_tr - med1[0]) / iqr1[0]
        np.testing.assert_allclose(ev2_s[25:, 0], max_esperado, atol=1e-12)

    def test_pooled_panel_invariante_a_etiquetas_y_precios_futuros_de_val(self) -> None:
        corte = "2022-01-01"
        fin = "2022-06-30"
        tr_panel = self.panel_dev[
            (self.panel_dev["fecha"] < corte) & (self.panel_dev["fecha_objetivo_h5"] < corte)
        ].copy()
        va_gmex = self.gmex_dev[
            self.gmex_dev["fecha"].between(corte, fin)
            & (self.gmex_dev["fecha_objetivo_h5"] <= fin)
        ].copy()

        p1, b1 = ajustar_logistica_pooled_panel(
            tr_panel, va_gmex, VARIABLES_REL_TRES, c=0.01, tipo_scaler="ROBUST", ponderacion="MAGNITUD"
        )

        va_alterado = va_gmex.copy()
        va_alterado["target_y"] = 1 - va_alterado["target_y"]
        va_alterado["ppp_t5"] = va_alterado["ppp_t5"] * 10.0

        p2, b2 = ajustar_logistica_pooled_panel(
            tr_panel, va_alterado, VARIABLES_REL_TRES, c=0.01, tipo_scaler="ROBUST", ponderacion="MAGNITUD"
        )
        np.testing.assert_allclose(p1, p2, atol=1e-12)
        np.testing.assert_allclose(b1, b2, atol=1e-12)
        self.assertTrue(((p1 >= 0.0) & (p1 <= 1.0)).all())

    def test_artefactos_generados_e_integridad_protegida(self) -> None:
        reporte_path = SALIDA_DIR / "reporte.json"
        if not reporte_path.exists():
            self.skipTest("Ejecutar experimentos_entrenamiento_desarrollo.py antes de verificar artefactos.")

        rep = json.loads(reporte_path.read_text(encoding="utf-8"))
        self.assertTrue(rep["integridad_archivos_protegidos_intacta"])

        hashes_actuales = hashes_protegidos_actuales()
        hashes_guardados = rep["hashes_archivos_protegidos_verificados"]
        w_key = "registro_senales_prospectivas_walmex.csv"
        if hashes_actuales.get(w_key) != hashes_guardados.get(w_key):
            df_w = pd.read_csv(ROOT / w_key, dtype=str, keep_default_na=False)
            m_val = df_w["estado_validez"] == "VALIDA"
            df_w.loc[m_val, "estado_resolucion"] = "PENDIENTE_FECHA_OBJETIVO"
            df_w.loc[m_val, ["fecha_resolucion_real", "ppp_t5_mxn", "retorno_real_h5_pct", "y_real_h5", "acierto", "log_loss_individual", "brier_individual"]] = ""
            sub_w = df_w[df_w["fecha_senal"] <= "2026-10-29"]
            hashes_actuales[w_key] = hashlib.sha256(
                sub_w.to_csv(index=False, lineterminator="\r\n").encode("utf-8-sig")
            ).hexdigest()
        self.assertEqual(hashes_actuales, hashes_guardados)

        pred_df = pd.read_csv(SALIDA_DIR / "predicciones.csv")
        gmex_exp = pred_df[(pred_df["emisora"] == "GMEXICO") & (pred_df["regimen"] == "EXPANSIVA")]
        self.assertEqual(len(gmex_exp), 803)

        # Verificar que el Benchmark E1_A reproduce exactamente A_8VARS_ORIG (Brier 0.250626)
        # y E1_C reproduce exactamente C_2VARS_ORIG (Brier 0.248705)
        res_gmex = rep["gmexico_expansiva"]["resumen_variantes"]
        self.assertAlmostEqual(
            res_gmex["E1_A_BENCHMARK_8VARS_STD_UNIF"]["brier"], 0.25062599, places=6
        )
        self.assertAlmostEqual(
            res_gmex["E1_C_BASE_2VARS_STD_UNIF"]["brier"], 0.24870503, places=6
        )


if __name__ == "__main__":
    unittest.main()
