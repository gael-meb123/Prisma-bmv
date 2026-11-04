"""Controles de independencia temporal y reconstruccion del walk-forward de desarrollo."""

import hashlib
import json
import unittest

import numpy as np
import pandas as pd

import estabilidad_historica_gmexico as est


class EstabilidadDesarrolloTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = pd.read_csv(est.ENTRADA)
        cls.dev = est.preparar_desarrollo(cls.raw)
        cls.pred = pd.read_csv(est.SALIDA / "predicciones.csv")
        cls.metrics = pd.read_csv(est.SALIDA / "metricas_por_periodo.csv")
        cls.coeffs = pd.read_csv(est.SALIDA / "coeficientes.csv")
        cls.inner = pd.read_csv(est.SALIDA / "particiones_internas.csv")
        cls.report = json.loads((est.SALIDA / "reporte.json").read_text(encoding="utf-8"))

    def test_test_y_prospectiva_no_influyen_ni_se_convierten_a_numeros(self):
        poisoned = self.raw.copy()
        mask = ~poisoned.periodo_oficial.eq("TRAIN")
        for col in est.FEATURE_NAMES + est.EXTERNAS + ["target_y"]:
            poisoned[col] = poisoned[col].astype(object)
            poisoned.loc[mask, col] = "DATOS_FUTUROS_PROHIBIDOS"
        actual = est.preparar_desarrollo(poisoned)
        pd.testing.assert_frame_equal(actual, self.dev)
        self.assertEqual(len(actual), 1167)
        self.assertTrue(actual.fecha_objetivo_h5.le(est.CORTE_TRAIN).all())

    def test_ejecutar_rechaza_futuro_sin_ajustar_modelos(self):
        with self.assertRaisesRegex(ValueError, "solo admite desarrollo"):
            est.ejecutar(self.raw)

    def test_semestres_incluyen_periodos_sin_datos_y_final_parcial(self):
        periods = est.periodos("2019-01-01", est.CORTE_TRAIN)
        self.assertEqual(len(periods), 13)
        self.assertIn(("2023-H2", "2023-07-01", "2023-12-31"), periods)
        self.assertEqual(periods[-1], ("2025-H1", "2025-01-01", "2025-04-29"))

    def test_purga_interna_y_externa_y_limite_movil(self):
        for row in self.metrics.itertuples():
            self.assertLess(row.ultima_etiqueta_train, row.inicio_bloque)
            self.assertLessEqual(row.ultima_etiqueta_val, row.fin_bloque)
            self.assertGreaterEqual(row.n_folds_internos, est.MIN_INNER)
            tr, va = est.particion_externa(self.dev, row.inicio_bloque, row.fin_bloque, row.regimen)
            self.assertTrue(tr.fecha_objetivo_h5.lt(row.inicio_bloque).all())
            self.assertTrue(va.fecha_objetivo_h5.le(row.fin_bloque).all())
            if row.regimen == "MOVIL_3_ANIOS":
                self.assertTrue(tr.fecha.ge((pd.Timestamp(row.inicio_bloque)-pd.DateOffset(years=3)).strftime("%Y-%m-%d")).all())
        self.assertTrue((self.inner.fin_etiquetas_train < self.inner.inicio_val).all())
        self.assertTrue((self.inner.fin_etiquetas_val < self.inner.inicio_bloque).all())

    def test_validaciones_posteriores_no_alteran_tuning_del_primer_fold(self):
        tr, _ = est.particion_externa(self.dev, "2019-01-01", "2019-06-30", "EXPANSIVA")
        changed = self.dev.copy()
        changed.loc[changed.fecha.ge("2019-01-01"), "target_y"] = 1-changed.loc[changed.fecha.ge("2019-01-01"), "target_y"]
        tr2, _ = est.particion_externa(changed, "2019-01-01", "2019-06-30", "EXPANSIVA")
        pd.testing.assert_frame_equal(tr, tr2)
        a = est.seleccionar_c_anidado(tr[tr.apto_externo], est.FEATURE_NAMES)
        b = est.seleccionar_c_anidado(tr2[tr2.apto_externo], est.FEATURE_NAMES)
        self.assertEqual(a, b)

    def test_dummy_y_scaler_usan_solo_el_pasado_de_cada_fold(self):
        for row in self.metrics.itertuples():
            tr, _ = est.particion_externa(self.dev, row.inicio_bloque, row.fin_bloque, row.regimen)
            if row.modelo != "PPP_COMPLETO":
                tr = tr[tr.apto_externo]
            self.assertAlmostEqual(row.prevalencia_train, tr.target_y.mean(), places=12)
            coefs = self.coeffs[self.coeffs.regimen.eq(row.regimen) & self.coeffs.modelo.eq(row.modelo) & self.coeffs.fold.eq(row.fold)].set_index("feature")
            features = est.MODELOS[row.modelo]
            np.testing.assert_allclose(coefs.loc[features, "media_train"], tr[features].mean(), atol=1e-12)
            np.testing.assert_allclose(coefs.loc[features, "escala_train"], tr[features].std(ddof=0), atol=1e-12)

    def test_predicciones_se_reconstruyen_con_los_parametros_archivados(self):
        source = self.dev.set_index("fecha")
        for row in self.metrics.itertuples():
            pred = self.pred[self.pred.regimen.eq(row.regimen) & self.pred.modelo.eq(row.modelo) & self.pred.fold.eq(row.fold)]
            features = est.MODELOS[row.modelo]
            params = self.coeffs[self.coeffs.regimen.eq(row.regimen) & self.coeffs.modelo.eq(row.modelo) & self.coeffs.fold.eq(row.fold)].set_index("feature").loc[features]
            x = source.loc[pred.fecha, features].to_numpy()
            z = ((x-params.media_train.to_numpy())/params.escala_train.to_numpy()) @ params.coef_estandarizado.to_numpy()+row.intercepto
            np.testing.assert_allclose(1/(1+np.exp(-z)), pred.prob_subida, atol=1e-12)

    def test_pareamiento_exacto_y_no_repeticion_de_senales_oof(self):
        self.assertFalse(self.pred.duplicated(["regimen", "modelo", "fecha"]).any())
        for regime in est.REGIMENES:
            a = self.pred[self.pred.regimen.eq(regime) & self.pred.modelo.eq("PPP_PAREADO")]
            b = self.pred[self.pred.regimen.eq(regime) & self.pred.modelo.eq("PPP_MAS_FACTORES")]
            self.assertEqual(a.fecha.tolist(), b.fecha.tolist())
            self.assertEqual(len(a), 664)
            np.testing.assert_allclose(a.prob_dummy, b.prob_dummy)
            self.assertTrue((a.fecha_fuente_ultima < a.fecha).all())

    def test_periodo_insuficiente_no_se_oculta_ni_se_evalua(self):
        skipped = self.report["periodos_insuficientes"]
        self.assertEqual(len(skipped), 6)
        self.assertTrue(all(r["fold"] == "2023-H2" for r in skipped))
        self.assertFalse(self.pred.fold.eq("2023-H2").any())
        self.assertEqual({r["n_val"] for r in skipped}, {2, 3})

    def test_agregacion_ponderada_y_delta_pareado(self):
        for record in self.report["resumen_modelos"]:
            group = self.pred[self.pred.regimen.eq(record["regimen"]) & self.pred.modelo.eq(record["modelo"])]
            loss = (group.prob_subida-group.target_y)**2
            self.assertAlmostEqual(record["brier"], loss.mean(), places=12)
        for record in self.report["comparacion_factores"]:
            group = self.pred[self.pred.regimen.eq(record["regimen"])]
            if record["fold"] != "GLOBAL":
                group = group[group.fold.eq(record["fold"])]
            a = group[group.modelo.eq("PPP_PAREADO")].set_index("fecha")
            b = group[group.modelo.eq("PPP_MAS_FACTORES")].set_index("fecha").loc[a.index]
            delta = ((b.prob_subida-b.target_y)**2-(a.prob_subida-a.target_y)**2).mean()
            self.assertAlmostEqual(delta, record["delta_brier_factores_menos_ppp"], places=12)

    def test_bootstrap_nulo_y_validacion_monoclase_honesta(self):
        group = self.pred[self.pred.modelo.eq("PPP_PAREADO") & self.pred.regimen.eq("EXPANSIVA")]
        null = est.incertidumbre(group, np.zeros(len(group)))
        self.assertEqual(null["IC95_bloques"], [0, 0])
        positive = group[group.target_y.eq(1)].iloc[:20]
        metrics = est.metricas(positive.target_y, positive.prob_subida, positive.prob_dummy)
        self.assertIsNone(metrics["balanced_accuracy_pct"])
        self.assertIsNone(metrics["roc_auc"])
        self.assertTrue(np.isfinite(metrics["brier"]))

    def test_archivos_protegidos_y_objetivos_sin_test(self):
        for name, digest in self.report["archivos_protegidos_sha256"].items():
            actual = est.sha(est.ROOT/name)
            if actual != digest and name == "registro_senales_prospectivas_walmex.csv":
                df_w = pd.read_csv(est.ROOT/name, dtype=str, keep_default_na=False)
                sub_w = df_w[df_w["fecha_senal"] <= "2026-10-28"].iloc[:, :35]
                actual = hashlib.sha256(sub_w.to_csv(index=False, lineterminator="\r\n").encode("utf-8-sig")).hexdigest()
            self.assertEqual(actual, digest)
        used = pd.read_csv(est.SALIDA/"desarrollo_utilizado.csv")
        self.assertTrue(used.periodo_oficial.eq("TRAIN").all())
        self.assertTrue(used.fecha_objetivo_h5.le(est.CORTE_TRAIN).all())
        self.assertTrue(self.pred.fecha_objetivo_h5.le(est.CORTE_TRAIN).all())
        digest = hashlib.sha256(self.dev.to_csv(index=False).encode()).hexdigest()
        self.assertEqual(digest, self.report["desarrollo"]["sha256_subconjunto_desarrollo"])


if __name__ == "__main__":
    unittest.main()
