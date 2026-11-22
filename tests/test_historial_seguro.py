import importlib
import json
import unittest
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from infra.capturas_seguras import clave, pagina
from tests.test_recolector_seguro import S3, BUCKET, HTML
from tests import test_api_gateway_aislada as fixtures

recolector = importlib.import_module("infra.lambda.recolector_seguro.handler")
guardia = importlib.import_module("infra.lambda.guardia_senales.handler")
api = importlib.import_module("infra.api_gateway_aislada.handler")


class Medido(S3):
    def __init__(self):
        super().__init__()
        self.gets = self.lists = 0

    def get_object(self, **kwargs):
        self.gets += 1
        return super().get_object(**kwargs)

    def list_objects_v2(self, Bucket, Prefix, MaxKeys, StartAfter="", **kwargs):
        self.lists += 1
        keys = [k for k in sorted(self.objetos) if k.startswith(Prefix) and k > StartAfter]
        return {"Contents": [{"Key": k} for k in keys[:MaxKeys]], "IsTruncated": len(keys) > MaxKeys}


class HistorialTest(unittest.TestCase):
    def setUp(self):
        self.s3 = Medido()

    def crear(self, dia):
        raw = HTML.replace(b"19 Nov", f"{dia} Nov".encode())
        return recolector.ejecutar({"fecha": f"2026-11-{dia}"}, self.s3, lambda _: raw, BUCKET)

    def test_guardia_incorpora_cortes_previos_confirmados_sin_listar(self):
        self.crear(18)
        resultado = self.crear(19)
        self.assertEqual(resultado["guardia"]["resumen_evidencia"]["COINCIDE_PPP_Y_HASH"], 4)
        self.assertEqual(resultado["guardia"]["resumen_evidencia"]["CAPTURA_SEGURA_CONFIRMADA"], 1)
        self.s3.gets = 0
        audit = guardia.ejecutar_s3({"fecha": "2026-11-19", "modo": "auditoria_s3"}, self.s3, BUCKET)
        self.assertEqual(audit["resumen_evidencia"]["CAPTURA_SEGURA_CONFIRMADA"], 2)
        self.assertEqual(audit["emision"], "NO_HABILITADA")
        self.assertEqual(self.s3.lists, 0)
        self.assertLessEqual(self.s3.gets, 21 * 4)

    def test_parcial_anterior_ignorado_y_recuperacion(self):
        def fallo(*args):
            raise RuntimeError("guardia no completada")
        raw = HTML.replace(b"19 Nov", b"18 Nov")
        with self.assertRaises(RuntimeError):
            recolector.ejecutar({"fecha": "2026-11-18"}, self.s3, lambda _: raw, BUCKET, guardia=fallo)
        audit = self.crear(19)["guardia"]
        self.assertEqual(audit["resumen_evidencia"]["COINCIDE_PPP_Y_HASH"], 2)
        self.crear(18)
        self.assertEqual(self.crear(19)["guardia"]["resumen_evidencia"]["COINCIDE_PPP_Y_HASH"], 4)

    def test_corrupcion_o_conflicto_no_degrada_a_legado(self):
        self.crear(18)
        m = json.loads(self.s3.objetos[clave("2026-11-18")])
        original = self.s3.objetos[m["silver"]]
        self.s3.objetos[m["silver"]] += b"alterado"
        with self.assertRaises(ValueError):
            self.crear(19)
        self.s3.objetos[m["silver"]] = original
        self.s3.objetos["silver/precios_ppp/2026/11/ppp_15_emisoras_20261118.csv"] = b"otro historial"
        with self.assertRaises(ValueError):
            self.crear(19)

    def test_paginacion_y_coste_no_dependen_de_otros_anios(self):
        self.crear(18)
        self.crear(19)
        for i in range(2100):
            self.s3.objetos[f"silver/capturas_seguras/2000/01/ruido_{i}"] = b"no consultar"
        self.s3.gets = self.s3.lists = 0
        env = {"MERCADO_BUCKET": BUCKET, "CAPTURAS_SEGURAS_HABILITADAS": "true"}
        ev = {"routeKey": "GET /api/mercado/fechas", "queryStringParameters": {"mes": "2026-11", "limite": "1"}}
        with patch.dict("os.environ", env):
            first = json.loads(api.ejecutar(ev, None, self.s3)["body"])
            self.assertEqual(first["fechas"], ["2026-11-18"])
            self.assertEqual(first["siguiente"], "2026-11-18")
            self.assertEqual((self.s3.lists, self.s3.gets), (1, 2))
            ev["queryStringParameters"]["despues"] = first["siguiente"]
            second = json.loads(api.ejecutar(ev, None, self.s3)["body"])
            self.assertEqual(second["fechas"], ["2026-11-19"])
            self.assertIsNone(second["siguiente"])
            self.assertEqual((self.s3.lists, self.s3.gets), (2, 4))

    def test_fecha_directa_no_lista_y_verifica_hash(self):
        self.crear(19)
        self.s3.gets = self.s3.lists = 0
        with patch.dict("os.environ", {"CAPTURAS_SEGURAS_HABILITADAS": "true"}):
            api._capturas_seguras(self.s3, BUCKET, "2026-11-19")
        self.assertEqual((self.s3.lists, self.s3.gets), (0, 2))

    def test_paginas_globales_incluyen_snapshot_y_todos_los_cortes(self):
        self.crear(18)
        self.crear(19)
        self.s3.objetos["snapshot.csv"] = fixtures.MercadoTest.CSV.encode()
        with patch.dict("os.environ", {"CAPTURAS_SEGURAS_HABILITADAS": "true",
                                     "MERCADO_BUCKET": BUCKET, "MERCADO_KEY": "snapshot.csv"}):
            e = {"routeKey": "GET /api/mercado/fechas", "queryStringParameters": {"paginado": "true", "limite": "1"}}
            primera = json.loads(api.ejecutar(e, None, self.s3)["body"])
            self.assertEqual(primera["fechas"], ["2026-11-18", "2026-11-17"])
            self.assertEqual(primera["siguiente"], "2026-11-18")
            e["queryStringParameters"]["despues"] = primera["siguiente"]
            segunda = json.loads(api.ejecutar(e, None, self.s3)["body"])
            self.assertEqual(segunda["fechas"], ["2026-11-19", "2026-11-17"])
            self.assertIsNone(segunda["siguiente"])
            self.assertEqual(primera["sha256_instantanea"], segunda["sha256_instantanea"])
            serie = api._serie({"routeKey": "GET /api/terminal/serie",
                                "queryStringParameters": {"emisora": "WALMEX", "paginado": "true", "limite": "1"}},
                               self.s3, ["WALMEX"])
            self.assertEqual(serie["statusCode"], 200)
            self.assertEqual(len(json.loads(serie["body"])["puntos"]), 2)

    def test_estadistica_consulta_intervalo_y_no_hay_truncamiento_silencioso(self):
        self.crear(18)
        self.crear(19)
        self.s3.objetos["snapshot.csv"] = fixtures.MercadoTest.CSV.encode()
        self.s3.objetos["silver/capturas_seguras/2020/01/no-leer"] = b"corrupto fuera del rango"
        with patch.dict("os.environ", {"CAPTURAS_SEGURAS_HABILITADAS": "true",
                                     "MERCADO_BUCKET": BUCKET, "MERCADO_KEY": "snapshot.csv"}):
            e = {"queryStringParameters": {"emisora": "WALMEX", "desde": "2026-11-17", "hasta": "2026-11-19"}}
            self.s3.lists = 0
            reporte = api._estadistica(e, self.s3, ["WALMEX"])
            self.assertEqual(reporte["statusCode"], 200)
            self.assertEqual(json.loads(reporte["body"])["cobertura_historico"]["registros"], 3)
            self.assertEqual(self.s3.lists, 1)
            e["queryStringParameters"]["desde"] = "2020-01-01"
            self.assertEqual(api._estadistica(e, self.s3, ["WALMEX"])["statusCode"], 422)

    def test_pagina_rechaza_duplicados_y_cursor_fuera_mes(self):
        class Duplicados:
            def list_objects_v2(self, **kwargs):
                return {"Contents": [{"Key": clave("2026-11-19")}] * 2}
        with self.assertRaises(ValueError):
            pagina(Duplicados(), BUCKET, "2026-11")
        with self.assertRaises(ValueError):
            pagina(self.s3, BUCKET, "2026-11", despues="2026-12-01")

    def test_pagina_corrupcion_no_devuelve_resultado_parcial(self):
        self.crear(19)
        self.s3.objetos[clave("2026-11-19")] = b"corrupto"
        with patch.dict("os.environ", {"CAPTURAS_SEGURAS_HABILITADAS": "true", "MERCADO_BUCKET": BUCKET}):
            result = api.ejecutar({"routeKey": "GET /api/mercado/fechas",
                                  "queryStringParameters": {"mes": "2026-11"}}, None, self.s3)
            self.assertEqual(result["statusCode"], 503)

    def test_api_empaquetada_carga_sin_repositorio(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            archivo = Path(directory) / "api.zip"
            subprocess.run([sys.executable, str(root / "scripts/empaquetar_api_gateway_aislada.py"),
                            "--salida", str(archivo)], check=True, capture_output=True)
            subprocess.run([sys.executable, "-I", "-c",
                            "import sys;sys.path.insert(0,sys.argv[1]);import handler;assert '.zip' in handler.__file__",
                            str(archivo)], cwd=directory, check=True, capture_output=True)
