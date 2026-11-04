"""
Tests unitarios para la arquitectura SaaS de Prisma BMV
"""

import unittest
from core.auth import (
    _hash_password,
    _verify_password,
    autenticar_usuario,
    cambiar_plan_usuario,
    cargar_usuarios,
    registrar_usuario,
)
from core.claude_bot import responder_con_claude
from core.data_provider import (
    cargar_monitoreo_en_vivo,
    cargar_senales_panel_g2,
    obtener_fechas_mercado,
    obtener_kpis_mercado,
)


class TestSaaSPrismaBMV(unittest.TestCase):
    def test_hashing_contrasenas(self):
        pwd = "PrismaSuperSecure2026!"
        h1, s1 = _hash_password(pwd)
        self.assertTrue(_verify_password(pwd, h1, s1))
        self.assertFalse(_verify_password("WrongPassword", h1, s1))

    def test_demo_user_exists_and_authenticates(self):
        usuarios = cargar_usuarios()
        self.assertIn("demo@prismabmv.com", usuarios)
        ok, info, msg = autenticar_usuario("demo@prismabmv.com", "Prisma2026!")
        self.assertTrue(ok)
        self.assertIsNotNone(info)
        self.assertEqual(info["email"], "demo@prismabmv.com")
        self.assertEqual(info["plan"], "professional")

    def test_data_provider_loads_files(self):
        df_mon = cargar_monitoreo_en_vivo()
        self.assertFalse(df_mon.empty)
        self.assertIn("ppp_bmv_mxn", df_mon.columns)

        fechas = obtener_fechas_mercado()
        self.assertGreater(len(fechas), 0)

        kpis = obtener_kpis_mercado(fechas[0])
        self.assertEqual(kpis["total_emisoras"], 15)
        self.assertGreaterEqual(kpis["total_verificadas"], 10)

    def test_claude_bot_guardrails_refusal(self):
        # Pregunta fuera de dominio
        resp_cocina = responder_con_claude("dame una receta de cocina para hacer pizza")
        self.assertIn("estrictamente restringido", resp_cocina)

        # Pregunta dentro de dominio
        resp_ppp = responder_con_claude("que es el ppp")
        self.assertIn("Precio Promedio Ponderado", resp_ppp)


if __name__ == "__main__":
    unittest.main()
