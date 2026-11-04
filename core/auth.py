"""
Prisma BMV - Motor de Autenticación, Usuarios y Gestión de Planes Freemium
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

from config_saas import PLANS

USERS_FILE = Path(__file__).resolve().parent.parent / "usuarios.json"


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hashed, salt


def _verify_password(password: str, hashed: str, salt: str) -> bool:
    expected_hash, _ = _hash_password(password, salt)
    return secrets.compare_digest(hashed, expected_hash)


def cargar_usuarios() -> dict[str, Any]:
    if not USERS_FILE.exists():
        # Crear usuario demo por defecto
        demo_hash, demo_salt = _hash_password("Prisma2026!")
        usuarios_iniciales = {
            "demo@prismabmv.com": {
                "nombre": "Analista Cuantitativo",
                "email": "demo@prismabmv.com",
                "password_hash": demo_hash,
                "salt": demo_salt,
                "plan": "professional",
                "creado_en": "2026-10-30T16:00:00Z",
                "onboarding_completado": True,
            }
        }
        guardar_usuarios(usuarios_iniciales)
        return usuarios_iniciales

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_usuarios(usuarios: dict[str, Any]) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, indent=2, ensure_ascii=False)


def registrar_usuario(
    nombre: str, email: str, password: str, plan: str = "professional"
) -> tuple[bool, str]:
    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "Correo electrónico no válido."
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."
    if not nombre.strip():
        return False, "El nombre no puede estar vacío."

    usuarios = cargar_usuarios()
    if email in usuarios:
        return False, "Ya existe una cuenta registrada con este correo."

    pwd_hash, salt = _hash_password(password)
    usuarios[email] = {
        "nombre": nombre.strip(),
        "email": email,
        "password_hash": pwd_hash,
        "salt": salt,
        "plan": plan if plan in PLANS else "explorer",
        "creado_en": "2026-11-02T00:00:00Z",
        "onboarding_completado": False,
    }
    guardar_usuarios(usuarios)
    return True, "Registro exitoso. ¡Bienvenido a Prisma BMV!"


def autenticar_usuario(email: str, password: str) -> tuple[bool, dict[str, Any] | None, str]:
    email = email.strip().lower()
    usuarios = cargar_usuarios()

    if email not in usuarios:
        return False, None, "Usuario no registrado."

    user_data = usuarios[email]
    if _verify_password(password, user_data["password_hash"], user_data["salt"]):
        # Retornar datos publicos sin hashes
        info = {
            "nombre": user_data["nombre"],
            "email": user_data["email"],
            "plan": user_data.get("plan", "explorer"),
            "onboarding_completado": user_data.get("onboarding_completado", False),
        }
        return True, info, "Autenticación exitosa."
    return False, None, "Contraseña incorrecta."


def cambiar_plan_usuario(email: str, nuevo_plan: str) -> bool:
    email = email.strip().lower()
    usuarios = cargar_usuarios()
    if email in usuarios and nuevo_plan in PLANS:
        usuarios[email]["plan"] = nuevo_plan
        guardar_usuarios(usuarios)
        return True
    return False


def marcar_onboarding_completado(email: str) -> None:
    email = email.strip().lower()
    usuarios = cargar_usuarios()
    if email in usuarios:
        usuarios[email]["onboarding_completado"] = True
        guardar_usuarios(usuarios)
