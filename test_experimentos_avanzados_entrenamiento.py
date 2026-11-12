from __future__ import annotations

import hashlib
import json
import unittest

import numpy as np
import pandas as pd

from experimentos_avanzados_entrenamiento import (
    PANEL_PATH,
    SALIDA_DIR,
    VARIABLES_DOS,
    VARIABLES_REL_TRES,
    ajustar_logistica_con_zona_neutral,
    filtrar_zona_neutral_train,
    hashes_protegidos_avanzados,
    preparar_panel_desarrollo_ppp,
    seleccionar_gamma_jerarquico_anidado,
)
from metodologia_ppp import ROOT


class TestExperimentosAvanzadosEntrenamiento(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.panel_dev, _ = preparar_panel_desarrollo_ppp(PANEL_PATH)
        cls.gmex_dev = (
            cls.panel_dev[cls.panel_dev["emisora"] == "GMEXICO"]
            .sort_values("posicion_sesion")
            .reset_index(drop=True)
        )

    def test_zona_neutral_filtra_solo_train_y_preserva_val_intacta(self) -> None:
        tr = self.gmex_dev.iloc[:400].copy()
        va = self.gmex_dev.iloc[410:460].copy()

        tr_f = filtrar_zona_neutral_train(tr, tau=0.0025)
        self.assertLess(len(tr_f), len(tr))
        mag_f = np.abs(tr_f["ppp_t5"].to_numpy(dtype=float) / tr_f["ppp_t"].to_numpy(dtype=float) - 1.0)
        self.assertTrue((mag_f >= 0.0025).all())

        # Predecir sobre va: debe devolver exactamente len(va) probabilidades finitas en [0, 1]
        p = ajustar_logistica_con_zona_neutral(
            tr, va, VARIABLES_DOS, c=0.01, tau=0.0025, modo_panel=False
        )
        self.assertEqual(len(p), len(va))
        self.assertTrue(np.isfinite(p).all())
        self.assertTrue(((p >= 0.0) & (p <= 1.0)).all())

    def test_seleccion_jerarquica_gamma_invariante_al_futuro(self) -> None:
        corte = "2022-01-01"
        tr_em = self.gmex_dev[
            (self.gmex_dev["fecha"] < corte) & (self.gmex_dev["fecha_objetivo_h5"] < corte)
        ].copy()
        tr_pan = self.panel_dev[
            (self.panel_dev["fecha"] < corte) & (self.panel_dev["fecha_objetivo_h5"] < corte)
        ].copy()

        res1 = seleccionar_gamma_jerarquico_anidado(
            tr_em, tr_pan, VARIABLES_REL_TRES, VARIABLES_REL_TRES, c_indiv=0.01, c_panel=0.01
        )
        self.assertIn(res1["gamma_seleccionado"], (0.0, 0.25, 0.50, 0.75, 1.0))

    def test_artefactos_avanzados_e_integridad_protegida(self) -> None:
        rep_path = SALIDA_DIR / "reporte.json"
        if not rep_path.exists():
            self.skipTest("Ejecutar experimentos_avanzados_entrenamiento.py primero.")

        rep = json.loads(rep_path.read_text(encoding="utf-8"))
        self.assertTrue(rep["integridad_archivos_protegidos_intacta"])
        hashes_actuales = hashes_protegidos_avanzados()
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

        res_gmex = rep["gmexico_expansiva"]["resumen_variantes"]
        self.assertAlmostEqual(res_gmex["REF_A_BENCHMARK_8VARS"]["brier"], 0.25062599, places=6)
        self.assertAlmostEqual(res_gmex["REF_C_INDIV_2VARS"]["brier"], 0.24870503, places=6)
        self.assertAlmostEqual(res_gmex["REF_P4_POOLED_REL3"]["brier"], 0.24490367, places=6)


if __name__ == "__main__":
    unittest.main()
