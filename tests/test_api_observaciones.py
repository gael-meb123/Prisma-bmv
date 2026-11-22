import importlib
import json
import unittest
from unittest.mock import patch
from tests.test_recolector_seguro import S3, BUCKET
from tests.test_yahoo_secundario import payload
from tests.test_api_gateway_aislada import Tabla

api = importlib.import_module("infra.api_gateway_aislada.handler")


class ObservacionTest(unittest.TestCase):
    def test_secundaria_no_tiene_ppp_y_respeta_plan(self):
        tabla = Tabla({"rol": "user", "plan": "explorer", "email": "a@example.org", "nombre": "A"})
        s3 = S3()
        s3.objetos["observaciones/yahoo/WALMEX.MX/2026-11-19.json"] = payload()
        ev = {"routeKey": "GET /api/observaciones/yahoo",
              "queryStringParameters": {"emisora": "WALMEX", "fecha": "2026-11-19"},
              "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "u", "token_use": "access"}}}}}
        with patch.dict("os.environ", {"MERCADO_BUCKET": BUCKET, "YAHOO_OBSERVACIONES_HABILITADAS": "true"}):
            result = api.ejecutar(ev, tabla, s3)
            self.assertEqual(result["statusCode"], 200)
            data = json.loads(result["body"])
            self.assertFalse(data["inferencia_habilitada"])
            self.assertNotIn("ppp_bmv_mxn", data)
            self.assertEqual(data["fuente"], "YAHOO_FINANCE_SECUNDARIA")
            ev["queryStringParameters"]["emisora"] = "AMX"
            self.assertEqual(api.ejecutar(ev, tabla, s3)["statusCode"], 403)
        self.assertFalse(any(k.startswith("silver/") for k in s3.objetos))

    def test_plan_profesional_admite_15_documentadas_y_bloquea_deshabilitado(self):
        tabla = Tabla({"rol": "user", "plan": "professional", "email": "p@example.org", "nombre": "P"})
        s3 = S3()
        s3.objetos["observaciones/yahoo/AMXB.MX/2026-11-19.json"] = payload("AMXB.MX")
        ev = {"routeKey": "GET /api/observaciones/yahoo",
              "queryStringParameters": {"emisora": "AMX", "fecha": "2026-11-19"},
              "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "u", "token_use": "access"}}}}}
        with patch.dict("os.environ", {"MERCADO_BUCKET": BUCKET, "YAHOO_OBSERVACIONES_HABILITADAS": "false"}):
            self.assertEqual(api.ejecutar(ev, tabla, s3)["statusCode"], 503)
        with patch.dict("os.environ", {"MERCADO_BUCKET": BUCKET, "YAHOO_OBSERVACIONES_HABILITADAS": "true"}):
            res = api.ejecutar(ev, tabla, s3)
            self.assertEqual(res["statusCode"], 200)
            body = json.loads(res["body"])
            self.assertEqual(body["simbolo"], "AMXB.MX")
            self.assertNotIn("ppp_bmv_mxn", body)
            self.assertFalse(body["inferencia_habilitada"])
            ev["queryStringParameters"]["emisora"] = "KOF"
            self.assertEqual(api.ejecutar(ev, tabla, s3)["statusCode"], 403)
            # Con universo=ipc35_provisional admite candidatos verificados .MX sin tocar Silver.
            s3.objetos["observaciones/yahoo/VOLARA.MX/2026-11-19.json"] = payload("VOLARA.MX")
            ev["queryStringParameters"] = {"emisora": "VOLAR", "fecha": "2026-11-19", "universo": "ipc35_provisional"}
            res_v = api.ejecutar(ev, tabla, s3)
            self.assertEqual(res_v["statusCode"], 200)
            self.assertEqual(json.loads(res_v["body"])["simbolo"], "VOLARA.MX")
            self.assertFalse(any(k.startswith("silver/") for k in s3.objetos))
