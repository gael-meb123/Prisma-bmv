"""Compatibilidad temporal: la autenticación fue consolidada en Cognito + DynamoDB (AWS).

Supabase fue retirado definitivamente; este shim reexporta los tipos de ``core.local_auth``
para no romper pruebas unitarias locales que inyectan ``Usuario`` mediante dependency_overrides.
"""
from core.local_auth import (  # noqa: F401
    EMISORAS_POR_PLAN,
    PLANES_VALIDOS,
    ROLES_VALIDOS,
    TODAS,
    Usuario,
    actualizar_usuario,
    crear_usuario,
    exigir_emisora,
    limpiar_cache,
    listar_usuarios,
    requiere_admin,
    usuario_actual,
)
