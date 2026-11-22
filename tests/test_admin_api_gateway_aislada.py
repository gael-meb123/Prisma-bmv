import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parent.parent / "infra/api_gateway_aislada/handler.py"
spec = importlib.util.spec_from_file_location("admin_handler", path)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


def evento(ruta, actor="admin-1", body=None, target="user-1", token="access"):
    return {"routeKey": ruta, "requestContext": {"authorizer": {"jwt": {"claims": {"sub": actor, "token_use": token}}}},
            "pathParameters": {"uid": target}, "body": json.dumps(body) if body is not None else None}


class Tabla:
    def __init__(self, role="admin", falla_scan=False):
        self.role = role
        self.falla_scan = falla_scan
        self.scans = []

    def get_item(self, Key, ConsistentRead):
        return {"Item": {"sub": Key["sub"], "rol": self.role, "plan": "explorer",
                         "email": "a@example.invalid", "nombre": "Nombre"}}

    def scan(self, **kwargs):
        self.scans.append(kwargs)
        if self.falla_scan:
            raise RuntimeError("detalle privado")
        if len(self.scans) == 1:
            return {"Items": [{"sub": "a", "email": "a@example.invalid", "rol": "admin", "plan": "explorer"}],
                    "LastEvaluatedKey": {"sub": "a"}}
        return {"Items": [{"sub": "b", "email": "b@example.invalid", "rol": "user", "plan": "explorer"}]}


class DDB:
    def __init__(self):
        self.calls = []

    def transact_write_items(self, **kwargs):
        self.calls.append(kwargs)


