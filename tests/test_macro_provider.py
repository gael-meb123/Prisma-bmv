from datetime import datetime, timezone
import io
import json

import boto3
import pytest
from fastapi.testclient import TestClient

import api
from core import macro_provider


@pytest.fixture(autouse=True)
def limpiar_cache(monkeypatch):
    macro_provider._cache.clear()
    monkeypatch.setenv("BANXICO_TOKEN", "token-de-prueba")
    yield
    macro_provider._cache.clear()


def test_indicadores_oficiales_y_cache(monkeypatch):
    llamadas = []

    def descargar(serie, token):
        llamadas.append(serie)
        return (20.1234, "2026-11-17")

    monkeypatch.setattr(macro_provider, "_descargar", descargar)
    respuesta = macro_provider.obtener_indicadores()
    assert len(respuesta["indicadores"]) == 4
    assert all(x["estado"] == "disponible" and x["fecha_dato"] == "2026-11-17" for x in respuesta["indicadores"])
    assert all(x["fuente"].startswith("Banco de México") for x in respuesta["indicadores"])
    macro_provider.obtener_indicadores()
    assert len(llamadas) == 4


def test_fallo_conserva_ultimo_valor_con_advertencia(monkeypatch):
    monkeypatch.setattr(macro_provider, "_descargar", lambda *_: (20.0, "2026-11-17"))
    macro_provider.obtener_indicadores()
    for entrada in macro_provider._cache.values():
        entrada["intento"] -= macro_provider.TTL_SEGUNDOS + 1

    def fallar(*_):
        raise OSError("servicio inaccesible")

    monkeypatch.setattr(macro_provider, "_descargar", fallar)
    indicadores = macro_provider.obtener_indicadores()["indicadores"]
    assert all(x["estado"] == "ultima_consulta_fallida" and x["valor"] == 20.0 for x in indicadores)
    assert all(datetime.fromisoformat(x["consultado_en"]).tzinfo == timezone.utc for x in indicadores)


def test_sin_token_no_fabrica_datos(monkeypatch):
    monkeypatch.delenv("BANXICO_TOKEN", raising=False)
    respuesta = TestClient(api.app).get("/api/macro/indicadores")
    assert respuesta.status_code == 200
    assert all(x["estado"] == "no_disponible" and x["valor"] is None for x in respuesta.json()["indicadores"])


def test_modo_s3_no_oculta_fallos_con_datos_locales(monkeypatch):
    monkeypatch.setenv("MACRO_S3_BUCKET", "prueba")

    def fallar(*_):
        raise OSError("No se puede leer S3")

    monkeypatch.setattr(api, "obtener_desde_s3", fallar)
    respuesta = TestClient(api.app).get("/api/macro/indicadores")
    assert respuesta.status_code == 503
    assert "S3" not in respuesta.text


def test_s3_marca_consultas_antiguas_sin_cambiar_la_fecha_del_dato(monkeypatch):
    class S3:
        def get_object(self, **kwargs):
            documento = {"indicadores": [{"valor": 20, "fecha_dato": "2026-01-01",
                                          "consultado_en": "2020-01-01T00:00:00+00:00",
                                          "estado": "disponible"}]}
            return {"Body": io.BytesIO(json.dumps(documento).encode())}

    monkeypatch.setattr(boto3, "client", lambda *_: S3())
    indicador = macro_provider.obtener_desde_s3("bucket")["indicadores"][0]
    assert indicador["estado"] == "ultima_consulta_fallida"
    assert indicador["fecha_dato"] == "2026-01-01"
