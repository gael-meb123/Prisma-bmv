"""
Prisma BMV - Servicio de cuentas: registro, autenticación, planes y cuotas.

Reglas:
* Toda cuenta nueva nace en Explorer. Un plan de pago solo se activa con un cobro
  aprobado por la pasarela (sandbox), nunca desde el formulario de registro.
* Mensaje de error genérico al autenticar (no revela si el correo existe).
* Bloqueo temporal tras 5 intentos fallidos durante 15 minutos.
* Migración transparente de hashes heredados sha256(sal+password) a PBKDF2.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from prisma.plans import EXPLORER, PLANES
from prisma.security.crypto import (
    AlmacenCifrado,
    hash_password,
    requiere_rehash,
    verificar_password,
    verificar_password_legado,
)

MAX_INTENTOS = 5
BLOQUEO = timedelta(minutes=15)
PASSWORD_DEMO = "Prisma-Demo-2026"
CUENTAS_DEMO = {
    "explorer@demo.prismabmv.com": ("Cuenta demo Explorer", "explorer"),
    "pro@demo.prismabmv.com": ("Cuenta demo Professional", "professional"),
    "enterprise@demo.prismabmv.com": ("Cuenta demo Enterprise", "enterprise"),
}
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
MSG_CREDENCIALES = "Correo o contraseña incorrectos."


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def validar_password(password: str) -> str | None:
    if len(password) < 10:
        return "La contraseña necesita al menos 10 caracteres."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "La contraseña debe combinar letras y números."
    return None


def _publico(u: dict[str, Any]) -> dict[str, Any]:
    return {k: u.get(k) for k in ("nombre", "email", "plan", "tour_completado", "creado_en")}


class ServicioUsuarios:
    def __init__(self, almacen: AlmacenCifrado, iteraciones: int):
        self._almacen = almacen
        self._iter = iteraciones

    # -- persistencia -------------------------------------------------------
    def _cargar(self) -> dict[str, Any]:
        return self._almacen.cargar().get("usuarios", {})

    def _guardar(self, usuarios: dict[str, Any]) -> None:
        self._almacen.guardar({"version": 2, "usuarios": usuarios})

    def obtener(self, email: str) -> dict[str, Any] | None:
        u = self._cargar().get(email.strip().lower())
        return _publico(u) if u else None

    # -- alta y acceso -------------------------------------------------------
    def registrar(self, nombre: str, email: str, password: str) -> tuple[bool, str]:
        email = email.strip().lower()
        if not nombre.strip():
            return False, "Escriba su nombre o el de su institución."
        if not _RE_EMAIL.match(email):
            return False, "El correo no tiene un formato válido."
        if err := validar_password(password):
            return False, err
        usuarios = self._cargar()
        if email in usuarios:
            return False, "Ya existe una cuenta con ese correo. Inicie sesión."
        usuarios[email] = {
            "nombre": nombre.strip(),
            "email": email,
            "password_hash": hash_password(password, self._iter),
            "plan": EXPLORER,
            "tour_completado": False,
            "creado_en": _ahora().isoformat(),
            "intentos_fallidos": 0,
            "bloqueado_hasta": None,
            "historial_planes": [{"plan": EXPLORER, "fecha": _ahora().isoformat(), "ref": "alta"}],
            "cuota_prismi": {},
        }
        self._guardar(usuarios)
        return True, "Cuenta creada."

    def autenticar(self, email: str, password: str) -> tuple[bool, dict[str, Any] | None, str]:
        email = email.strip().lower()
        usuarios = self._cargar()
        u = usuarios.get(email)
        if u is None:
            return False, None, MSG_CREDENCIALES

        bloqueo = u.get("bloqueado_hasta")
        if bloqueo and datetime.fromisoformat(bloqueo) > _ahora():
            return False, None, "Cuenta bloqueada temporalmente por intentos fallidos. Intente en 15 minutos."

        ok = False
        if "password_hash" in u:
            ok = verificar_password(password, u["password_hash"])
        elif "legacy_sha256" in u:
            ok = verificar_password_legado(password, u["legacy_sha256"], u.get("legacy_salt", ""))

        if not ok:
            u["intentos_fallidos"] = int(u.get("intentos_fallidos", 0)) + 1
            if u["intentos_fallidos"] >= MAX_INTENTOS:
                u["bloqueado_hasta"] = (_ahora() + BLOQUEO).isoformat()
                u["intentos_fallidos"] = 0
            self._guardar(usuarios)
            return False, None, MSG_CREDENCIALES

        u["intentos_fallidos"], u["bloqueado_hasta"] = 0, None
        if "password_hash" not in u or requiere_rehash(u["password_hash"], self._iter):
            u["password_hash"] = hash_password(password, self._iter)
            u.pop("legacy_sha256", None)
            u.pop("legacy_salt", None)
        u["ultimo_acceso"] = _ahora().isoformat()
        self._guardar(usuarios)
        return True, _publico(u), "Sesión iniciada."

    # -- plan, tour y cuotas -------------------------------------------------
    def cambiar_plan(self, email: str, plan: str, referencia: str) -> bool:
        if plan not in PLANES:
            return False
        usuarios = self._cargar()
        u = usuarios.get(email.strip().lower())
        if u is None:
            return False
        u["plan"] = plan
        u.setdefault("historial_planes", []).append(
            {"plan": plan, "fecha": _ahora().isoformat(), "ref": referencia}
        )
        self._guardar(usuarios)
        return True

    def marcar_tour_completado(self, email: str) -> None:
        usuarios = self._cargar()
        if (u := usuarios.get(email.strip().lower())) is not None:
            u["tour_completado"] = True
            self._guardar(usuarios)

    def consumir_cuota_prismi(self, email: str, limite: int, hoy: str) -> tuple[bool, int]:
        """Descuenta una consulta a Claude del día. Devuelve (permitido, restantes)."""
        usuarios = self._cargar()
        u = usuarios.get(email.strip().lower())
        if u is None:
            return False, 0
        cuota = u.setdefault("cuota_prismi", {})
        usadas = int(cuota.get(hoy, 0))
        if usadas >= limite:
            return False, 0
        u["cuota_prismi"] = {hoy: usadas + 1}  # solo se conserva el día en curso
        self._guardar(usuarios)
        return True, limite - usadas - 1

    # -- utilidades -------------------------------------------------------------
    def sembrar_cuentas_demo(self) -> None:
        usuarios = self._cargar()
        cambio = False
        for email, (nombre, plan) in CUENTAS_DEMO.items():
            if email not in usuarios:
                usuarios[email] = {
                    "nombre": nombre, "email": email,
                    "password_hash": hash_password(PASSWORD_DEMO, self._iter),
                    "plan": plan, "tour_completado": True,
                    "creado_en": _ahora().isoformat(), "intentos_fallidos": 0,
                    "bloqueado_hasta": None, "cuota_prismi": {},
                    "historial_planes": [{"plan": plan, "fecha": _ahora().isoformat(), "ref": "demo"}],
                }
                cambio = True
        if cambio:
            self._guardar(usuarios)

    def importar_legado(self, ruta_json: Path) -> int:
        """Importa usuarios.json heredado (texto plano) al almacén cifrado sin conocer contraseñas."""
        datos = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
        usuarios = self._cargar()
        n = 0
        for email, u in datos.items():
            email = email.strip().lower()
            if email in usuarios:
                continue
            usuarios[email] = {
                "nombre": u.get("nombre", ""), "email": email,
                "legacy_sha256": u["password_hash"], "legacy_salt": u["salt"],
                "plan": u.get("plan", EXPLORER) if u.get("plan") in PLANES else EXPLORER,
                "tour_completado": bool(u.get("onboarding_completado")),
                "creado_en": u.get("creado_en", _ahora().isoformat()),
                "intentos_fallidos": 0, "bloqueado_hasta": None, "cuota_prismi": {},
                "historial_planes": [{"plan": u.get("plan", EXPLORER), "fecha": _ahora().isoformat(), "ref": "migracion"}],
            }
            n += 1
        self._guardar(usuarios)
        return n
