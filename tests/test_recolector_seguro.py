import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from unittest.mock import patch

path = Path(__file__).resolve().parent.parent / "infra/lambda/recolector_seguro/handler.py"
spec = importlib.util.spec_from_file_location("recolector_seguro", path)
recolector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recolector)

HTML = ("""<p>19 Nov 2026</p><table><tr><th>Emisora</th><th>Serie</th>
<th>Último</th><th>Anterior</th><th>PPP</th></tr>
<tr><td>AMX</td><td>B</td><td>11</td><td>9</td><td>10</td></tr>
<tr><td>WALMEX</td><td>*</td><td>20</td><td>19</td><td>20</td></tr>
</table>""").encode()
BUCKET = recolector.BUCKET
EVENTO = {"fecha": "2026-11-19"}


class ErrorS3(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class S3:
    def __init__(self):
        self.objetos = {}
        self.lock = Lock()

    def put_object(self, Bucket, Key, Body, ContentType, IfNoneMatch):
        assert Bucket == BUCKET and IfNoneMatch == "*"
        with self.lock:
            if Key in self.objetos:
                raise ErrorS3("PreconditionFailed")
            self.objetos[Key] = Body

    def get_object(self, Bucket, Key):
        with self.lock:
            if Key not in self.objetos:
                raise ErrorS3("NoSuchKey")
            raw = self.objetos[Key]
        return {"Body": io.BytesIO(raw), "ContentLength": len(raw)}

    def list_objects_v2(self, Bucket, Prefix, MaxKeys, **kwargs):
        keys = [k for k in sorted(self.objetos) if k.startswith(Prefix)]
        return {"Contents": [{"Key": k} for k in keys], "IsTruncated": False}


class RecolectorSeguroTest(unittest.TestCase):
    def ejecutar(self, s3, html=HTML, **kwargs):
        return recolector.ejecutar(EVENTO, s3, lambda url: html, BUCKET, **kwargs)

    def test_guardia_real_y_reintento_idempotente(self):
        s3 = S3()
        first = self.ejecutar(s3)
        snapshot = dict(s3.objetos)
        second = self.ejecutar(s3)
        self.assertEqual(first["emision"], "NO_HABILITADA")
        self.assertEqual(first["guardia"]["resumen_evidencia"]["COINCIDE_PPP_Y_HASH"], 2)
        self.assertFalse(first["guardia"]["evaluacion"]["AMX"]["ventana_apta"])
        self.assertEqual(second["silver"], "IDENTICO")
        self.assertEqual(snapshot, s3.objetos)
        self.assertFalse(any(k.startswith("gold/") or k == "silver/serie_unificada_reciente.csv"
                             for k in s3.objetos))
        silver = next(v for k, v in s3.objetos.items() if k.startswith("silver/recolector_seguro/precios_ppp/"))
        self.assertIn(b"NO_ENCONTRADO_EN_TABLAS_BOLETIN", silver)

    def test_silver_legado_nunca_se_escribe_ni_reemplaza(self):
        s3 = S3()
        legado = "silver/precios_ppp/2026/11/ppp_15_emisoras_20261119.csv"
        s3.objetos[legado] = b"historico legado que debe permanecer intacto"
        resultado = self.ejecutar(s3)
        self.assertEqual(s3.objetos[legado], b"historico legado que debe permanecer intacto")
        self.assertEqual(resultado["guardia"]["resumen_evidencia"]["COINCIDE_PPP_Y_HASH"], 2)
        manifiesto = json.loads(next(v for k, v in s3.objetos.items()
                                     if k.startswith("silver/capturas_seguras/")))
        self.assertTrue(manifiesto["silver"].startswith("silver/recolector_seguro/precios_ppp/"))

    def test_fallo_parcial_no_publica_en_prefijo_legado(self):
        s3 = S3()
        def falla(*args):
            raise RuntimeError("guardia")
        with self.assertRaises(RuntimeError):
            self.ejecutar(s3, guardia=falla)
        self.assertFalse(any(k.startswith("silver/precios_ppp/") for k in s3.objetos))
        self.assertTrue(any(k.startswith("silver/recolector_seguro/precios_ppp/") for k in s3.objetos))

    def test_concurrencia_no_sobrescribe(self):
        s3 = S3()
        with ThreadPoolExecutor(max_workers=8) as pool:
            resultados = list(pool.map(lambda _: self.ejecutar(s3), range(8)))
        self.assertEqual(len(resultados), 8)
        self.assertEqual(len(s3.objetos), 4)
        self.assertTrue(all(r["emision"] == "NO_HABILITADA" for r in resultados))

    def test_contenido_diferente_va_a_cuarentena_y_preserva_silver(self):
        s3 = S3()
        self.ejecutar(s3)
        anterior = dict(s3.objetos)
        with self.assertRaises(recolector.ConflictoInmutable):
            self.ejecutar(s3, HTML + b"<!-- otra version -->")
        for key, raw in anterior.items():
            self.assertEqual(s3.objetos[key], raw)
        self.assertEqual(sum(k.startswith("cuarentena/") for k in s3.objetos), 1)

    def test_silver_distinto_no_se_sobrescribe(self):
        s3 = S3()
        self.ejecutar(s3)
        key = next(k for k in s3.objetos if k.startswith("silver/recolector_seguro/precios_ppp/"))
        s3.objetos[key] = b"silver anterior"
        with self.assertRaises(recolector.ConflictoInmutable):
            self.ejecutar(s3)
        self.assertEqual(s3.objetos[key], b"silver anterior")

    def test_fallo_guardia_no_emite_ni_toca_gold_y_reintento_recupera(self):
        s3 = S3()
        def falla(*args):
            raise RuntimeError("fallo guardia")
        with self.assertRaises(RuntimeError):
            self.ejecutar(s3, guardia=falla)
        self.assertEqual(len(s3.objetos), 3)
        self.assertFalse(any(k.startswith("silver/capturas_seguras/") for k in s3.objetos))
        self.assertEqual(self.ejecutar(s3)["emision"], "NO_HABILITADA")
        self.assertFalse(any(k.startswith("gold/") for k in s3.objetos))

    def test_guardia_invalida_no_se_acepta(self):
        with self.assertRaises(ValueError):
            self.ejecutar(S3(), guardia=lambda *args: {"emision": "NO_HABILITADA"})

    def test_rechaza_datos_incompletos_o_ambiguos_antes_de_escribir(self):
        s3 = S3()
        conflictivo = HTML.replace(b"</table>", b"<tr><td>AMX</td><td>B</td><td>11</td><td>9</td><td>12</td></tr></table>")
        for raw in (b"", HTML.replace(b"19 Nov", b"18 Nov"), conflictivo):
            with self.assertRaises(ValueError):
                self.ejecutar(s3, raw)
        self.assertEqual(s3.objetos, {})

    def test_solo_404_explicitamente_ausente_y_error_no_oculto(self):
        class Denegado(S3):
            def put_object(self, **kwargs):
                raise ErrorS3("AccessDenied")
        with self.assertRaises(ErrorS3):
            self.ejecutar(Denegado())

    def test_sin_boletin_no_hay_fallback_ni_escritura(self):
        s3 = S3()
        def no_publicado(url):
            raise urllib.error.HTTPError(url, 404, "No publicado", {}, None)
        with self.assertRaises(urllib.error.HTTPError):
            recolector.ejecutar(EVENTO, s3, no_publicado, BUCKET)
        self.assertEqual(s3.objetos, {})

    def test_recupera_silver_tras_fallo_parcial(self):
        class FallaUnaVez(S3):
            fallar = True
            def put_object(self, **kwargs):
                if kwargs["Key"].startswith("silver/recolector_seguro/precios_ppp/") and self.fallar:
                    self.fallar = False
                    raise ErrorS3("AccessDenied")
                return super().put_object(**kwargs)
        s3 = FallaUnaVez()
        with self.assertRaises(ErrorS3):
            self.ejecutar(s3)
        self.assertEqual(len(s3.objetos), 2)
        resultado = self.ejecutar(s3)
        self.assertEqual(resultado["bronze"], "IDENTICO")
        self.assertEqual(resultado["silver"], "CREADO")

    def test_evento_y_calendario_cerrados(self):
        for event in ({"fecha": "2027-01-04"}, {"fecha": "20261119"},
                      {"fecha": "2026-11-19", "emitir": True}):
            with self.assertRaises(ValueError):
                recolector.ejecutar(event, S3(), lambda _: HTML, BUCKET)

    def test_paquete_carga_fuera_del_repositorio(self):
        root = path.parents[3]
        with tempfile.TemporaryDirectory() as directory:
            zip_path = Path(directory) / "recolector.zip"
            subprocess.run([sys.executable, str(root / "scripts/empaquetar_recolector_seguro.py"),
                            "--salida", str(zip_path)], check=True, capture_output=True)
            codigo = ("import importlib,sys; sys.path.insert(0,sys.argv[1]); "
                      "m=importlib.import_module('infra.lambda.recolector_seguro.handler'); "
                      "assert '.zip' in m.__file__; "
                      "importlib.import_module('infra.lambda.guardia_senales.handler')")
            subprocess.run([sys.executable, "-I", "-c", codigo, str(zip_path)], cwd=directory,
                           check=True, capture_output=True)

    def test_api_descubre_solo_publicacion_completa_y_verifica_hash(self):
        api_path = path.parents[3] / "infra/api_gateway_aislada/handler.py"
        api_spec = importlib.util.spec_from_file_location("api_capturas_test", api_path)
        api = importlib.util.module_from_spec(api_spec)
        api_spec.loader.exec_module(api)
        s3 = S3()
        s3.objetos["snapshot.csv"] = (b"fecha,emisora,serie,estado_captura,ppp_bmv_mxn\n"
                                      b"2026-11-17,WALMEX,*,PPP_PUBLICADO_VERIFICADO,42\n")
        class Tabla:
            def get_item(self, **kwargs):
                return {"Item": {"rol": "user", "plan": "explorer", "email": "a@example.org", "nombre": "X"}}
        with patch.dict("os.environ", {"MERCADO_BUCKET": BUCKET, "MERCADO_KEY": "snapshot.csv",
                                       "CAPTURAS_SEGURAS_HABILITADAS": "true"}):
            evento = {"routeKey": "GET /api/mercado/fechas"}
            self.assertEqual(json.loads(api.ejecutar(evento, Tabla(), s3)["body"]), ["2026-11-17"])
            def falla(*args):
                raise RuntimeError("guardia")
            with self.assertRaises(RuntimeError):
                self.ejecutar(s3, guardia=falla)
            self.assertEqual(json.loads(api.ejecutar(evento, Tabla(), s3)["body"]), ["2026-11-17"])
            self.ejecutar(s3)
            self.assertEqual(json.loads(api.ejecutar(evento, Tabla(), s3)["body"]), ["2026-11-19", "2026-11-17"])
            resumen = api.ejecutar({"routeKey": "GET /api/mercado/resumen"}, Tabla(), s3)
            self.assertEqual(json.loads(resumen["body"])["fecha"], "2026-11-19")
            auth = {"routeKey": "GET /api/serie/walmex", "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "u", "token_use": "access"}}}}}
            self.assertEqual(len(json.loads(api.ejecutar(auth, Tabla(), s3)["body"])), 2)
            key = next(k for k in s3.objetos if k.startswith("silver/recolector_seguro/precios_ppp/"))
            s3.objetos[key] += b"alterado"
            self.assertEqual(api.ejecutar(evento, Tabla(), s3)["statusCode"], 503)

    def test_manifiesto_solo_se_confirma_tras_guardia_correcta(self):
        s3 = S3()
        def resultado_invalido(*args):
            return {"fecha": "2026-11-19", "origen": "SILVER_DIARIO_Y_BRONZE_S3",
                    "emision": "NO_HABILITADA", "evaluacion": {}}
        with self.assertRaises(ValueError):
            self.ejecutar(s3, guardia=resultado_invalido)
        self.assertFalse(any(k.startswith("silver/capturas_seguras/") for k in s3.objetos))
        self.ejecutar(s3)
        key = next(k for k in s3.objetos if k.startswith("silver/capturas_seguras/"))
        manifiesto = json.loads(s3.objetos[key])
        self.assertEqual(manifiesto["guardia"], "COMPLETADA_SIN_EMISION")
        self.assertEqual(manifiesto["fecha"], "2026-11-19")

    def test_api_bloquea_diario_parcial_si_fecha_ya_existe_en_snapshot(self):
        api_path = path.parents[3] / "infra/api_gateway_aislada/handler.py"
        api_spec = importlib.util.spec_from_file_location("api_capturas_parciales_test", api_path)
        api = importlib.util.module_from_spec(api_spec)
        api_spec.loader.exec_module(api)
        s3 = S3()
        s3.objetos["snapshot.csv"] = (b"fecha,emisora,serie,estado_captura,ppp_bmv_mxn\n"
                                      b"2026-11-19,WALMEX,*,PPP_PUBLICADO_VERIFICADO,20\n")
        def falla(*args):
            raise RuntimeError("guardia")
        with patch.dict("os.environ", {"MERCADO_BUCKET": BUCKET, "MERCADO_KEY": "snapshot.csv",
                                       "CAPTURAS_SEGURAS_HABILITADAS": "true"}):
            with self.assertRaises(RuntimeError):
                self.ejecutar(s3, guardia=falla)
            evento = {"routeKey": "GET /api/mercado/resumen"}
            self.assertEqual(api.ejecutar(evento, None, s3)["statusCode"], 503)
            self.ejecutar(s3)
            self.assertEqual(api.ejecutar(evento, None, s3)["statusCode"], 200)
            s3.objetos["snapshot.csv"] = s3.objetos["snapshot.csv"].replace(b",20\n", b",42\n")
            self.assertEqual(api.ejecutar(evento, None, s3)["statusCode"], 503)
            self.assertEqual(api.ejecutar({"routeKey": "GET /api/mercado/fechas"}, None, s3)["statusCode"], 503)

    def test_api_detecta_inicio_concurrente_despues_de_descubrir_manifiestos(self):
        api_path = path.parents[3] / "infra/api_gateway_aislada/handler.py"
        api_spec = importlib.util.spec_from_file_location("api_carrera_test", api_path)
        api = importlib.util.module_from_spec(api_spec)
        api_spec.loader.exec_module(api)
        s3 = S3()
        s3.objetos["snapshot.csv"] = (b"fecha,emisora,serie,estado_captura,ppp_bmv_mxn\n"
                                      b"2026-11-19,WALMEX,*,PPP_PUBLICADO_VERIFICADO,42\n")
        leer = api._leer_corte_diario
        def carrera(cliente, fecha):
            resultado = leer(cliente, fecha)
            def falla(*args):
                raise RuntimeError("guardia")
            with self.assertRaises(RuntimeError):
                self.ejecutar(s3, guardia=falla)
            return resultado
        with patch.dict("os.environ", {"MERCADO_BUCKET": BUCKET, "MERCADO_KEY": "snapshot.csv",
                                       "CAPTURAS_SEGURAS_HABILITADAS": "true"}), \
                patch.object(api, "_leer_corte_diario", side_effect=carrera):
            self.assertEqual(api.ejecutar({"routeKey": "GET /api/mercado/resumen"}, None, s3)["statusCode"], 503)

    def test_api_no_confunde_marcador_inaccesible_o_corrupto_con_ausente(self):
        api_path = path.parents[3] / "infra/api_gateway_aislada/handler.py"
        api_spec = importlib.util.spec_from_file_location("api_marcador_test", api_path)
        api = importlib.util.module_from_spec(api_spec)
        api_spec.loader.exec_module(api)
        class SinPermiso(S3):
            def get_object(self, Bucket, Key):
                if Key.startswith("silver/capturas_en_curso/"):
                    raise ErrorS3("AccessDenied")
                return super().get_object(Bucket, Key)
        for s3 in (S3(), SinPermiso()):
            s3.objetos["snapshot.csv"] = (b"fecha,emisora,serie,estado_captura,ppp_bmv_mxn\n"
                                          b"2026-11-19,WALMEX,*,PPP_PUBLICADO_VERIFICADO,20\n")
            if type(s3) is S3:
                s3.objetos["silver/capturas_en_curso/2026/11/captura_20261119.json"] = b"incorrecto"
            with patch.dict("os.environ", {"MERCADO_BUCKET": BUCKET, "MERCADO_KEY": "snapshot.csv",
                                           "CAPTURAS_SEGURAS_HABILITADAS": "true"}):
                self.assertEqual(api.ejecutar({"routeKey": "GET /api/mercado/resumen"}, None, s3)["statusCode"], 503)


if __name__ == "__main__":
    unittest.main()
