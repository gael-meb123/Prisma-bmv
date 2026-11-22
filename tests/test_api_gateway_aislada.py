import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

archivo = Path(__file__).resolve().parent.parent / "infra/api_gateway_aislada/handler.py"
spec = importlib.util.spec_from_file_location("api_gateway_aislada", archivo)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class Tabla:
    def __init__(self, item=None, falla=False):
        self.item, self.falla, self.calls = item, falla, []

    def get_item(self, **kwargs):
        self.calls.append(kwargs)
        if self.falla:
            raise RuntimeError("secreto no debe salir")
        return {"Item": self.item}


def evento(claims=None):
    return {"routeKey": "GET /api/me", "requestContext": {"authorizer": {"jwt": {"claims": claims or {}}}}}


class ApiAisladaTest(unittest.TestCase):
    def test_salud_y_rutas_desconocidas(self):
        self.assertEqual(api.ejecutar({"routeKey": "GET /health"}, Tabla())["statusCode"], 200)
        self.assertEqual(api.ejecutar({"routeKey": "GET /api/mercado"}, Tabla())["statusCode"], 404)

    def test_rechaza_token_y_perfil_ausente_o_invalido(self):
        self.assertEqual(api.ejecutar(evento(), Tabla())["statusCode"], 401)
        self.assertEqual(api.ejecutar(evento({"sub": "u", "token_use": "id"}), Tabla())["statusCode"], 401)
        e = evento({"sub": "u", "token_use": "access"})
        self.assertEqual(api.ejecutar(e, Tabla())["statusCode"], 403)
        self.assertEqual(api.ejecutar(e, Tabla({"rol": "admin", "plan": "inventado"}))["statusCode"], 403)

    def test_perfil_usa_sub_verificado_y_permiso_por_plan(self):
        t = Tabla({"rol": "user", "plan": "explorer", "email": "x@example.org", "nombre": "X"})
        r = api.ejecutar(evento({"sub": "abc", "token_use": "access"}), t)
        self.assertEqual(t.calls, [{"Key": {"sub": "abc"}, "ConsistentRead": True}])
        self.assertEqual(json.loads(r["body"])["emisoras"], ["WALMEX"])

    def test_error_de_tabla_no_filtra_datos(self):
        r = api.ejecutar(evento({"sub": "u", "token_use": "access"}), Tabla(falla=True))
        self.assertEqual(r["statusCode"], 503)
        self.assertNotIn("secreto", r["body"])

    def test_senales_bloqueadas_exigen_acceso_y_no_exponen_gold(self):
        t = Tabla({"rol": "user", "plan": "explorer", "email": "x@example.org", "nombre": "X"})
        rutas = ["GET /api/senales/panel", "GET /api/terminal/senal", "GET /api/terminal/seguimiento",
                 "GET /api/terminal/consenso", "GET /api/terminal/marcador"]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                e = evento({"sub": "u", "token_use": "access"})
                e["routeKey"] = ruta
                e["queryStringParameters"] = {"emisora": "WALMEX"}
                r = api.ejecutar(e, t)
                self.assertEqual(r["statusCode"], 503)
                self.assertIn("pendientes de validación", json.loads(r["body"])["detail"])
                e["queryStringParameters"]["emisora"] = "AMX"
                self.assertEqual(api.ejecutar(e, t)["statusCode"], 403)
                e["requestContext"]["authorizer"]["jwt"]["claims"]["token_use"] = "id"
                self.assertEqual(api.ejecutar(e, t)["statusCode"], 401)
        e = evento({"sub": "u", "token_use": "access"})
        e["routeKey"] = "GET /api/terminal/seguimiento"
        self.assertEqual(api.ejecutar(e, t)["statusCode"], 422)


