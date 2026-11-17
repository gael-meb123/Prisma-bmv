"""Lambda recolector-diario-bmv contra un S3 en memoria (sin AWS)."""

import io
import json
import urllib.error

import pandas as pd
import pytest

import importlib.util
from pathlib import Path

# Carga explícita por ruta: la raíz del repositorio conserva un lambda_function.py heredado
# que, por orden de sys.path, taparía al recolector de infra/.
_RUTA_LAMBDA = Path(__file__).resolve().parent.parent / "infra" / "lambda" / "recolector_diario_bmv" / "lambda_function.py"
_spec = importlib.util.spec_from_file_location("recolector_diario_bmv_lambda", _RUTA_LAMBDA)
lf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lf)
from prisma.domain import bmv_core as core


class S3Falso:
    class exceptions:  # noqa: N801
        NoSuchKey = KeyError

    def __init__(self):
        self.obj: dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.obj[Key] = Body if isinstance(Body, bytes) else Body.encode()

    def get_object(self, Bucket, Key):
        if Key not in self.obj:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.obj[Key])}

    def head_object(self, Bucket, Key):
        if Key not in self.obj:
            raise KeyError(Key)
        return {}

    def csv(self, key):
        return pd.read_csv(io.BytesIO(self.obj[key]))


@pytest.fixture
def s3(serie, modelos, monkeypatch):
    monkeypatch.setenv("BUCKET_NAME", "bucket-prueba")
    s = S3Falso()
    s.put_object("b", lf.SERIE_KEY, serie.to_csv(index=False).encode())
    s.put_object("b", lf.MODELOS_KEY, json.dumps(modelos).encode())
    return s


def _boletin_desde_serie(serie, fecha):
    """HTML sintético con los PPP de `fecha` tomados de la serie real."""
    filas = serie[(serie["fecha"] == fecha) & (serie["estado_captura"] == core.ESTADO_PUBLICADO)]
    tr = "".join(f"<tr><td>{r.emisora.replace('&', '&amp;')}</td><td>{r.serie}</td><td>{r.ultimo_bmv_mxn}</td>"
                 f"<td>{r.anterior_bmv_mxn}</td><td>{r.ppp_bmv_mxn}</td><td>1</td></tr>" for r in filas.itertuples())
    return (f"<table><tr><td>Más Negociadas</td></tr><tr><th>Emisora</th><th>Serie</th><th>Último</th>"
            f"<th>Anterior</th><th>PPP</th><th>Vol</th></tr>{tr}</table>").encode()


def test_flujo_completo_bronze_silver_gold(s3, serie):
    html = _boletin_desde_serie(serie, "2026-10-30")
    r = lf.lambda_handler({"fecha": "20261030"}, None, s3_client=s3, descargador=lambda u: html)
    body = json.loads(r["body"])
    assert r["statusCode"] == 200 and body["estado"] == "EXITO"
    assert "bronze/2026/10/boletin_20261030.html" in s3.obj
    assert s3.obj["bronze/2026/10/boletin_20261030.sha256"].decode() == body["sha256"]

    silver = s3.csv("silver/precios_ppp/2026/10/ppp_15_emisoras_20261030.csv")
    assert list(silver.columns) == list(core.COLUMNAS_SILVER) and len(silver) == 15
    assert not s3.obj["silver/precios_ppp/2026/10/ppp_15_emisoras_20261030.csv"].startswith(b"\xef\xbb\xbf")

    gold = s3.csv(lf.GOLD_G2_KEY)
    assert list(gold.columns) == list(core.COLUMNAS_GOLD_G2)
    assert body["senales_g2_nuevas"] == 12
    assert body["consensos"]["GMEXICO"] == "CONSENSO_PANEL_G2_SUBIDA"


def test_reejecucion_es_idempotente_y_no_reescribe_senales(s3, serie):
    html = _boletin_desde_serie(serie, "2026-10-30")
    lf.lambda_handler({"fecha": "20261030"}, None, s3_client=s3, descargador=lambda u: html)
    g1 = s3.csv(lf.GOLD_G2_KEY)
    r = lf.lambda_handler({"fecha": "20261030"}, None, s3_client=s3, descargador=lambda u: html)
    g2 = s3.csv(lf.GOLD_G2_KEY)
    assert json.loads(r["body"])["bronze"]["estado"] == "YA_INGERIDO_FIRMA_IDENTICA"
    assert len(g1) == len(g2) == g2["id_senal_g2"].nunique()
    pd.testing.assert_series_equal(g1["timestamp_emision_utc"], g2["timestamp_emision_utc"])


def test_hash_divergente_no_sobrescribe_bronze(s3, serie):
    html = _boletin_desde_serie(serie, "2026-10-30")
    lf.lambda_handler({"fecha": "20261030"}, None, s3_client=s3, descargador=lambda u: html)
    original = s3.obj["bronze/2026/10/boletin_20261030.html"]
    r = lf.lambda_handler({"fecha": "20261030"}, None, s3_client=s3, descargador=lambda u: html + b"<!-- cambio -->")
    assert r["statusCode"] == 409
    assert s3.obj["bronze/2026/10/boletin_20261030.html"] == original
    assert any(k.startswith("bronze/2026/10/boletin_20261030__") for k in s3.obj)


def test_dia_inhabil_no_descarga(s3):
    def no_llamar(u):
        raise AssertionError("no debía descargar")
    r = lf.lambda_handler({"fecha": "20261102"}, None, s3_client=s3, descargador=no_llamar)
    assert json.loads(r["body"])["estado"] == "DIA_INHABIL_BMV"


def test_boletin_no_publicado(s3):
    def error_404(u):
        raise urllib.error.HTTPError(u, 404, "Not Found", {}, None)
    r = lf.lambda_handler({"fecha": "20261103"}, None, s3_client=s3, descargador=error_404)
    assert r["statusCode"] == 404 and json.loads(r["body"])["estado"] == "BOLETIN_NO_PUBLICADO"


def test_sesion_sin_backfill_bloquea_inferencia(s3, serie):
    """Si falta la sesión del 30/10 en la serie, el 3/11 no tiene ventana completa: no se infiere."""
    sin_30 = serie[serie["fecha"] != "2026-10-30"]
    s3.put_object("b", lf.SERIE_KEY, sin_30.to_csv(index=False).encode())
    html = _boletin_desde_serie(serie, "2026-10-30")  # precios cualquiera para el 3/11
    r = json.loads(lf.lambda_handler({"fecha": "20261103"}, None, s3_client=s3, descargador=lambda u: html)["body"])
    assert r["senales_g2_nuevas"] == 0
    assert set(r["emisoras_bloqueadas_por_huecos"]) == set(core.EMISORAS_PANEL_G2)