class Cognito:
    def __init__(self, error_en=None):
        self.calls = []
        self.error_en = error_en

    def admin_create_user(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["MessageAction"] == self.error_en:
            raise RuntimeError("detalle privado")
        return {"User": {"Attributes": [{"Name": "sub", "Value": "nuevo-1"}]}}


class AdminTest(unittest.TestCase):
    def test_listar_exige_access_token_y_admin(self):
        e = evento("GET /api/admin/usuarios")
        self.assertEqual(api.ejecutar(e, Tabla("user"))["statusCode"], 403)
        self.assertEqual(api.ejecutar(evento("GET /api/admin/usuarios", token="id"), Tabla())["statusCode"], 401)
        tabla = Tabla()
        r = api.ejecutar(e, tabla)
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(len(json.loads(r["body"])), 2)
        self.assertTrue(tabla.scans[1]["ExclusiveStartKey"])

    def test_falla_scan_no_filtra_detalles(self):
        r = api.ejecutar(evento("GET /api/admin/usuarios"), Tabla(falla_scan=True))
        self.assertEqual(r["statusCode"], 503)
        self.assertNotIn("detalle privado", r["body"])

    def test_cambio_exige_admin_y_valida_cuerpos(self):
        e = evento("PATCH /api/admin/usuarios/{uid}", body={"plan": "professional"})
        db = DDB()
        with patch.dict("os.environ", {"PERFILES_TABLE": "perfiles"}):
            self.assertEqual(api.ejecutar(e, Tabla("user"), ddb=db)["statusCode"], 403)
            for body in ({}, {"plan": "otro"}, {"rol": "root"}, {"sub": "otro"}, {"nombre": ""}):
                self.assertEqual(api.ejecutar(evento(e["routeKey"], body=body), Tabla(), ddb=db)["statusCode"], 422)
            self.assertEqual(api.ejecutar(evento(e["routeKey"], body={"rol": "user"}, target="admin-1"), Tabla(), ddb=db)["statusCode"], 400)
            self.assertEqual(db.calls, [])

    def test_cambio_condiciona_permiso_y_existencia_en_transaccion(self):
        e = evento("PATCH /api/admin/usuarios/{uid}", body={"plan": "professional", "rol": "user"})
        db = DDB()
        with patch.dict("os.environ", {"PERFILES_TABLE": "perfiles"}):
            self.assertEqual(api.ejecutar(e, Tabla(), ddb=db)["statusCode"], 200)
        acciones = db.calls[0]["TransactItems"]
        self.assertEqual(acciones[0]["ConditionCheck"]["Key"]["sub"]["S"], "admin-1")
        self.assertEqual(acciones[0]["ConditionCheck"]["ExpressionAttributeValues"][":admin"]["S"], "admin")
        self.assertEqual(acciones[1]["Update"]["Key"]["sub"]["S"], "user-1")
        self.assertIn("attribute_exists", acciones[1]["Update"]["ConditionExpression"])

    def test_cambio_propio_no_duplica_elemento_en_transaccion(self):
        e = evento("PATCH /api/admin/usuarios/{uid}", body={"plan": "professional"}, target="admin-1")
        db = DDB()
        with patch.dict("os.environ", {"PERFILES_TABLE": "perfiles"}):
            self.assertEqual(api.ejecutar(e, Tabla(), ddb=db)["statusCode"], 200)
        acciones = db.calls[0]["TransactItems"]
        self.assertEqual(len(acciones), 1)
        self.assertIn("#actorrol = :admin", acciones[0]["Update"]["ConditionExpression"])

    def test_alta_crea_sin_correo_y_envia_solo_despues_de_perfil_condicional(self):
        datos = {"email": "Usuario@Example.org", "nombre": " Prueba ", "rol": "user", "plan": "explorer"}
        e = evento("POST /api/admin/usuarios", body=datos)
        db, cognito = DDB(), Cognito()
        with patch.dict("os.environ", {"PERFILES_TABLE": "perfiles", "COGNITO_POOL_ID": "pool"}):
            r = api.ejecutar(e, Tabla(), ddb=db, cognito=cognito)
        self.assertEqual(r["statusCode"], 201)
        self.assertEqual([c["MessageAction"] for c in cognito.calls], ["SUPPRESS", "RESEND"])
        self.assertNotIn("TemporaryPassword", cognito.calls[0])
        acciones = db.calls[0]["TransactItems"]
        self.assertEqual(acciones[0]["ConditionCheck"]["Key"]["sub"]["S"], "admin-1")
        self.assertEqual(acciones[1]["Put"]["Item"]["email"]["S"], "usuario@example.org")
        self.assertIn("attribute_not_exists", acciones[1]["Put"]["ConditionExpression"])

    def test_alta_no_envia_si_falla_perfil_y_admite_fallo_de_envio(self):
        datos = {"email": "test@example.org", "nombre": "X", "rol": "user", "plan": "explorer"}
        e = evento("POST /api/admin/usuarios", body=datos)
        class FallaDB:
            def transact_write_items(self, **kwargs):
                raise RuntimeError("detalle privado")
        with patch.dict("os.environ", {"PERFILES_TABLE": "perfiles", "COGNITO_POOL_ID": "pool"}):
            cognito = Cognito()
            r = api.ejecutar(e, Tabla(), ddb=FallaDB(), cognito=cognito)
            self.assertEqual(r["statusCode"], 503)
            self.assertEqual([x["MessageAction"] for x in cognito.calls], ["SUPPRESS"])
            self.assertNotIn("detalle privado", r["body"])
            cognito = Cognito("RESEND")
            r = api.ejecutar(e, Tabla(), ddb=DDB(), cognito=cognito)
            self.assertEqual(r["statusCode"], 202)
            self.assertEqual(json.loads(r["body"])["invitacion"], "ENVIO_NO_CONFIRMADO")

    def test_alta_exige_admin_y_rechaza_contrasenas_y_campos_extra(self):
        datos = {"email": "test@example.org", "nombre": "X", "rol": "user", "plan": "explorer"}
        cognito, db = Cognito(), DDB()
        with patch.dict("os.environ", {"PERFILES_TABLE": "perfiles", "COGNITO_POOL_ID": "pool"}):
            self.assertEqual(api.ejecutar(evento("POST /api/admin/usuarios", body=datos), Tabla("user"), ddb=db, cognito=cognito)["statusCode"], 403)
            for cambios in ({"password": "no"}, {"rol": "root"}, {"plan": "otro"}, {"email": "inválido"}):
                self.assertEqual(api.ejecutar(evento("POST /api/admin/usuarios", body={**datos, **cambios}), Tabla(), ddb=db, cognito=cognito)["statusCode"], 422)
        self.assertEqual(cognito.calls, [])


if __name__ == "__main__":
    unittest.main()
