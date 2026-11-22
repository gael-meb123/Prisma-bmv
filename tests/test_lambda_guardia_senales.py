import importlib.util
import csv
import hashlib
import io
import unittest
from datetime import date
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "infra/lambda/guardia_senales/handler.py"
spec = importlib.util.spec_from_file_location("guardia_lab", path)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class GuardiaTest(unittest.TestCase):
    def datos(self):
        sesiones = api.sesiones("2026-11-19")
        return [{"fecha": f, "emisora": e, "serie": "B", "estado_captura": "PPP_PUBLICADO_VERIFICADO",
                 "ppp_bmv_mxn": "10", "sha256_boletin": "a" * 64,
                 "url_fuente": f"https://www.bmv.com.mx/docs-pub/rss/boletin{f.replace('-', '')}.html"}
                for e in ("AMX", "WALMEX") for f in sesiones]

    def test_nunca_emite_y_bloquea_contingencia_en_ventana(self):
        filas = self.datos()
        filas[0]["estado_captura"] = "CONTINGENCIA_FUENTE_SECUNDARIA"
        r = api.ejecutar({"fecha": "2026-11-19", "emisoras": ["AMX", "WALMEX"], "filas": filas})
        self.assertEqual(r["emision"], "NO_HABILITADA")
        self.assertFalse(r["evaluacion"]["AMX"]["ventana_apta"])
        self.assertTrue(r["evaluacion"]["WALMEX"]["ventana_apta"])
        self.assertFalse(r["evaluacion"]["WALMEX"]["apta_modelo_relativo"])

    def test_rechaza_entrada_no_admitida(self):
        for e in ({"fecha": "2027-01-01", "emisoras": ["AMX"], "filas": []},
                  {"fecha": "2026-11-19", "emisoras": ["CANDIDATA"], "filas": []},
                  {"fecha": "2026-11-19", "emisoras": ["AMX"], "filas": [], "emitir": True}):
            with self.assertRaises(ValueError):
                api.ejecutar(e)

    def test_calendario_coincide_con_calendario_local_2026(self):
        from prisma.domain.bmv_core import ultimas_sesiones
        self.assertEqual(api.sesiones("2026-11-19"), ultimas_sesiones("2026-11-19", 21))

    def test_integracion_s3_verifica_html_y_no_escribe(self):
        class Ausente(Exception):
            response = {"Error": {"Code": "NoSuchKey"}}
        class S3:
            def __init__(self):
                self.objetos, self.calls = {}, []
            def get_object(self, Bucket, Key):
                self.calls.append((Bucket, Key))
                if Key not in self.objetos:
                    raise Ausente()
                raw = self.objetos[Key]
                return {"Body": io.BytesIO(raw), "ContentLength": len(raw)}
        s3, bucket = S3(), "prisma-bmv-datalake-tunombre-2026"
        for fecha in api.sesiones("2026-11-19"):
            d = date.fromisoformat(fecha)
            mes = {10: "Oct", 11: "Nov"}[d.month]
            html = (f"<p>{d.day} {mes} {d.year}</p><table><tr><th>Emisora</th><th>Serie</th>"
                    "<th>Último</th><th>Anterior</th><th>PPP</th></tr>"
                    "<tr><td>AMX</td><td>B</td><td>11</td><td>9</td><td>10</td></tr>"
                    "<tr><td>WALMEX</td><td>*</td><td>11</td><td>9</td><td>10</td></tr></table>").encode()
            sha = hashlib.sha256(html).hexdigest()
            url = f"https://www.bmv.com.mx/docs-pub/rss/boletin{d:%Y%m%d}.html"
            buffer = io.StringIO(newline="")
            cols = ["fecha", "emisora", "serie", "estado_captura", "ppp_bmv_mxn", "sha256_boletin", "url_fuente"]
            writer = csv.DictWriter(buffer, fieldnames=cols); writer.writeheader()
            for emisora, serie in (("AMX", "B"), ("WALMEX", "*")):
                writer.writerow({"fecha": fecha, "emisora": emisora, "serie": serie, "estado_captura": "PPP_PUBLICADO_VERIFICADO",
                                 "ppp_bmv_mxn": "10", "sha256_boletin": sha, "url_fuente": url})
            s3.objetos[f"silver/precios_ppp/{d:%Y/%m}/ppp_15_emisoras_{d:%Y%m%d}.csv"] = buffer.getvalue().encode()
            s3.objetos[f"bronze/{d:%Y/%m}/boletin_{d:%Y%m%d}.html"] = html
        event = {"fecha": "2026-11-19", "modo": "auditoria_s3"}
        resultado = api.ejecutar_s3(event, s3, bucket)
        self.assertEqual(resultado["emision"], "NO_HABILITADA")
        self.assertEqual(resultado["resumen_evidencia"]["COINCIDE_PPP_Y_HASH"], 42)
        self.assertTrue(resultado["evaluacion"]["AMX"]["apta_modelo_relativo"])
        s3.objetos["bronze/2026/11/boletin_20261119.html"] += b"corrupto"
        resultado = api.ejecutar_s3(event, s3, bucket)
        self.assertEqual(resultado["resumen_evidencia"]["HASH_DIFERENTE"], 2)
        self.assertFalse(resultado["evaluacion"]["AMX"]["ventana_apta"])
        self.assertFalse(resultado["evaluacion"]["WALMEX"]["ventana_apta"])
        with self.assertRaises(ValueError):
            api.ejecutar_s3(event, s3, "otro-bucket")

    def test_error_s3_no_se_confunde_con_archivo_ausente(self):
        class Denegado(Exception):
            response = {"Error": {"Code": "AccessDenied"}}
        class S3:
            def get_object(self, **kwargs):
                raise Denegado()
        with self.assertRaises(Denegado):
            api.ejecutar_s3({"fecha": "2026-11-19", "modo": "auditoria_s3"},
                            S3(), "prisma-bmv-datalake-tunombre-2026")


if __name__ == "__main__":
    unittest.main()
