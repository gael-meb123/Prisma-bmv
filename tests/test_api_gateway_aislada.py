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
            self.assertEqual(por_em["VOLAR"]["sector"], "Industrial · Aerolíneas (provisional)")
            self.assertEqual(por_em["VOLAR"]["ppp_bmv_mxn"], 15.15)
            self.assertAlmostEqual(por_em["VOLAR"]["variacion_pct"], 1.0)
            self.assertFalse(por_em["VOLAR"]["elegible_senales"])
            self.assertEqual(por_em["PINFRA"]["estado_captura"], "NO_ENCONTRADO_EN_TABLAS_BOLETIN")
            self.assertEqual(por_em["PINFRA"]["sector"], "Industrial · Infraestructura (provisional)")
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

    def test_gobernanza_en_vivo_y_prismi_aws_con_guardrails_y_plan(self):
        class ErrorNoSuchKey(Exception):
            def __init__(self):
                self.response = {"Error": {"Code": "NoSuchKey"}}

        class S3Gob:
            def __init__(self):
                self.objs = {
                    "k": MercadoTest.CSV.encode("utf-8"),
                    "evidencias/operacion/avance_ventana_limpia.json": json.dumps({
                        "ultima_fecha_capturada": "2026-11-20",
                        "capturas_seguras_totales": 8,
                        "sha256_bronze": "a" * 64,
                        "sha256_silver": "b" * 64,
                        "emision": "NO_HABILITADA",
                        "ventana_limpia": {"desde_corte_limpio": "2026-11-20", "sesiones_consecutivas": 1, "meta": 21, "faltan": 20, "completa": False, "fechas_racha": ["2026-11-20"]},
                    }).encode("utf-8"),
                    "evidencias/observaciones_yahoo/estado_permiso.json": json.dumps({"estado": "APROBADO", "habilitacion_permitida": True}).encode("utf-8"),
                    "evidencias/calendario_bmv/2027/estado.json": json.dumps({"estado": "PENDIENTE_FUENTE_OFICIAL", "habilita_operacion": False}).encode("utf-8"),
                }

            def get_object(self, Bucket, Key):
                if Key not in self.objs:
                    raise ErrorNoSuchKey()
                raw = self.objs[Key]
                return {"Body": io.BytesIO(raw), "ContentLength": len(raw), "LastModified": "2026-11-21"}

            def list_objects_v2(self, Bucket, Prefix, MaxKeys=100):
                if Prefix == "silver/ipc35_provisional/capturas/":
                    return {"Contents": [{"Key": "silver/ipc35_provisional/capturas/2026/11/captura_20261120.json"}]}
                return {"Contents": []}

        s3 = S3Gob()
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k", "YAHOO_OBSERVACIONES_HABILITADAS": "true", "ANTHROPIC_API_KEY": ""}):
            r_gob = api.ejecutar({"routeKey": "GET /api/terminal/gobernanza"}, Tabla(), s3)
            self.assertEqual(r_gob["statusCode"], 200)
            gob = json.loads(r_gob["body"])
            self.assertEqual(len(gob["nodos"]), 10)
            self.assertEqual(gob["estado_operativo"]["ventana_limpia"]["sesiones_consecutivas"], 1)
            self.assertEqual(gob["estado_operativo"]["compuertas"]["emision_senales"], "NO_HABILITADA")
            self.assertTrue(gob["estado_operativo"]["compuertas"]["yahoo_observaciones"]["habilitada_api"])
            self.assertEqual(gob["estado_operativo"]["integridad"]["cortes_ipc35_provisionales"], 1)

            perfil_exp = Tabla({"rol": "user", "plan": "explorer", "email": "e@example.org", "nombre": "Exp"})
            ev_p = evento({"sub": "u", "token_use": "access"})
            ev_p["routeKey"] = "POST /api/terminal/prismi"

            # Tema externo -> GUARDRAIL
            ev_p["body"] = json.dumps({"pregunta": "Dame una receta de pastel"})
            r_ext = api.ejecutar(ev_p, perfil_exp, s3)
            self.assertEqual(r_ext["statusCode"], 200)
            self.assertEqual(json.loads(r_ext["body"])["origen"], "GUARDRAIL")

            # Asesoría imperativa -> GUARDRAIL
            ev_p["body"] = json.dumps({"pregunta": "¿Debo comprar WALMEX hoy?"})
            r_adv = api.ejecutar(ev_p, perfil_exp, s3)
            b_adv = json.loads(r_adv["body"])
            self.assertEqual(b_adv["origen"], "GUARDRAIL")
            self.assertIn("No doy recomendaciones", b_adv["respuesta"])
            self.assertIn("$42.00 MXN", b_adv["respuesta"])

            # Respeta plan Explorer (no filtra AMX)
            ev_p["body"] = json.dumps({"pregunta": "¿Cómo cerró AMX?"})
            r_plan = api.ejecutar(ev_p, perfil_exp, s3)
            self.assertIn("no está incluida en tu plan", json.loads(r_plan["body"])["respuesta"])

            # Consulta sobre señales -> honestamente indica bloqueo 1/21
            ev_p["body"] = json.dumps({"pregunta": "¿Ya están listas las señales G2?"})
            r_sen = api.ejecutar(ev_p, perfil_exp, s3)
            b_sen = json.loads(r_sen["body"])
            self.assertEqual(b_sen["origen"], "LOCAL_AWS")
            self.assertIn("bloqueados", b_sen["respuesta"])
            self.assertIn("1/21", b_sen["respuesta"])

            # Cuerpo vacío -> 422
            ev_p["body"] = json.dumps({"pregunta": "   "})
            self.assertEqual(api.ejecutar(ev_p, perfil_exp, s3)["statusCode"], 422)

    def test_gold_evaluacion_habilitada_y_bloqueada_por_flag(self):
        csv_g2 = (
            "id_senal_g2,fecha_senal,muestra_evaluacion,fecha_objetivo_h5,emisora,serie,sector_economico,"
            "modelo_g2,ppp_base_t,ret_10,ret_10_rel_panel,volatilidad_20,probabilidad_subida,prediccion_clase,"
            "prediccion_etiqueta,estado_consenso_g2,estado_resolucion,sesiones_transcurridas,fecha_parcial_reciente,"
            "retorno_parcial_pct,acierto_parcial_en_curso,acierto_direccional_t5,brier_observado_t5,sha256_boletin_base\n"
            + "\n".join(
                f"G2_20261110_WALMEX_{m},2026-11-10,OUT_OF_SAMPLE_PRE_REGISTRADO,2026-11-18,WALMEX,*,Comercio,"
                f"{m},50.0,0.02,-0.03,0.015,0.58,1,SUBIDA,CONSENSO_PANEL_G2_SUBIDA,PENDIENTE_T+5,0,,,,,,{'a'*64}"
                for m in (
                    "G2_V1_POOLED_REL3_CALIBRADO",
                    "G2_V2_POOLED_REL3_ZONA_NEUTRAL",
                    "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO",
                    "G2_V4_POOLED_DM5_REL_CORTO_PLAZO",
                    "G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL",
                )
            )
            + "\n"
        )
        precios_csv = (
            "fecha,emisora,serie,estado_captura,ppp_bmv_mxn,anterior_bmv_mxn,variacion_ppp_vs_anterior_pct\n"
            "2026-11-10,WALMEX,*,PPP_PUBLICADO_VERIFICADO,50.0,49.5,1.0\n"
            "2026-11-11,WALMEX,*,PPP_PUBLICADO_VERIFICADO,51.0,50.0,2.0\n"
            "2026-11-18,WALMEX,*,PPP_PUBLICADO_VERIFICADO,52.0,51.0,1.96\n"
        )
        reg_json = json.dumps({
            "G2_V1_POOLED_REL3_CALIBRADO": {
                "variables": ["ret_10", "ret_10_rel_panel", "volatilidad_20"],
                "beta": [0.1, 0.2, -0.3, 0.05],
                "scalers_por_emisora": {"WALMEX": {"mean": [0.0, 0.0, 0.01], "scale": [0.02, 0.02, 0.01]}},
            }
        })
        met_json = json.dumps({"fecha_congelamiento_oficial": "2026-11-06", "modelos_test": []})

        class ErrorNoSuchKey(Exception):
            def __init__(self):
                self.response = {"Error": {"Code": "NoSuchKey"}}

        class S3Gold:
            def __init__(self):
                self.objs = {
                    "k": precios_csv.encode(),
                    "gold/senales_g2/registro_senales_prospectivas_panel_g2.csv": csv_g2.encode(),
                    "evidencias/modelos_evaluacion/registro_modelos_g2_oficial.json": reg_json.encode(),
                    "evidencias/modelos_evaluacion/metricas_institucionales_v1.json": met_json.encode(),
                }

            def get_object(self, Bucket, Key):
                if Key not in self.objs:
                    raise ErrorNoSuchKey()
                raw = self.objs[Key]
                return {"Body": io.BytesIO(raw), "ContentLength": len(raw), "LastModified": "2026-11-21"}

        s3 = S3Gold()
        perfil_exp = Tabla({"rol": "user", "plan": "explorer", "email": "e@example.org", "nombre": "E"})

        # Con bandera en false -> sigue bloqueado (503)
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k", "GOLD_EVALUACION_HABILITADA": "false"}):
            self.assertEqual(api.ejecutar({"routeKey": "GET /api/metricas/modelos"}, Tabla(), s3)["statusCode"], 503)

        # Con bandera en true -> sirve consenso, senal (con cascada), seguimiento t+5, marcador y metricas
        with patch.dict("os.environ", {"MERCADO_BUCKET": "b", "MERCADO_KEY": "k", "GOLD_EVALUACION_HABILITADA": "true"}):
            r_met = api.ejecutar({"routeKey": "GET /api/metricas/modelos"}, Tabla(), s3)
            self.assertEqual(r_met["statusCode"], 200)
            self.assertTrue(json.loads(r_met["body"])["modo_evaluacion_gold"])

            ev_c = evento({"sub": "u", "token_use": "access"})
            ev_c["routeKey"] = "GET /api/terminal/consenso"
            r_c = api.ejecutar(ev_c, perfil_exp, s3)
            self.assertEqual(r_c["statusCode"], 200)
            bc = json.loads(r_c["body"])
            self.assertEqual(bc["emisoras"][0]["estado"], "subida")

            ev_s = evento({"sub": "u", "token_use": "access"})
            ev_s["routeKey"] = "GET /api/terminal/senal"
            ev_s["queryStringParameters"] = {"emisora": "WALMEX"}
            r_s = api.ejecutar(ev_s, perfil_exp, s3)
            self.assertEqual(r_s["statusCode"], 200)
            bs = json.loads(r_s["body"])
            self.assertEqual(bs["consensos"]["G2"], "CONSENSO_ALTO_SUBIDA")
            self.assertIn("ret_10_rel_panel", bs["factor"]["contribuciones"])

            # Explorer bloqueado en GMEXICO (403)
            ev_s["queryStringParameters"] = {"emisora": "GMEXICO"}
            self.assertEqual(api.ejecutar(ev_s, perfil_exp, s3)["statusCode"], 403)

            ev_seg = evento({"sub": "u", "token_use": "access"})
            ev_seg["routeKey"] = "GET /api/terminal/seguimiento"
            ev_seg["queryStringParameters"] = {"emisora": "WALMEX"}
            r_seg = api.ejecutar(ev_seg, perfil_exp, s3)
            self.assertEqual(r_seg["statusCode"], 200)
            bseg = json.loads(r_seg["body"])
            self.assertEqual(bseg["resumen"]["estado"], "RESUELTA_T+5")
            self.assertTrue(bseg["modelos"][0]["acierto_t5"])

            ev_m = evento({"sub": "u", "token_use": "access"})
            ev_m["routeKey"] = "GET /api/terminal/marcador"
            r_m = api.ejecutar(ev_m, perfil_exp, s3)
            self.assertEqual(r_m["statusCode"], 200)
            self.assertEqual(len(json.loads(r_m["body"])["modelos"]), 5)


if __name__ == "__main__":
    unittest.main()
