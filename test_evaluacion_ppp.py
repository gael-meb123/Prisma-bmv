"""Regresiones temporales con PPP reales del panel; no se fabrican precios."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
import pandas as pd

import etapa10_ejecutor_diario as diario
import investigacion_profunda_gmexico as gm
import modulo_panel_multiemisora as panel
from metodologia_ppp import (
    ROOT, VERSION_FEATURES, add_bmv_sessions, agregar_trazabilidad,
    calcular_features_ppp, localizar_insumo, mascara_etiquetas_conocidas,
    seleccionar_train_test, validar_ventana_fechas,
)

TEMP_ROOT = None


class EvaluacionPPPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = pd.read_csv(ROOT / "serie_ppp_historica_15_emisoras_bmv.csv")
        cls.walmex = cls.raw[cls.raw.emisora.eq("WALMEX")].sort_values("posicion_sesion")
        cls.series = pd.read_csv(ROOT / "serie_ppp_walmex_prospectiva.csv")
        cls.registro = pd.read_csv(ROOT / "registro_senales_prospectivas_walmex.csv")

    def senal_historica(self, fecha):
        row = self.registro.iloc[[0]].copy()
        row["fecha_senal"] = fecha
        row["fecha_corte_datos"] = fecha
        row["fecha_objetivo_h5"] = add_bmv_sessions(fecha, 5)
        row["ppp_base_mxn"] = float(self.walmex.set_index("fecha").loc[fecha, "ppp_bmv_mxn"])
        return row

    def test_calendario_y_feriado(self):
        self.assertEqual([add_bmv_sessions("2026-10-28", i) for i in range(1, 6)], [
            "2026-10-29", "2026-10-30", "2026-11-03", "2026-11-04", "2026-11-05",
        ])
        with self.assertRaisesRegex(ValueError, "no verificado"):
            add_bmv_sessions("2026-12-31", 5)

    def test_parser_en_vivo_comparte_extraccion_historica(self):
        from sistema_nucleo_walmex_prospectivo import fetch_and_verify_bmv_bulletin
        path = ROOT / "cache_boletines" / "boletin_20261028.html"
        with patch("urllib.request.urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value = path.read_bytes()
            bulletin = fetch_and_verify_bmv_bulletin("20261028")
        expected = self.raw[self.raw.fecha.eq("2026-10-28") & self.raw.ppp_bmv_mxn.notna()]
        for row in expected.itertuples():
            self.assertAlmostEqual(bulletin["cotizaciones"][row.emisora]["ppp"], row.ppp_bmv_mxn)
        self.assertNotIn("ASUR", bulletin["cotizaciones"])

    def test_parser_no_confunde_columna_omitida_con_precio(self):
        from sistema_nucleo_walmex_prospectivo import fetch_and_verify_bmv_bulletin
        found = 0
        for fecha in self.walmex[self.walmex.ppp_bmv_mxn.isna()].fecha:
            path = ROOT / "cache_boletines" / f"boletin_{fecha.replace('-', '')}.html"
            if not path.exists():
                continue
            with patch("urllib.request.urlopen") as request:
                request.return_value.__enter__.return_value.read.return_value = path.read_bytes()
                bulletin = fetch_and_verify_bmv_bulletin(fecha.replace("-", ""))
            self.assertNotIn("WALMEX", bulletin["cotizaciones"])
            found += 1
        self.assertGreater(found, 0)

    def test_media20_y_compatibilidad_control_congelado(self):
        win = self.walmex.tail(21).ppp_bmv_mxn.to_numpy()
        feats = calcular_features_ppp(win)
        self.assertAlmostEqual(feats[-1], win[-1] / np.mean(win[-20:]) - 1)
        self.assertNotAlmostEqual(feats[-1], win[-1] / np.mean(win) - 1)
        with zipfile.ZipFile(localizar_insumo("etapa9G_WALMEX_PPP_20261028T164002342440Z.zip")) as z:
            p = json.loads(z.read("resultados/parametros.json"))["logistica_balanceada"]
        logit = ((feats - p["media"]) / p["escala"]) @ p["coeficientes"] + p["intercepto"]
        self.assertAlmostEqual(1 / (1 + np.exp(-logit)), float(self.registro.iloc[0].prob_subida_h5), places=6)

    def test_ventana_rechaza_sesion_eliminada_y_corte_distinto(self):
        missing = self.walmex[~self.walmex.fecha.eq("2026-10-15")].tail(21)
        with self.assertRaisesRegex(ValueError, "Hueco"):
            validar_ventana_fechas(missing.fecha, "2026-10-28")
        with self.assertRaises(ValueError):
            validar_ventana_fechas(self.walmex.tail(21).fecha, "2026-10-29")

    def test_features_rechazan_nan_cero_e_infinito(self):
        for value in [np.nan, 0.0, np.inf]:
            win = self.walmex.tail(21).ppp_bmv_mxn.to_numpy().copy()
            win[10] = value
            with self.assertRaises(ValueError):
                calcular_features_ppp(win)

    def test_panel_comparte_formula_y_no_comprime_huecos(self):
        sub = self.walmex.tail(45).copy()
        feats = panel.extract_features_and_targets_for_issuer(sub, "WALMEX")
        today = feats[feats.fecha.eq("2026-10-28")].iloc[0]
        np.testing.assert_allclose(today[panel.FEATURE_NAMES].to_numpy(dtype=float), calcular_features_ppp(sub.tail(21).ppp_bmv_mxn))
        self.assertEqual(today.version_features, VERSION_FEATURES)
        missing = sub[~sub.fecha.eq("2026-10-15")]
        bad = panel.extract_features_and_targets_for_issuer(missing, "WALMEX")
        self.assertFalse(bad.fecha.eq("2026-10-28").any())
        # Aun si se renumeran incorrectamente las filas, manda el calendario.
        missing = sub[~sub.fecha.eq("2026-10-27")].copy()
        missing["posicion_sesion"] = np.arange(len(missing))
        result = panel.extract_features_and_targets_for_issuer(missing, "WALMEX")
        origin = result[result.fecha.eq("2026-10-20")].iloc[0]
        self.assertEqual(origin.fecha_objetivo_h5, "2026-10-27")
        self.assertFalse(origin.target_disponible)

    def test_purga_train_y_cierre_de_test(self):
        labels = pd.DataFrame({
            "fecha": ["2025-04-22", "2025-04-28", "2026-10-20", "2026-10-21"],
            "fecha_objetivo_h5": ["2025-04-29", "2025-05-06", "2026-10-27", "2026-10-28"],
            "periodo_oficial": ["TRAIN", "TRAIN", "TEST", "TEST"],
            "target_disponible": True,
        })
        tr, te = seleccionar_train_test(labels)
        self.assertEqual(tr.fecha.tolist(), ["2025-04-22"])
        self.assertEqual(te.fecha.tolist(), ["2026-10-20"])
        self.assertFalse(mascara_etiquetas_conocidas(labels, "2026-10-27").iloc[-1])

    def test_resolucion_exacta_aunque_falte_intermedia(self):
        series = self.series[~self.series.fecha.eq("2026-10-23")]
        res = diario.resolver_senales_fecha_exacta(self.senal_historica("2026-10-21"), series).iloc[0]
        self.assertEqual(res.estado_resolucion, "RESUELTA_VERIFICADA")
        self.assertEqual(res.fecha_resolucion_real, "2026-10-28")
        self.assertAlmostEqual(res.ppp_t5_mxn, 48.40)

    def test_objetivo_ausente_no_se_sustituye_ni_conserva_metricas(self):
        signal = self.senal_historica("2026-10-20")
        signal["acierto"] = 1.0
        signal["brier_individual"] = 0.0
        series = self.series[~self.series.fecha.eq("2026-10-27")]
        res = diario.resolver_senales_fecha_exacta(signal, series).iloc[0]
        self.assertEqual(res.estado_resolucion, "NO_RESOLUBLE_PPP_OBJETIVO_AUSENTE")
        self.assertTrue(pd.isna(res.brier_individual))
        self.assertEqual(res.fecha_resolucion_real, "")

    def test_fecha_objetivo_erronea_y_senales_anuladas(self):
        signal = self.senal_historica("2026-10-20")
        signal["fecha_objetivo_h5"] = "2026-10-28"
        res = diario.resolver_senales_fecha_exacta(signal, self.series)
        self.assertEqual(res.iloc[0].estado_resolucion, "ERROR_FECHA_OBJETIVO")
        signal["estado_validez"] = "ANULADA_FECHAS_REPORTE_NO_DOCUMENTADAS"
        self.assertEqual(diario.resolver_senales_fecha_exacta(signal, self.series).iloc[0].estado_resolucion, "ANULADA_NO_EVALUABLE")

    def test_actualizacion_documenta_dias_no_capturados_y_ausencia(self):
        original = self.series[self.series.fecha.le("2026-10-23")]
        quote = self.walmex[self.walmex.fecha.eq("2026-10-28")].iloc[0]
        bulletin = {"fecha_boletin": "2026-10-28", "cotizaciones": {"WALMEX": {"ppp": quote.ppp_bmv_mxn}}, "url_fuente": quote.url_fuente, "sha256_html": quote.sha256_boletin}
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            path = Path(tmp) / "serie.csv"
            original.to_csv(path, index=False)
            result = diario.init_or_update_master_ppp_series(bulletin, path)
            holes = result[result.fecha.isin(["2026-10-26", "2026-10-27"])]
            self.assertEqual(len(holes), 2)
            self.assertTrue(holes.ppp_bmv_mxn.isna().all())
            self.assertTrue((~holes.precio_apto_calculo).all())
            pd.testing.assert_frame_equal(result, diario.init_or_update_master_ppp_series(bulletin, path), check_dtype=False)
            bulletin["cotizaciones"] = {}
            original.to_csv(path, index=False)
            absent = diario.init_or_update_master_ppp_series(bulletin, path)
            self.assertTrue(pd.isna(absent.iloc[-1].ppp_bmv_mxn))

    def test_trazabilidad_no_inventa_emisiones_y_es_idempotente(self):
        original = self.registro.copy()
        annotated = agregar_trazabilidad(original)
        pd.testing.assert_frame_equal(annotated[original.columns], original, check_dtype=False)
        pd.testing.assert_frame_equal(agregar_trazabilidad(annotated), annotated)
        unknown = annotated.timestamp_emision_utc.str.startswith("NO_")
        self.assertTrue(annotated.loc[unknown, "fecha_emision_real"].isna().all())

    def test_elasticnet_l2_coincide_con_irls_y_no_es_constante(self):
        feats = panel.extract_features_and_targets_for_issuer(self.raw[self.raw.emisora.eq("GMEXICO")].tail(350), "GMEXICO")
        eligible = feats[feats.target_disponible]
        X, y = eligible[gm.FEATURE_NAMES].to_numpy(), eligible.target_y.to_numpy()
        p_lr, _ = gm.fit_predict_logistic(X, y, X, C=.5)
        p_en, beta = gm.fit_predict_elasticnet(X, y, X, C=.5, l1_ratio=0)
        np.testing.assert_allclose(p_en, p_lr, atol=2e-5)
        self.assertGreater(np.linalg.norm(beta[1:]), 0)

    def test_emision_completa_y_purga_de_fila_futura(self):
        from experimento_ajuste_dividendos import load_data, build_adjusted_features_and_indicator
        data = load_data()
        s9d, el9d, divs9d, *rest = data
        divs9g = data[-1]
        div_map = dict(zip(divs9d.fecha_ex.astype(str), divs9d.dividendo_documentado.astype(float)))
        div_map.update(dict(zip(divs9g.fecha_ex.astype(str), divs9g.dividendo_documentado.astype(float))))
        merged = build_adjusted_features_and_indicator(s9d, el9d, div_map)
        known = merged[merged.apto_features_ajustadas & merged.apto_label_h5 & merged.soporte_dentro_del_bloque]
        future = known.iloc[[-1]].copy()
        future["fecha"] = "2026-10-28"
        future["fecha_fin_label_h5"] = "2026-11-05"
        merged = pd.concat([merged, future], ignore_index=True)
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            path = Path(tmp) / "senales.csv"
            signals = diario.generate_daily_signals_for_date("2026-10-28", self.series, merged, pd.DataFrame(), path, div_map=div_map)
            self.assertEqual(len(signals), 3)
            self.assertEqual(signals.n_entrenamiento.iloc[1], len(known))
            self.assertTrue(signals.fecha_corte_entrenamiento.le("2026-10-28").all())
            self.assertTrue(signals.version_features.eq(VERSION_FEATURES).all())
            self.assertAlmostEqual(signals.prob_subida_h5.iloc[0], .535924, places=6)

    def test_marcador_excluye_emision_sin_timestamp_o_posterior_al_objetivo(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            path, score = Path(tmp) / "senales.csv", Path(tmp) / "score.csv"
            signal = self.senal_historica("2026-10-20")
            signal["timestamp_emision_utc"] = "2026-10-29T16:31:00+00:00"
            signal.to_csv(path, index=False)
            res, board = diario.resolve_matured_signals_and_update_scoreboard(self.series, path, score)
            self.assertEqual(res.iloc[0].estado_resolucion, "RESUELTA_VERIFICADA")
            self.assertFalse(res.iloc[0].apta_evaluacion_prospectiva)
            self.assertEqual(board.senales_resueltas.sum(), 0)
            self.assertTrue(board.brier_prospectivo.isna().all())

    def test_gbdt_ajusta_residuos_reales_y_reduce_perdida_train(self):
        feats = panel.extract_features_and_targets_for_issuer(self.raw[self.raw.emisora.eq("GMEXICO")].tail(350), "GMEXICO")
        eligible = feats[feats.target_disponible]
        X, y = eligible[gm.FEATURE_NAMES].to_numpy(), eligible.target_y.to_numpy()
        model = gm.PureNumPyGBDT(n_estimators=10).fit(X, y)
        p = model.predict_proba(X)
        self.assertLess(np.mean((p - y) ** 2), np.mean((y.mean() - y) ** 2))
        self.assertTrue(any(leaf < 0 for leaf in model.trees[0].predict(X)))

    def test_contingencia_secundaria_y_reconciliacion_primaria(self):
        original = self.series[self.series.fecha.le("2026-11-03")].copy()
        sec_bulletin = {
            "fecha_boletin": "2026-11-04",
            "origen_fuente": "SECUNDARIA_CONTINGENCIA",
            "estado_captura": "CONTINGENCIA_FUENTE_SECUNDARIA",
            "cotizaciones": {"WALMEX": {"ppp": 52.10, "ultimo": 52.22, "anterior": 50.04, "variacion_ppp_vs_anterior_pct": 4.12}},
            "url_fuente": "https://query1.finance.yahoo.com/v8/finance/chart/WALMEX.MX?date=2026-11-04#contingencia_bmv_404",
            "sha256_html": "sec_hash_1104",
        }
        prim_bulletin = {
            "fecha_boletin": "2026-11-04",
            "origen_fuente": "PRIMARIA_BOLETIN_OFICIAL_BMV",
            "estado_captura": "PPP_PUBLICADO_VERIFICADO",
            "cotizaciones": {"WALMEX": {"ppp": 52.18, "ultimo": 52.22, "anterior": 50.04, "variacion_ppp_vs_anterior_pct": 4.28}},
            "url_fuente": "https://www.bmv.com.mx/docs-pub/rss/boletin20261104.html",
            "sha256_html": "prim_hash_1104",
        }
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            s_path = Path(tmp) / "serie.csv"
            m_path = Path(tmp) / "multi.csv"
            original.to_csv(s_path, index=False)
            res_sec = diario.init_or_update_master_ppp_series(sec_bulletin, s_path)
            self.assertEqual(res_sec.iloc[-1].estado, "CONTINGENCIA_FUENTE_SECUNDARIA")
            self.assertAlmostEqual(float(res_sec.iloc[-1].ppp_bmv_mxn), 52.10)

            # En el siguiente dia (20261105), la cola debe incluir automaticamente 20261104 por ser secundaria + 20261105
            cola = diario.obtener_cola_fechas_reconciliacion("20261105", s_path, m_path)
            self.assertEqual(cola, ["20261104", "20261105"])

            # Al llegar el boletin primario de 2026-11-04, debe promoverse y sobreescribir a la secundaria sin error
            res_prim = diario.init_or_update_master_ppp_series(prim_bulletin, s_path)
            self.assertEqual(res_prim.iloc[-1].estado, "PPP_PUBLICADO_VERIFICADO")
            self.assertAlmostEqual(float(res_prim.iloc[-1].ppp_bmv_mxn), 52.18)

            # Una vez promovida 20261104 a primaria, la cola para 20261105 ya solo pide 20261105
            cola_post = diario.obtener_cola_fechas_reconciliacion("20261105", s_path, m_path)
            self.assertEqual(cola_post, ["20261105"])


if __name__ == "__main__":
    unittest.main()