class MercadoTest(unittest.TestCase):
    CSV = ("fecha,emisora,serie,estado_captura,ppp_bmv_mxn,anterior_bmv_mxn,variacion_ppp_vs_anterior_pct\n"
           "2026-11-17,WALMEX,*,PPP_PUBLICADO_VERIFICADO,42,40,5\n"
           "2026-11-17,AMX,B,CONTINGENCIA_FUENTE_SECUNDARIA,23,22,4.5\n"
           "2026-11-17,GRUMA,B,NO_PUBLICADO_EN_BOLETIN_RSS_DEL_DIA,,,\n")

    class S3:
        def __init__(self, data):
            self.data = data

        def get_object(self, **kwargs):
            return {"Body": io.BytesIO(self.data.encode()), "ContentLength": len(self.data),
                    "LastModified": "2026-11-18"}

    def llamar(self, ruta, data=CSV, fecha=None):
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k"}):
            return api.ejecutar({"routeKey": ruta, "queryStringParameters": {"fecha": fecha}},
                                Tabla(), self.S3(data))

    def test_cobertura_y_contingencia_no_se_presenta_como_ppp(self):
        r = self.llamar("GET /api/mercado/resumen")
        self.assertEqual(r["statusCode"], 200)
        body = json.loads(r["body"])
        self.assertEqual(body["kpis"]["total_emisoras"], 3)
        self.assertEqual(body["kpis"]["total_verificadas"], 1)
        self.assertEqual(body["cotizaciones"][0]["ppp_bmv_mxn"], 42)
        self.assertIsNone(body["cotizaciones"][1]["ppp_bmv_mxn"])
        self.assertIsNone(body["cotizaciones"][1]["variacion_pct"])
        self.assertIn("no acredita universo completo", body["fuente"]["cobertura"])

    def test_fechas_ausentes_y_duplicados(self):
        self.assertEqual(self.llamar("GET /api/mercado/resumen", fecha="2020-01-01")["statusCode"], 404)
        self.assertEqual(self.llamar("GET /api/mercado/fechas")["statusCode"], 200)
        self.assertEqual(self.llamar("GET /api/mercado/resumen", self.CSV + "2026-11-17,WALMEX,*,PPP_PUBLICADO_VERIFICADO,43,,\n")["statusCode"], 503)

    def test_sin_variaciones_no_inventa_ceros(self):
        data = self.CSV.replace(",42,40,5", ",42,,")
        body = json.loads(self.llamar("GET /api/mercado/resumen", data)["body"])
        self.assertEqual(body["kpis"]["total_con_variacion"], 0)
        self.assertIsNone(body["kpis"]["conteo_alzas"])
        self.assertIsNone(body["kpis"]["conteo_bajas"])

    def test_sectores_excluye_contingencia_y_reporta_cobertura(self):
        csv = ("fecha,emisora,serie,sector_economico,estado_captura,ppp_bmv_mxn,variacion_ppp_vs_anterior_pct\n"
               "2026-11-17,WALMEX,*,Consumo,PPP_PUBLICADO_VERIFICADO,42,5\n"
               "2026-11-17,AMX,B,Consumo,CONTINGENCIA_FUENTE_SECUNDARIA,23,99\n"
               "2026-11-17,GRUMA,B,Industria,PPP_PUBLICADO_VERIFICADO,12,\n")
        r = self.llamar("GET /api/terminal/sectores", csv)
        self.assertEqual(r["statusCode"], 200)
        sectores = {x["sector"]: x for x in json.loads(r["body"])["sectores"]}
        self.assertEqual(sectores["Consumo"]["variacion_media_pct"], 5)
        self.assertEqual(sectores["Consumo"]["con_ppp"], 1)
        self.assertEqual(sectores["Consumo"]["huecos"], 1)
        self.assertEqual(sectores["Industria"]["con_ppp"], 1)
        self.assertEqual(sectores["Industria"]["con_variacion"], 0)
        self.assertIsNone(sectores["Industria"]["variacion_media_pct"])
        self.assertEqual(self.llamar("GET /api/terminal/sectores", csv, "2020-01-01")["statusCode"], 404)

    def test_diario_recupera_serie_y_variacion_sin_cambiar_snapshot(self):
        snapshot = ("fecha,emisora,serie,estado_captura,ppp_bmv_mxn\n"
                    "2026-11-17,WALMEX,,PPP_PUBLICADO_VERIFICADO,42\n")
        diario = ("fecha,emisora,serie,sector_economico,estado_captura,ppp_bmv_mxn,variacion_ppp_vs_anterior_pct\n"
                  "2026-11-17,WALMEX,*,Comercio,PPP_PUBLICADO_VERIFICADO,42,5\n"
                  "2026-11-17,AMX,B,Telecomunicaciones,CONTINGENCIA_FUENTE_SECUNDARIA,23,9\n")
        class S3PorClave:
            def get_object(self, Bucket, Key):
                valor = diario if Key.startswith("silver/precios_ppp/") else snapshot
                return {"Body": io.BytesIO(valor.encode()), "ContentLength": len(valor), "LastModified": "2026-11-18"}
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k"}):
            r = api.ejecutar({"routeKey": "GET /api/mercado/resumen"}, Tabla(), S3PorClave())
        body = json.loads(r["body"])
        self.assertEqual(body["fuente"]["tipo"], "silver_diario_s3")
        self.assertEqual(body["cotizaciones"][0]["serie"], "*")
        self.assertEqual(body["cotizaciones"][0]["variacion_pct"], 5)
        self.assertIsNone(body["cotizaciones"][1]["ppp_bmv_mxn"])
        self.assertIsNone(body["cotizaciones"][1]["variacion_pct"])

    def test_solo_corte_ausente_permite_respaldo(self):
        snapshot = self.CSV
        class ErrorS3(Exception):
            def __init__(self, code):
                self.response = {"Error": {"Code": code}}
        class S3ConError:
            def __init__(self, code):
                self.code = code
            def get_object(self, Bucket, Key):
                if Key.startswith("silver/precios_ppp/"):
                    raise ErrorS3(self.code)
                return {"Body": io.BytesIO(snapshot.encode()), "ContentLength": len(snapshot)}
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k"}):
            r = api.ejecutar({"routeKey": "GET /api/mercado/resumen"}, Tabla(), S3ConError("NoSuchKey"))
            self.assertEqual(json.loads(r["body"])["fuente"]["tipo"], "instantanea_s3")
            r = api.ejecutar({"routeKey": "GET /api/mercado/resumen"}, Tabla(), S3ConError("AccessDenied"))
            self.assertEqual(r["statusCode"], 503)

    def test_rechaza_corte_diario_con_fecha_o_serie_invalidas(self):
        snapshot = self.CSV
        class S3Invalido:
            def get_object(self, Bucket, Key):
                valor = (snapshot.replace("2026-11-17,WALMEX,*", "2026-11-16,WALMEX,*")
                         if Key.startswith("silver/precios_ppp/") else snapshot)
                return {"Body": io.BytesIO(valor.encode()), "ContentLength": len(valor)}
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k"}):
            self.assertEqual(api.ejecutar({"routeKey": "GET /api/mercado/resumen"}, Tabla(), S3Invalido())["statusCode"], 503)

    def test_formato_o_fuente_no_disponible(self):
        self.assertEqual(self.llamar("GET /api/mercado/fechas", "invalido\n")["statusCode"], 503)
        with patch.dict("os.environ", {"MERCADO_BUCKET": "", "MERCADO_KEY": ""}):
            self.assertEqual(api.ejecutar({"routeKey": "GET /api/mercado/fechas"}, Tabla())["statusCode"], 503)

    def test_serie_exige_token_y_permiso_de_emisora(self):
        perfil = Tabla({"rol": "user", "plan": "explorer", "email": "x@example.org", "nombre": "X"})
        e = evento({"sub": "u", "token_use": "access"})
        e["routeKey"] = "GET /api/terminal/serie"
        e["queryStringParameters"] = {"emisora": "AMX"}
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k"}):
            self.assertEqual(api.ejecutar(e, perfil, self.S3(self.CSV))["statusCode"], 403)
            e["queryStringParameters"]["emisora"] = "WALMEX"
            r = api.ejecutar(e, perfil, self.S3(self.CSV))
            self.assertEqual(r["statusCode"], 200)
            self.assertEqual(json.loads(r["body"])["puntos"][0]["ppp"], 42)
            e["requestContext"]["authorizer"]["jwt"]["claims"]["token_use"] = "id"
            self.assertEqual(api.ejecutar(e, perfil, self.S3(self.CSV))["statusCode"], 401)

    def test_serie_rechaza_fechas_ambiguas_y_no_rellena_contingencia(self):
        perfil = Tabla({"rol": "user", "plan": "professional", "email": "x@example.org", "nombre": "X"})
        e = evento({"sub": "u", "token_use": "access"})
        e["routeKey"] = "GET /api/terminal/serie"
        e["queryStringParameters"] = {"emisora": "AMX"}
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k"}):
            r = api.ejecutar(e, perfil, self.S3(self.CSV))
            self.assertIsNone(json.loads(r["body"])["puntos"][0]["ppp"])
            data = self.CSV + "2026-11-17,AMX,C,PPP_PUBLICADO_VERIFICADO,24,,\n"
            self.assertEqual(api.ejecutar(e, perfil, self.S3(data))["statusCode"], 503)

    def test_estadistica_permiso_cobertura_y_contingencia(self):
        perfil = Tabla({"rol": "user", "plan": "explorer", "email": "x@example.org", "nombre": "X"})
        e = evento({"sub": "u", "token_use": "access"})
        e["routeKey"] = "GET /api/terminal/estadistica"
        e["queryStringParameters"] = {"emisora": "AMX"}
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k"}):
            self.assertEqual(api.ejecutar(e, perfil, self.S3(self.CSV))["statusCode"], 403)
            e["queryStringParameters"]["emisora"] = "WALMEX"
            r = api.ejecutar(e, perfil, self.S3(self.CSV))
            b = json.loads(r["body"])
            self.assertEqual(r["statusCode"], 200)
            self.assertEqual(b["cobertura_historico"]["registros"], 1)
            self.assertEqual(b["estadisticas_historico_verificado"][0]["media"], 42)
            self.assertIsNone(b["cobertura_panel"])
            self.assertIn("no está conectado", b["metodologia"]["advertencia"])
            e["queryStringParameters"].update({"desde": "2026-11-20", "hasta": "2026-11-19"})
            self.assertEqual(api.ejecutar(e, perfil, self.S3(self.CSV))["statusCode"], 422)
            e["queryStringParameters"]["desde"] = "20261117"
            self.assertEqual(api.ejecutar(e, perfil, self.S3(self.CSV))["statusCode"], 422)

    def test_estadistica_contingencia_y_duplicados(self):
        perfil = Tabla({"rol": "user", "plan": "professional", "email": "x@example.org", "nombre": "X"})
        e = evento({"sub": "u", "token_use": "access"})
        e["routeKey"] = "GET /api/terminal/estadistica"
        e["queryStringParameters"] = {"emisora": "AMX"}
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k"}):
            b = json.loads(api.ejecutar(e, perfil, self.S3(self.CSV))["body"])
            self.assertEqual(b["cobertura_historico"]["registros"], 1)
            self.assertEqual(b["estadisticas_historico_verificado"][0]["n_valido"], 0)
            self.assertIsNone(b["estadisticas_historico_verificado"][0]["media"])
            self.assertEqual(b["serie_historica_verificada"], [])
            dup = self.CSV + "2026-11-17,AMX,C,PPP_PUBLICADO_VERIFICADO,24,,\n"
            self.assertEqual(api.ejecutar(e, perfil, self.S3(dup))["statusCode"], 503)

    def test_medidas_muestrales_y_histograma(self):
        valores = [1.0, 2.0, 3.0, 4.0]
        m = api._medidas(valores, 5, "x")
        self.assertEqual(m["n_valido"], 4)
        self.assertEqual(m["faltantes"], 1)
        self.assertEqual(m["media"], 2.5)
        self.assertEqual(m["q1"], 1.75)
        self.assertAlmostEqual(m["asimetria"], 0)
        self.assertAlmostEqual(m["exceso_curtosis"], -1.2)
        self.assertEqual(sum(b["n"] for b in api._histograma(valores)), 4)

    def test_mercado_universo_ipc35_provisional_con_y_sin_bronze_sin_habilitar_senales(self):
        bronze_html = (
            "<html><body><p>Resumen 17 Nov 2026</p><table>"
            "<tr><th>Emisora</th><th>Serie</th><th>Último</th><th>Anterior</th><th>PPP</th></tr>"
            "<tr><td>VOLAR</td><td>A</td><td>15.30</td><td>15.00</td><td>15.15</td></tr>"
            "<tr><td>KOF</td><td>UBL</td><td>162.00</td><td>160.00</td><td>161.60</td></tr>"
            "</table></body></html>"
        )

        class ErrorNoSuchKey(Exception):
            def __init__(self):
                self.response = {"Error": {"Code": "NoSuchKey"}}

        class S3Ipc35:
            def __init__(self, incluir_bronze=True):
                self.incluir_bronze = incluir_bronze

            def get_object(self, Bucket, Key):
                if Key.startswith("silver/precios_ppp/"):
                    raise ErrorNoSuchKey()
                if Key.startswith("bronze/"):
                    if not self.incluir_bronze:
                        raise ErrorNoSuchKey()
                    raw = bronze_html.encode("utf-8")
                    return {"Body": io.BytesIO(raw), "ContentLength": len(raw), "LastModified": "2026-11-18"}
                raw = MercadoTest.CSV.encode("utf-8")
                return {"Body": io.BytesIO(raw), "ContentLength": len(raw), "LastModified": "2026-11-18"}

        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k"}):
            # Universo inválido -> 422.
            bad = api.ejecutar({"routeKey": "GET /api/mercado/resumen",
                                "queryStringParameters": {"fecha": "2026-11-17", "universo": "inventado"}},
                               Tabla(), S3Ipc35(True))
            self.assertEqual(bad["statusCode"], 422)

            # Con Bronze HTML disponible -> 3 base del CSV + 20 candidatos = 23 filas (2 candidatos con PPP observado, 18 huecos).
            r_ok = api.ejecutar({"routeKey": "GET /api/mercado/resumen",
                                 "queryStringParameters": {"fecha": "2026-11-17", "universo": "ipc35_provisional"}},
                                Tabla(), S3Ipc35(True))
            self.assertEqual(r_ok["statusCode"], 200)
            body = json.loads(r_ok["body"])
            self.assertEqual(body["kpis"]["total_candidatos_20"], 20)
            self.assertEqual(body["kpis"]["total_provisionales_con_ppp"], 2)
            self.assertTrue(body["catalogo_ipc"]["bronze_disponible"])
            self.assertFalse(body["catalogo_ipc"]["senales_habilitadas"])
            self.assertEqual(body["catalogo_ipc"]["estado_composicion"], "PROVISIONAL_NO_OFICIAL")
            por_em = {x["emisora"]: x for x in body["cotizaciones"]}
            self.assertEqual(por_em["VOLAR"]["estado_captura"], "PPP_OBSERVADO_MAPEO_PROVISIONAL")
            self.assertEqual(por_em["VOLAR"]["ppp_bmv_mxn"], 15.15)
            self.assertAlmostEqual(por_em["VOLAR"]["variacion_pct"], 1.0)
            self.assertFalse(por_em["VOLAR"]["elegible_senales"])
            self.assertEqual(por_em["PINFRA"]["estado_captura"], "NO_ENCONTRADO_EN_TABLAS_BOLETIN")
            self.assertIsNone(por_em["PINFRA"]["ppp_bmv_mxn"])
            self.assertTrue(all(x["elegible_senales"] is False for x in body["cotizaciones"]))

            # Sin Bronze HTML -> candidatos quedan explícitamente sin dato y sin imputación.
            r_sin = api.ejecutar({"routeKey": "GET /api/mercado/resumen",
                                  "queryStringParameters": {"fecha": "2026-11-17", "universo": "ipc35_provisional"}},
                                 Tabla(), S3Ipc35(False))
            self.assertEqual(r_sin["statusCode"], 200)
            body_sin = json.loads(r_sin["body"])
            self.assertFalse(body_sin["catalogo_ipc"]["bronze_disponible"])
            self.assertEqual(body_sin["kpis"]["total_provisionales_con_ppp"], 0)
            cands = [x for x in body_sin["cotizaciones"] if x["origen_catalogo"] == "CANDIDATO_20"]
            self.assertEqual(len(cands), 20)
            self.assertTrue(all(x["estado_captura"] == "BOLETIN_BRONZE_NO_DISPONIBLE" and x["ppp_bmv_mxn"] is None for x in cands))


if __name__ == "__main__":
    unittest.main()
