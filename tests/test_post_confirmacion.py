import unittest
from infra.auth_aws_aislado.post_confirmacion import ejecutar


class ErrorCondicional(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class Tabla:
    def __init__(self):
        self.item = None

    def put_item(self, Item, **kwargs):
        assert kwargs["ConditionExpression"] == "attribute_not_exists(#s)"
        if self.item is not None:
            raise ErrorCondicional()
        self.item = Item

    def get_item(self, **kwargs):
        return {"Item": self.item}


class PerfilTest(unittest.TestCase):
    def evento(self):
        return {"userPoolId": "pool", "triggerSource": "PostConfirmation_ConfirmSignUp",
                "request": {"userAttributes": {"sub": "u", "email": "a@example.org",
                            "name": "Nombre", "email_verified": "true", "custom:rol": "admin"}}}

    def test_privilegios_y_reintento_no_rebaja_admin_existente(self):
        tabla = Tabla()
        ejecutar(self.evento(), tabla, "pool")
        self.assertEqual((tabla.item["rol"], tabla.item["plan"]), ("user", "explorer"))
        tabla.item["rol"] = "admin"
        ejecutar(self.evento(), tabla, "pool")
        self.assertEqual(tabla.item["rol"], "admin")

    def test_recuperacion_no_modifica_perfil(self):
        evento = self.evento()
        evento["triggerSource"] = "PostConfirmation_ConfirmForgotPassword"
        tabla = Tabla()
        ejecutar(evento, tabla, "pool")
        self.assertIsNone(tabla.item)

    def test_correo_no_verificado_y_pool_invalido(self):
        evento = self.evento()
        with self.assertRaises(ValueError):
            ejecutar(evento, Tabla(), "otro")
        evento["request"]["userAttributes"]["email_verified"] = "false"
        with self.assertRaises(ValueError):
            ejecutar(evento, Tabla(), "pool")
