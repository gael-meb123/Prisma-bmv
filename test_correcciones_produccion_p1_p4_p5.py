"""
Tests de las correcciones de producción P1 (calendario BMV), P4 (pre-registro
append-only) y P5 (errores visibles) en `lambda_function_con_ia.py`.
"""

import datetime
import io
import json
import unittest
from unittest import mock

import pandas as pd

import lambda_function_con_ia as lf
from metodologia_ppp import FERIADOS_BMV_2026, add_bmv_sessions


class _ErrorS3(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3:
    def __init__(self, objetos=None, errores_get=None):
        self.objetos = dict(objetos or {})
        self.errores_get = dict(errores_get or {})
        self.puts = []

    def get_object(self, Bucket, Key):
        if Key in self.errores_get:
            raise _ErrorS3(self.errores_get[Key])
        if Key not in self.objetos:
            raise _ErrorS3("NoSuchKey")
        return {"Body": io.BytesIO(self.objetos[Key])}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.puts.append(Key)
        self.objetos[Key] = Body


def _fila(id_s, fecha, h5, clase, prob, ppp_t, em="WALMEX", **extra):
    base = {
        "id_senal_g2": id_s, "fecha_senal": fecha, "fecha_objetivo_h5": h5, "emisora": em,
        "modelo_g2": "G2_V4_POOLED_DM5_REL_CORTO_PLAZO", "ppp_base_t": ppp_t,
        "probabilidad_subida": prob, "prediccion_clase": clase,
        "estado_resolucion": "PENDIENTE_T+5", "sesiones_transcurridas": 0,
        "fecha_parcial_reciente": "PENDIENTE", "ppp_parcial_reciente": None,
        "retorno_parcial_pct": None, "acierto_parcial_en_curso": None,
        "ppp_t5_observado": None, "target_y_observado": None,
        "acierto_direccional_t5": None, "brier_observado_t5": None,
        "timestamp_emision_utc": "2026-11-06T00:00:00+00:00",
    }
    base.update(extra)
    return base


class TestP1CalendarioBMV(unittest.TestCase):
    def test_feriados_2026_identicos_a_metodologia(self):
        self.assertEqual(set(lf.FERIADOS_BMV_2026), set(FERIADOS_BMV_2026))

    def test_paridad_fecha_objetivo_con_add_bmv_sessions_todo_2026(self):
        d = datetime.date(2026, 1, 2)
        n = 0
        while d <= datetime.date(2026, 12, 17):
            iso = d.isoformat()
            if lf.es_sesion_bmv(iso):
                self.assertEqual(lf.calcular_fecha_h5(iso), add_bmv_sessions(iso, 5), iso)
                n += 1
            d += datetime.timedelta(days=1)
        self.assertGreater(n, 230)

    def test_casos_criticos(self):
        self.assertEqual(lf.calcular_fecha_h5("2026-10-28"), "2026-11-05")  # salta 02-nov
        self.assertEqual(lf.calcular_fecha_h5("2026-11-09"), "2026-11-17")  # salta 16-nov
        self.assertFalse(lf.es_sesion_bmv("2026-11-16"))
        self.assertFalse(lf.es_sesion_bmv("2026-11-07"))

    def test_handler_no_ejecuta_en_feriado(self):
        s3 = FakeS3()
        with mock.patch.object(lf, "boto3") as b3:
            b3.client.return_value = s3
            res = lf.lambda_handler({"fecha": "2026-11-16"}, None)
        self.assertEqual(json.loads(res["body"])["estado"], "SIN_SESION_BMV")
        self.assertEqual(s3.puts, [])


class TestP4PreRegistroInmutable(unittest.TestCase):
    def test_emision_inmutable_y_resolucion_actualizada(self):
        prev = pd.DataFrame([_fila("S1", "2026-11-06", "2026-11-13", 1, 0.56, 50.0)])
        nueva = pd.DataFrame([_fila(
            "S1", "2026-11-06", "2026-11-13", 0, 0.41, 50.0,
            estado_resolucion="RESUELTA_OFICIAL_T5", ppp_t5_observado=52.0, target_y_observado=1,
            acierto_direccional_t5=False, brier_observado_t5=0.3481,
            timestamp_emision_utc="2026-11-20T00:00:00+00:00",
        ), _fila("S2", "2026-11-09", "2026-11-17", 1, 0.6, 51.0)])
        comb = lf.fusionar_gold_append_only(prev, nueva).set_index("id_senal_g2")
        self.assertEqual(len(comb), 2)
        self.assertAlmostEqual(float(comb.at["S1", "probabilidad_subida"]), 0.56)
        self.assertEqual(int(comb.at["S1", "prediccion_clase"]), 1)
        self.assertEqual(comb.at["S1", "timestamp_emision_utc"], "2026-11-06T00:00:00+00:00")
        self.assertEqual(comb.at["S1", "estado_resolucion"], "RESUELTA_OFICIAL_T5")
        # Acierto recalculado con la predicción ORIGINAL (clase 1, y=1)
        self.assertTrue(comb.at["S1", "acierto_direccional_t5"])
        self.assertAlmostEqual(float(comb.at["S1", "brier_observado_t5"]), round((0.56 - 1) ** 2, 6))

    def test_resolucion_de_pendientes_y_contingencia(self):
        gold = pd.DataFrame([
            _fila("A", "2026-11-03", "2026-11-10", 1, 0.55, 100.0),
            _fila("B", "2026-11-04", "2026-11-11", 0, 0.45, 100.0),
            _fila("C", "2026-11-09", "2026-11-16", 1, 0.6, 100.0),  # objetivo en feriado
        ])
        serie = pd.DataFrame([
            {"fecha": "2026-11-03", "emisora": "WALMEX", "ppp_bmv_mxn": 100.0, "estado_captura": "PPP_PUBLICADO_VERIFICADO"},
            {"fecha": "2026-11-04", "emisora": "WALMEX", "ppp_bmv_mxn": 100.0, "estado_captura": "CONTINGENCIA_FUENTE_SECUNDARIA"},
            {"fecha": "2026-11-10", "emisora": "WALMEX", "ppp_bmv_mxn": 103.0, "estado_captura": "PPP_PUBLICADO_VERIFICADO"},
            {"fecha": "2026-11-11", "emisora": "WALMEX", "ppp_bmv_mxn": 99.0, "estado_captura": "PPP_PUBLICADO_VERIFICADO"},
        ])
        out = lf.actualizar_resolucion_pendientes(gold, serie).set_index("id_senal_g2")
        self.assertEqual(out.at["A", "estado_resolucion"], "RESUELTA_OFICIAL_T5")
        self.assertEqual(int(out.at["A", "target_y_observado"]), 1)
        self.assertTrue(out.at["A", "acierto_direccional_t5"])
        self.assertEqual(out.at["B", "estado_resolucion"], "PENDIENTE_RECONCILIACION")
        self.assertEqual(out.at["C", "fecha_objetivo_h5"], "2026-11-17")


class TestP5ErroresVisibles(unittest.TestCase):
    def test_falla_lectura_gold_no_sobrescribe_y_lanza_error(self):
        s3 = FakeS3(errores_get={lf.__dict__.get("_GOLD_KEY", "gold/senales_g2/registro_senales_prospectivas_panel_g2.csv"): "AccessDenied"})
        df_sil = pd.DataFrame([{
            "fecha": "2026-11-06", "emisora": "WALMEX", "ppp_bmv_mxn": 53.0,
            "estado_captura": "PPP_PUBLICADO_VERIFICADO",
        }])
        with mock.patch.object(lf, "boto3") as b3, \
                mock.patch.object(lf, "_procesar_fecha_en_s3", return_value=(df_sil, {"fecha": "2026-11-06"})):
            b3.client.return_value = s3
            with self.assertRaises(RuntimeError) as ctx:
                lf.lambda_handler({"fecha": "2026-11-06"}, None)
        self.assertIn("ERROR_PRISMA_CRITICO", str(ctx.exception))
        self.assertNotIn("gold/senales_g2/registro_senales_prospectivas_panel_g2.csv", s3.puts)
        # La serie unificada se guarda aunque falle la capa Gold
        self.assertIn("silver/serie_unificada_reciente.csv", s3.puts)

    def test_sin_datos_en_dia_habil_lanza_error(self):
        s3 = FakeS3()
        with mock.patch.object(lf, "boto3") as b3, \
                mock.patch.object(lf, "_procesar_fecha_en_s3", side_effect=RuntimeError("sin datos")):
            b3.client.return_value = s3
            with self.assertRaises(RuntimeError):
                lf.lambda_handler({"fecha": "2026-11-06"}, None)


class TestP2P3P6P7P8Completa(unittest.TestCase):
    def test_p3_ajuste_dividendos_en_resolucion(self):
        df_ev = pd.DataFrame([{
            "emisora": "WALMEX",
            "fecha_ex": "2026-11-05",
            "tipo": "DIVIDENDO",
            "monto_mxn": 2.0,
            "factor": 0.96,
            "fuente": "TEST",
        }])
        # Sin ajuste: ppp_t=50.0, ppp_t5=49.0 -> parecería caída (y=0)
        # Con ajuste por dividendo (factor=0.96): ppp_t5_adj = 49.0 / 0.96 = 51.0417 > 50.0 -> subida real (y=1)
        ppp_adj = lf.calcular_ppp_t5_ajustado_dividendo("WALMEX", "2026-10-29", "2026-11-06", 49.0, df_ev)
        self.assertGreater(ppp_adj, 50.0)
        gold = pd.DataFrame([_fila("D1", "2026-10-29", "2026-11-06", 1, 0.55, 50.0)])
        serie = pd.DataFrame([
            {"fecha": "2026-10-29", "emisora": "WALMEX", "ppp_bmv_mxn": 50.0, "estado_captura": "PPP_PUBLICADO_VERIFICADO"},
            {"fecha": "2026-11-06", "emisora": "WALMEX", "ppp_bmv_mxn": 49.0, "estado_captura": "PPP_PUBLICADO_VERIFICADO"},
        ])
        out = lf.actualizar_resolucion_pendientes(gold, serie, df_eventos=df_ev).set_index("id_senal_g2")
        self.assertEqual(out.at["D1", "estado_resolucion"], "RESUELTA_OFICIAL_T5")
        self.assertEqual(int(out.at["D1", "target_y_observado"]), 1)
        self.assertTrue(out.at["D1", "acierto_direccional_t5"])

    def test_p6_expiracion_contingencia_mayor_a_10_sesiones(self):
        gold = pd.DataFrame([_fila("C_OLD", "2026-10-01", "2026-10-08", 1, 0.55, 100.0)])
        serie = pd.DataFrame([
            {"fecha": "2026-10-01", "emisora": "WALMEX", "ppp_bmv_mxn": 100.0, "estado_captura": "PPP_PUBLICADO_VERIFICADO"},
            {"fecha": "2026-10-08", "emisora": "WALMEX", "ppp_bmv_mxn": 102.0, "estado_captura": "CONTINGENCIA_FUENTE_SECUNDARIA"},
            {"fecha": "2026-11-06", "emisora": "WALMEX", "ppp_bmv_mxn": 105.0, "estado_captura": "PPP_PUBLICADO_VERIFICADO"},
        ])
        out = lf.actualizar_resolucion_pendientes(gold, serie, max_sesiones_contingencia=10).set_index("id_senal_g2")
        self.assertEqual(out.at["C_OLD", "estado_resolucion"], "CONTINGENCIA_DEFINITIVA_EXCLUIDA")

    def test_p7_monitoreo_secuencial_gold_cusum_y_sprt(self):
        filas = [
            _fila(f"M_{i}", "2026-10-01", "2026-10-08", 1, 0.56, 100.0,
                  estado_resolucion="RESUELTA_OFICIAL_T5", target_y_observado=1)
            for i in range(5)
        ]
        mon = lf.calcular_monitoreo_secuencial_gold(pd.DataFrame(filas))
        self.assertIn("G2_V4_POOLED_DM5_REL_CORTO_PLAZO", mon)
        m_v4 = mon["G2_V4_POOLED_DM5_REL_CORTO_PLAZO"]
        self.assertEqual(m_v4["n_resueltas_oficial_t5"], 5)
        self.assertEqual(m_v4["aciertos_direccionales"], 5)
        self.assertGreater(m_v4["llr_nominal"], 0.0)
        self.assertFalse(m_v4["alarma_cusum_activa"])

    def test_p2_y_p8_campeon_f1_gap_y_metadatos_entrenamiento(self):
        res, _ = lf.inferir_modelos_g2(
            emisora="WALMEX", ret_10=0.01, ret_10_rel=0.005, vol_20=0.014,
            ret_1_rel=0.002, dm_5=0.004, dm_5_rel=0.001,
            gap_uh_ppp=0.0015, incluir_challenger_f1=True,
        )
        self.assertIn("G2_V4_F1_GAP", res)
        self.assertEqual(lf.META_ENTRENAMIENTO_G2["G2_V1_POOLED_REL3_CALIBRADO"]["n_train_panel"], 8122)
        self.assertEqual(lf.META_ENTRENAMIENTO_G2["G2_V4_POOLED_DM5_REL_CORTO_PLAZO"]["n_train_panel"], 9679)
        self.assertEqual(lf.MAPA_SECTOR_EMISORA["WALMEX"], "Comercio y autoservicio")


if __name__ == "__main__":
    unittest.main()
