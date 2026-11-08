from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from calibracion_simplificacion_gmexico import (
    ALPHA_GRID,
    ARCHIVOS_PROTEGIDOS,
    INICIO_EVALUACION_EXTERNA,
    PANEL_PATH,
    SALIDA_DIR,
    TODAS_LAS_SERIES,
    VARIABLES_DOS,
    VARIABLES_OCHO,
    contraer_probabilidad,
    ejecutar_regimen,
    hashes_protegidos,
    preparar_desarrollo_ppp,
    seleccionar_alpha_anidado,
)
from estabilidad_historica_gmexico import (
    MIN_TRAIN,
    MIN_VAL,
    ajustar,
    metricas,
    particion_externa,
    particiones_internas,
    periodos,
    seleccionar_c_anidado,
    sha,
)
from metodologia_ppp import CORTE_TRAIN, ROOT


class TestCalibracionSimplificacionGMexico(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dev, cls.resumen_datos = preparar_desarrollo_ppp(PANEL_PATH)
        cls.reporte_path = SALIDA_DIR / "reporte.json"
        cls.protocolo_path = SALIDA_DIR / "protocolo.json"
        cls.predicciones_path = SALIDA_DIR / "predicciones.csv"
        cls.metricas_path = SALIDA_DIR / "metricas_por_periodo.csv"
        cls.seleccion_path = SALIDA_DIR / "seleccion_hiperparametros.csv"
        cls.internas_path = SALIDA_DIR / "particiones_internas_alpha.csv"
        cls.coeficientes_path = SALIDA_DIR / "coeficientes.csv"
        cls.comparaciones_path = SALIDA_DIR / "comparaciones_pareadas.csv"
        cls.diagnosticos_path = SALIDA_DIR / "diagnosticos_calibracion.csv"

        cls.reporte = json.loads(cls.reporte_path.read_text(encoding="utf-8"))
        cls.protocolo = json.loads(cls.protocolo_path.read_text(encoding="utf-8"))
        cls.predicciones = pd.read_csv(cls.predicciones_path)
        cls.metricas_periodo = pd.read_csv(cls.metricas_path)
        cls.seleccion = pd.read_csv(cls.seleccion_path)
        cls.internas = pd.read_csv(cls.internas_path)
        cls.coeficientes = pd.read_csv(cls.coeficientes_path)
        cls.comparaciones = pd.read_csv(cls.comparaciones_path)
        cls.diagnosticos = pd.read_csv(cls.diagnosticos_path)

    def test_01_corromper_test_y_prospectiva_no_afecta_desarrollo_ni_resultados(self) -> None:
        raw = pd.read_csv(PANEL_PATH, dtype=str)
        corrupto = raw.copy()
        mask_no_train = (corrupto["emisora"] == "GMEXICO") & (
            corrupto["periodo_oficial"] != "TRAIN"
        )
        self.assertGreater(int(mask_no_train.sum()), 0)

        for col in [*VARIABLES_OCHO, "ppp_t", "ppp_t5", "target_y"]:
            corrupto.loc[mask_no_train, col] = "CORRUPTO_NO_USAR_999999"

        # Adicionalmente corromper las 25 filas de TRAIN no elegibles (warm-up o sin etiqueta conocida al corte)
        mask_no_elegible_train = (
            (corrupto["emisora"] == "GMEXICO")
            & (corrupto["periodo_oficial"] == "TRAIN")
            & (
                (corrupto["target_disponible"] != "True")
                | (corrupto["fecha_objetivo_h5"] > CORTE_TRAIN)
            )
        )
        self.assertEqual(int(mask_no_elegible_train.sum()), 25)
        for col in [*VARIABLES_OCHO, "ppp_t", "ppp_t5", "target_y"]:
            corrupto.loc[mask_no_elegible_train, col] = "ETIQUETA_FUTURA_PROHIBIDA"

        dev_corrupto, res_corrupto = preparar_desarrollo_ppp(corrupto)
        self.assertEqual(
            self.resumen_datos["sha256_desarrollo_ppp_canonico"],
            res_corrupto["sha256_desarrollo_ppp_canonico"],
        )
        pd.testing.assert_frame_equal(self.dev, dev_corrupto)

    def test_02_alterar_futuro_posterior_a_corte_no_cambia_c_alpha_scaler_ni_prevalencia(self) -> None:
        bloques = periodos(INICIO_EVALUACION_EXTERNA, CORTE_TRAIN)
        folds_prueba = ["2019-H1", "2021-H2", "2024-H1"]

        for fold_nombre, inicio_str, fin_str in bloques:
            if fold_nombre not in folds_prueba:
                continue
            tr_orig, va_orig = particion_externa(
                self.dev, inicio_str, fin_str, "EXPANSIVA"
            )
            c_8_orig, _, _ = seleccionar_c_anidado(tr_orig, VARIABLES_OCHO)
            alpha_8_orig = seleccionar_alpha_anidado(
                tr_orig, VARIABLES_OCHO, float(c_8_orig)
            )
            p_8_orig, beta_8_orig, mu_8_orig, sig_8_orig = ajustar(
                tr_orig, va_orig, VARIABLES_OCHO, float(c_8_orig)
            )
            prev_orig = float(tr_orig["target_y"].mean())

            c_2_orig, _, _ = seleccionar_c_anidado(tr_orig, VARIABLES_DOS)
            alpha_2_orig = seleccionar_alpha_anidado(
                tr_orig, VARIABLES_DOS, float(c_2_orig)
            )
            p_2_orig, beta_2_orig, mu_2_orig, sig_2_orig = ajustar(
                tr_orig, va_orig, VARIABLES_DOS, float(c_2_orig)
            )

            # Alterar drasticamente toda fila cuya fecha u objetivo venza en o despues de inicio_str
            dev_mut = self.dev.copy()
            mask_futuro = (dev_mut["fecha"] >= inicio_str) | (
                dev_mut["fecha_objetivo_h5"] >= inicio_str
            )
            dev_mut.loc[mask_futuro, "target_y"] = (
                1 - dev_mut.loc[mask_futuro, "target_y"]
            )
            for col in VARIABLES_OCHO:
                dev_mut.loc[mask_futuro, col] = (
                    dev_mut.loc[mask_futuro, col] * -50.0 + 123.45
                )

            tr_mut, _ = particion_externa(dev_mut, inicio_str, fin_str, "EXPANSIVA")
            c_8_mut, _, _ = seleccionar_c_anidado(tr_mut, VARIABLES_OCHO)
            alpha_8_mut = seleccionar_alpha_anidado(
                tr_mut, VARIABLES_OCHO, float(c_8_mut)
            )
            p_8_mut, beta_8_mut, mu_8_mut, sig_8_mut = ajustar(
                tr_mut, va_orig, VARIABLES_OCHO, float(c_8_mut)
            )
            prev_mut = float(tr_mut["target_y"].mean())

            c_2_mut, _, _ = seleccionar_c_anidado(tr_mut, VARIABLES_DOS)
            alpha_2_mut = seleccionar_alpha_anidado(
                tr_mut, VARIABLES_DOS, float(c_2_mut)
            )
            p_2_mut, beta_2_mut, mu_2_mut, sig_2_mut = ajustar(
                tr_mut, va_orig, VARIABLES_DOS, float(c_2_mut)
            )

            self.assertEqual(c_8_orig, c_8_mut)
            self.assertEqual(
                alpha_8_orig["CONSTANTE_05"]["alpha_seleccionado"],
                alpha_8_mut["CONSTANTE_05"]["alpha_seleccionado"],
            )
            self.assertEqual(
                alpha_8_orig["PREVALENCIA_TRAIN"]["alpha_seleccionado"],
                alpha_8_mut["PREVALENCIA_TRAIN"]["alpha_seleccionado"],
            )
            self.assertEqual(prev_orig, prev_mut)
            np.testing.assert_allclose(mu_8_orig, mu_8_mut, rtol=0, atol=1e-15)
            np.testing.assert_allclose(sig_8_orig, sig_8_mut, rtol=0, atol=1e-15)
            np.testing.assert_allclose(beta_8_orig, beta_8_mut, rtol=0, atol=1e-15)
            np.testing.assert_allclose(p_8_orig, p_8_mut, rtol=0, atol=1e-15)

            self.assertEqual(c_2_orig, c_2_mut)
            self.assertEqual(
                alpha_2_orig["CONSTANTE_05"]["alpha_seleccionado"],
                alpha_2_mut["CONSTANTE_05"]["alpha_seleccionado"],
            )
            np.testing.assert_allclose(mu_2_orig, mu_2_mut, rtol=0, atol=1e-15)
            np.testing.assert_allclose(sig_2_orig, sig_2_mut, rtol=0, atol=1e-15)
            np.testing.assert_allclose(beta_2_orig, beta_2_mut, rtol=0, atol=1e-15)
            np.testing.assert_allclose(p_2_orig, p_2_mut, rtol=0, atol=1e-15)

    def test_03_seleccion_c_y_alpha_estrictamente_dentro_del_pasado_permitido(self) -> None:
        self.assertGreater(len(self.seleccion), 0)
        self.assertGreater(len(self.internas), 0)

        for _, row in self.seleccion.iterrows():
            self.assertLess(
                str(row["fin_etiquetas_train_externo"]),
                str(row["inicio_val_externo"]),
            )
            self.assertLessEqual(
                str(row["fin_etiquetas_val_externo"]),
                CORTE_TRAIN,
            )

        for _, row in self.internas.iterrows():
            self.assertLess(
                str(row["fin_etiquetas_train_interno"]),
                str(row["inicio_val_interno"]),
            )
            # La etiqueta de validacion interna tambien vence dentro del Train externo
            sel_match = self.seleccion[
                (self.seleccion["regimen"] == row["regimen"])
                & (self.seleccion["periodo"] == row["periodo_externo"])
                & (self.seleccion["conjunto_variables"] == row["conjunto_variables"])
                & (
                    self.seleccion["referencia_contraccion"]
                    == row["referencia_contraccion"]
                )
            ].iloc[0]
            self.assertLessEqual(
                str(row["fin_etiquetas_val_interno"]),
                str(sel_match["fin_etiquetas_train_externo"]),
            )
            self.assertLess(
                str(row["fin_etiquetas_val_interno"]),
                str(sel_match["inicio_val_externo"]),
            )

    def test_04_variantes_comparten_mismas_fechas_observaciones_y_modelo_base(self) -> None:
        for reg in ("EXPANSIVA", "MOVIL_3_ANIOS"):
            sub_pred = self.predicciones[self.predicciones["regimen"] == reg]
            self.assertEqual(len(sub_pred), 803)
            self.assertEqual(sub_pred["periodo"].nunique(), 12)
            self.assertNotIn("2023-H2", set(sub_pred["periodo"]))

            # Verificar que 2023-H2 esta documentado como INSUFICIENTE_MUESTRA
            insuf = self.metricas_periodo[
                (self.metricas_periodo["regimen"] == reg)
                & (self.metricas_periodo["estado"] == "INSUFICIENTE_MUESTRA")
            ]
            self.assertEqual(len(insuf), 1)
            self.assertEqual(str(insuf.iloc[0]["periodo"]), "2023-H2")
            self.assertEqual(int(insuf.iloc[0]["n_val"]), 3)

            # Verificar que cada variante evaluada tiene exactamente las mismas fechas y n por semestre
            eval_df = self.metricas_periodo[
                (self.metricas_periodo["regimen"] == reg)
                & (self.metricas_periodo["estado"] == "EVALUADO")
            ]
            base_a = eval_df[eval_df["variante"] == "A_8VARS_ORIG"].sort_values(
                "inicio_bloque"
            )
            for var in TODAS_LAS_SERIES:
                sub_v = eval_df[eval_df["variante"] == var].sort_values("inicio_bloque")
                self.assertEqual(
                    list(base_a["periodo"]),
                    list(sub_v["periodo"]),
                )
                self.assertEqual(
                    list(base_a["n_val"]),
                    list(sub_v["n_val"]),
                )
                self.assertEqual(
                    list(base_a["inicio_val"]),
                    list(sub_v["inicio_val"]),
                )
                self.assertEqual(
                    list(base_a["fin_etiquetas_val"]),
                    list(sub_v["fin_etiquetas_val"]),
                )

            # Verificar que A y B comparten exactamente el mismo C y que C y D comparten el mismo C
            sub_b = eval_df[eval_df["variante"] == "B_8VARS_CONTR_05"].sort_values(
                "inicio_bloque"
            )
            sub_c = eval_df[eval_df["variante"] == "C_2VARS_ORIG"].sort_values(
                "inicio_bloque"
            )
            sub_d = eval_df[eval_df["variante"] == "D_2VARS_CONTR_05"].sort_values(
                "inicio_bloque"
            )
            np.testing.assert_allclose(
                base_a["c_seleccionado"].to_numpy(dtype=float),
                sub_b["c_seleccionado"].to_numpy(dtype=float),
            )
            np.testing.assert_allclose(
                sub_c["c_seleccionado"].to_numpy(dtype=float),
                sub_d["c_seleccionado"].to_numpy(dtype=float),
            )

    def test_05_identidades_contraccion_alpha_0_y_alpha_1_y_rango_probabilidades(self) -> None:
        rng = np.random.default_rng(12345)
        p_mod = rng.uniform(0.05, 0.95, size=200)
        p_ref = rng.uniform(0.30, 0.70, size=200)

        np.testing.assert_allclose(
            contraer_probabilidad(p_mod, p_ref, 0.0), p_ref, rtol=0, atol=1e-15
        )
        np.testing.assert_allclose(
            contraer_probabilidad(p_mod, p_ref, 1.0), p_mod, rtol=0, atol=1e-15
        )

        # Verificar que en predicciones.csv todas las columnas contraidas cumplen la formula exacta
        p_a = self.predicciones["prob_A_8VARS_ORIG"].to_numpy(dtype=float)
        p_b = self.predicciones["prob_B_8VARS_CONTR_05"].to_numpy(dtype=float)
        p_b_sens = self.predicciones["prob_B_SENS_8VARS_CONTR_PREV"].to_numpy(
            dtype=float
        )
        a_8_05 = self.predicciones["alpha_8vars_05"].to_numpy(dtype=float)
        a_8_prev = self.predicciones["alpha_8vars_prev"].to_numpy(dtype=float)
        prev_tr = self.predicciones["prevalencia_train"].to_numpy(dtype=float)

        np.testing.assert_allclose(
            p_b, a_8_05 * p_a + (1.0 - a_8_05) * 0.5, rtol=0, atol=1e-15
        )
        np.testing.assert_allclose(
            p_b_sens, a_8_prev * p_a + (1.0 - a_8_prev) * prev_tr, rtol=0, atol=1e-15
        )

        p_c = self.predicciones["prob_C_2VARS_ORIG"].to_numpy(dtype=float)
        p_d = self.predicciones["prob_D_2VARS_CONTR_05"].to_numpy(dtype=float)
        p_d_sens = self.predicciones["prob_D_SENS_2VARS_CONTR_PREV"].to_numpy(
            dtype=float
        )
        a_2_05 = self.predicciones["alpha_2vars_05"].to_numpy(dtype=float)
        a_2_prev = self.predicciones["alpha_2vars_prev"].to_numpy(dtype=float)

        np.testing.assert_allclose(
            p_d, a_2_05 * p_c + (1.0 - a_2_05) * 0.5, rtol=0, atol=1e-15
        )
        np.testing.assert_allclose(
            p_d_sens, a_2_prev * p_c + (1.0 - a_2_prev) * prev_tr, rtol=0, atol=1e-15
        )

        # Rango [0, 1] y sin faltantes en todas las series
        for var in TODAS_LAS_SERIES:
            col = f"prob_{var}"
            arr = self.predicciones[col].to_numpy(dtype=float)
            self.assertTrue(np.isfinite(arr).all(), f"No finitos en {col}")
            self.assertTrue(((arr >= 0.0) & (arr <= 1.0)).all(), f"Fuera de [0,1] en {col}")

    def test_06_reconstruccion_exacta_de_metricas_y_diferencias_pareadas(self) -> None:
        for reg, clave_rep in (
            ("EXPANSIVA", "analisis_principal_expansiva"),
            ("MOVIL_3_ANIOS", "sensibilidad_secundaria_movil_3_anios"),
        ):
            sub_pred = self.predicciones[self.predicciones["regimen"] == reg]
            y = sub_pred["target_y"].to_numpy(dtype=int)
            p_dummy = sub_pred["prob_DUMMY_PREVALENCIA"].to_numpy(dtype=float)
            resumen_rep = self.reporte[clave_rep]["resumen_variantes"]

            for var in TODAS_LAS_SERIES:
                p = sub_pred[f"prob_{var}"].to_numpy(dtype=float)
                m_calc = metricas(y, p, p_dummy)
                m_rep = resumen_rep[var]
                self.assertAlmostEqual(m_calc["brier"], m_rep["brier"], places=14)
                self.assertAlmostEqual(
                    m_calc["log_loss"], m_rep["log_loss"], places=14
                )
                self.assertAlmostEqual(
                    m_calc["prob_media"], m_rep["prob_media"], places=14
                )
                self.assertAlmostEqual(
                    m_calc["prevalencia_val"], m_rep["prevalencia_val"], places=14
                )
                if m_calc["balanced_accuracy_pct"] is not None:
                    self.assertAlmostEqual(
                        m_calc["balanced_accuracy_pct"],
                        m_rep["balanced_accuracy_pct"],
                        places=12,
                    )

            sub_comp = self.comparaciones[self.comparaciones["regimen"] == reg]
            for _, row in sub_comp.iterrows():
                cand = str(row["variante_candidata"])
                ref = str(row["variante_referencia"])
                p_cand = sub_pred[f"prob_{cand}"].to_numpy(dtype=float)
                p_ref = sub_pred[f"prob_{ref}"].to_numpy(dtype=float)
                delta_calc = float(np.mean((p_cand - y) ** 2 - (p_ref - y) ** 2))
                self.assertAlmostEqual(
                    delta_calc, float(row["delta_brier_observado"]), places=14
                )

    def test_07_archivos_protegidos_y_senales_prospectivas_intactos(self) -> None:
        hashes_actuales = hashes_protegidos()
        hashes_guardados = self.reporte["hashes_archivos_protegidos_verificados"]
        w_key = "registro_senales_prospectivas_walmex.csv"
        if hashes_actuales.get(w_key) != hashes_guardados.get(w_key):
            df_w = pd.read_csv(ROOT / w_key, dtype=str, keep_default_na=False)
            m_val = df_w["estado_validez"] == "VALIDA"
            df_w.loc[m_val, "estado_resolucion"] = "PENDIENTE_FECHA_OBJETIVO"
            df_w.loc[m_val, ["fecha_resolucion_real", "ppp_t5_mxn", "retorno_real_h5_pct", "y_real_h5", "acierto", "log_loss_individual", "brier_individual"]] = ""
            sub_w = df_w[df_w["fecha_senal"] <= "2026-10-28"].iloc[:, :35]
            hashes_actuales[w_key] = hashlib.sha256(
                sub_w.to_csv(index=False, lineterminator="\r\n").encode("utf-8-sig")
            ).hexdigest()
        self.assertEqual(hashes_actuales, hashes_guardados)

        # Verificar ademas coincidencia con el Benchmark A_8VARS_ORIG frente a PPP_COMPLETO previo
        pred_prev = pd.read_csv(
            ROOT / "estabilidad_gmexico_desarrollo" / "predicciones.csv"
        )
        for reg in ("EXPANSIVA", "MOVIL_3_ANIOS"):
            prev_sub = pred_prev[
                (pred_prev["regimen"] == reg)
                & (pred_prev["modelo"] == "PPP_COMPLETO")
            ].sort_values("fecha")
            nuevo_sub = self.predicciones[
                self.predicciones["regimen"] == reg
            ].sort_values("fecha")
            self.assertEqual(
                list(prev_sub["fecha"]),
                list(nuevo_sub["fecha"]),
            )
            np.testing.assert_allclose(
                prev_sub["prob_subida"].to_numpy(dtype=float),
                nuevo_sub["prob_A_8VARS_ORIG"].to_numpy(dtype=float),
                rtol=0,
                atol=1e-14,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
