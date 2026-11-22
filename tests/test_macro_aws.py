import importlib.util
import io
import json
from pathlib import Path

from botocore.exceptions import ClientError

spec = importlib.util.spec_from_file_location(
    "macro_aws_handler", Path(__file__).resolve().parents[1] / "infra/macro_aws/src/handler.py"
)
handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handler)


class S3Falso:
    def __init__(self):
        self.payload = None

    def get_object(self, **kwargs):
        if self.payload is None:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": ""}}, "GetObject")
        return {"Body": io.BytesIO(self.payload)}

    def put_object(self, **kwargs):
        self.payload = kwargs["Body"]


class TablaFalsa:
    def __init__(self):
        self.borradas = []

    def scan(self, **kwargs):
        return {"Items": [{"connectionId": "activa"}, {"connectionId": "cerrada"}]}

    def delete_item(self, **kwargs):
        self.borradas.append(kwargs["Key"]["connectionId"])


def test_publicador_conserva_datos_y_notifica(monkeypatch):
    s3, tabla = S3Falso(), TablaFalsa()
    mensajes = []

    class Secretos:
        def get_secret_value(self, **kwargs):
            return {"SecretString": "token"}

    class Gateway:
        def post_to_connection(self, **kwargs):
            if kwargs["ConnectionId"] == "cerrada":
                raise ClientError({"Error": {"Code": "GoneException", "Message": ""}}, "PostToConnection")
            mensajes.append(json.loads(kwargs["Data"]))

    class Dynamo:
        def Table(self, name):
            return tabla

    def cliente(nombre, **kwargs):
        return {"s3": s3, "secretsmanager": Secretos(), "apigatewaymanagementapi": Gateway()}[nombre]

    for key, value in {"MACRO_BUCKET": "bucket", "MACRO_KEY": "macro/indicadores.json",
                       "BANXICO_SECRET_ARN": "secret", "CONNECTIONS_TABLE": "tabla",
                       "WS_MANAGEMENT_URL": "https://example.com/prod"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(handler.boto3, "client", cliente)
    monkeypatch.setattr(handler.boto3, "resource", lambda *_: Dynamo())
    monkeypatch.setattr(handler, "_serie", lambda *_: (20.0, "2026-11-17"))
    assert handler.publicar({}, None)["series_disponibles"] == 4
    assert mensajes == [{"tipo": "macro_actualizada"}]
    assert tabla.borradas == ["cerrada"]

    def fallo(*_):
        raise OSError("No disponible")

    monkeypatch.setattr(handler, "_serie", fallo)
    handler.publicar({}, None)
    indicadores = json.loads(s3.payload)["indicadores"]
    assert all(item["valor"] == 20.0 and item["estado"] == "ultima_consulta_fallida" for item in indicadores)
