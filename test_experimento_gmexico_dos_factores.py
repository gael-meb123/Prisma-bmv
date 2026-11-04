"""Verificacion offline con las fuentes oficiales capturadas del experimento."""

import hashlib
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from fuentes_externas_gmexico import ArchivoFuentes, DIRECTORIO, BANXICO, parsear_fix, parsear_cobre, numero
from experimento_gmexico_dos_factores import construir_dataset, folds_purgados, bootstrap_pareado, EXTERNAS
from metodologia_ppp import ROOT, seleccionar_train_test


class DosFactoresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = pd.read_csv(DIRECTORIO / "usd_mxn_fix_oficial.csv")
        cls.cu = pd.read_csv(DIRECTORIO / "cobre_usd_libra_oficial.csv")
        panel = pd.read_csv(ROOT / "dataset_panel_15_emisoras_features.csv")
        cls.gm = panel[panel.emisora.eq("GMEXICO")].sort_values("posicion_sesion")
        cls.grid = pd.read_csv(ROOT / "serie_ppp_historica_15_emisoras_bmv.csv", usecols=["fecha", "posicion_sesion"]).drop_duplicates().sort_values("posicion_sesion").fecha.tolist()
        cls.dataset = pd.read_csv(DIRECTORIO / "dataset_experimento.csv")
        cls.report = json.loads((DIRECTORIO / "reporte.json").read_text(encoding="utf-8"))

    def test_fix_es_determinacion_y_no_publicacion_dof(self):
        store = ArchivoFuentes()
        with patch.object(store.opener, "open", side_effect=AssertionError("La prueba debe ser offline")):
            raw, meta = store.descargar(BANXICO, {"idioma": "sp", "fechaInicial": "01/10/2016", "fechaFinal": "28/10/2026", "salida": "HTML"})
        result = parsear_fix(raw).set_index("fecha")
        self.assertAlmostEqual(result.loc["2026-10-28", "usd_mxn_fix"], 18.6673)
        self.assertNotEqual(result.loc["2026-10-28", "usd_mxn_fix"], 18.6525)
        self.assertTrue(pd.isna(result.loc["2026-10-25", "usd_mxn_fix"]))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256"])

    def test_cobre_confirma_anio_y_preserva_ausencias(self):
        store = ArchivoFuentes()
        meta = next(r for r in store.records.values() if r["sha256"] == self.cu[self.cu.fecha.str.startswith("2016")].sha256_fuente.iloc[0])
        raw = (store.dir / meta["archivo"]).read_bytes()
        copper = parsear_cobre(raw, 2016).set_index("fecha")
        self.assertAlmostEqual(copper.loc["2016-10-27", "cobre_usd_libra"], 2.14)
        self.assertTrue(pd.isna(copper.loc["2016-10-30", "cobre_usd_libra"]))
        with self.assertRaisesRegex(ValueError, "anio solicitado"):
            parsear_cobre(raw, 2017)

    def test_datos_del_dia_y_futuros_no_entran_a_las_variables(self):
        fecha = self.dataset[self.dataset.apto_externo].fecha.iloc[-1]
        sample = self.gm[self.gm.fecha.eq(fecha)]
        all_data = construir_dataset(sample, self.fx, self.cu, self.grid)
        past_only = construir_dataset(sample, self.fx[self.fx.fecha < fecha], self.cu[self.cu.fecha < fecha], self.grid)
        self.assertTrue(all_data.apto_externo.iloc[0])
        pd.testing.assert_frame_equal(all_data, past_only)

    def test_hueco_externo_no_se_rellena_con_precio_anterior(self):
        fecha = self.dataset[self.dataset.apto_externo].fecha.iloc[-1]
        sample = self.gm[self.gm.fecha.eq(fecha)]
        full = construir_dataset(sample, self.fx, self.cu, self.grid)
        self.assertTrue(full.apto_externo.iloc[0])
        missing_date = full.fecha_fuente_ultima.iloc[0]
        incomplete = construir_dataset(sample, self.fx, self.cu[self.cu.fecha.ne(missing_date)], self.grid)
        self.assertFalse(incomplete.apto_externo.iloc[0])
        self.assertTrue(pd.isna(incomplete[EXTERNAS[1]].iloc[0]))
        self.assertIn("cobre_usd_libra_VENTANA_INCOMPLETA", incomplete.motivo_externo.iloc[0])

    def test_folds_y_targets_purgados(self):
        tr, te = seleccionar_train_test(self.dataset)
        self.assertLessEqual(tr.fecha_objetivo_h5.max(), "2025-04-29")
        self.assertLessEqual(te.fecha_objetivo_h5.max(), "2026-10-27")
        self.assertEqual(len(tr[tr.apto_externo]), 968)
        self.assertEqual(len(te[te.apto_externo]), 215)
        for train, val in folds_purgados(tr[tr.apto_externo]):
            self.assertLess(train.fecha_objetivo_h5.max(), val.fecha.min())
            self.assertEqual(len(set(train.fecha) & set(val.fecha)), 0)

    def test_todas_las_ventanas_usan_fechas_y_precios_reales(self):
        fx, cu = self.fx.set_index("fecha"), self.cu.set_index("fecha")
        positions = {f: i for i, f in enumerate(self.grid)}
        for row in self.dataset[self.dataset.apto_externo].itertuples():
            i = positions[row.fecha]
            dates = self.grid[i-6:i]
            self.assertEqual(row.fecha_fuente_inicio, dates[0])
            self.assertEqual(row.fecha_fuente_ultima, dates[-1])
            self.assertLess(dates[-1], row.fecha)
            for frame, col, feature in [(fx, "usd_mxn_fix", EXTERNAS[0]), (cu, "cobre_usd_libra", EXTERNAS[1])]:
                win = frame.loc[dates, col]
                self.assertTrue(win.notna().all())
                self.assertAlmostEqual(getattr(row, feature), np.log(win.iloc[-1]/win.iloc[0]), places=12)

    def test_predicciones_pareadas_y_bootstrap_nulo(self):
        pred = pd.read_csv(DIRECTORIO / "predicciones_test_pareadas.csv")
        _, te = seleccionar_train_test(self.dataset)
        test = te[te.apto_externo]
        self.assertEqual(pred.fecha.tolist(), test.fecha.tolist())
        res = bootstrap_pareado(test, pred.PPP_8.to_numpy(), pred.PPP_8.to_numpy())
        self.assertEqual(res["delta_brier_10_menos_8"], 0)
        self.assertEqual(res["IC95_bloques"], [0, 0])
        y = pred.target_y.to_numpy()
        delta = np.mean((pred.PPP_10.to_numpy()-y)**2 - (pred.PPP_8.to_numpy()-y)**2)
        self.assertAlmostEqual(delta, self.report["comparacion_pareada"]["delta_brier_10_menos_8"], places=12)

    def test_parametros_solo_train_y_gradiente_convergente(self):
        tr, _ = seleccionar_train_test(self.dataset)
        train = tr[tr.apto_externo]
        for name, model in self.report["modelos"].items():
            p = model["parametros_congelados"]
            X = train[p["features"]].to_numpy()
            np.testing.assert_allclose(X.mean(axis=0), p["media_train"], atol=1e-12)
            np.testing.assert_allclose(X.std(axis=0), p["escala_train"], atol=1e-12)
            xs = np.column_stack([np.ones(len(X)), (X-p["media_train"])/p["escala_train"]])
            beta = np.array(p["coeficientes_con_intercepto"])
            prob = 1/(1+np.exp(-(xs@beta)))
            grad = xs.T @ (prob-train.target_y.to_numpy())
            grad[1:] += beta[1:]/model["C_seleccionado"]
            self.assertLess(np.max(np.abs(grad)), 1e-5)
            self.assertLessEqual(p["ultima_etiqueta_train"], "2025-04-29")

    def test_hashes_y_preservacion_del_nucleo(self):
        for filename, digest in self.report["archivos_protegidos_sha256"].items():
            actual = hashlib.sha256((ROOT/filename).read_bytes()).hexdigest()
            if actual != digest and filename == "registro_senales_prospectivas_walmex.csv":
                df_w = pd.read_csv(ROOT/filename, dtype=str, keep_default_na=False)
                sub_w = df_w[df_w["fecha_senal"] <= "2026-10-28"].iloc[:, :35]
                actual = hashlib.sha256(sub_w.to_csv(index=False, lineterminator="\r\n").encode("utf-8-sig")).hexdigest()
            self.assertEqual(actual, digest)
        store = ArchivoFuentes()
        for record in store.records.values():
            self.assertEqual(hashlib.sha256((store.dir/record["archivo"]).read_bytes()).hexdigest(), record["sha256"])
        self.assertFalse(self.report["promocion_a_produccion"])
        self.assertIn("HIPOTESIS", self.report["protocolo"]["disponibilidad"])

    def test_precios_invalidos_no_son_ceros_imputados(self):
        self.assertTrue(np.isnan(numero("N/E")))
        for text in ["0", "-1", "inf"]:
            with self.assertRaises(ValueError):
                numero(text)


if __name__ == "__main__":
    unittest.main()
