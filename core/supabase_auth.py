"""
Prisma BMV - Autenticación y permisos con Supabase.

Reemplaza a core/auth.py (usuarios.json + SHA-256).

Variables de entorno (backend/.env o del sistema):
    SUPABASE_URL                ej. https://abcd1234.supabase.co
    SUPABASE_ANON_KEY           clave pública (anon / publishable)
    SUPABASE_SERVICE_ROLE_KEY   clave secreta. SOLO backend. Nunca al frontend.

Cómo valida: reenvía el token del usuario a Supabase (GET /auth/v1/user).
Funciona con cualquier algoritmo de firma y detecta tokens vencidos o
revocados. Después lee rol y plan de public.profiles con service_role.
Solo usa la librería estándar.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException

CACHE_TTL = 30  # segundos; un cambio de plan o rol tarda como máximo esto en verse

# ------------------------------------------------------------------------------
# Matriz de acceso (espejo de src/plans.mjs). El backend es la fuente de verdad.
# ------------------------------------------------------------------------------
TODAS = [
    "WALMEX", "GMEXICO", "GFNORTE", "AMX", "FEMSA", "CEMEX", "BIMBO", "GAP",
    "PE&OLES", "AC", "ASUR", "GFINBUR", "VESTA", "LIVEPOL", "GRUMA",
]
EMISORAS_POR_PLAN: dict[str, list[str]] = {
    "explorer": ["WALMEX"],
    "professional": TODAS,
    "enterprise": TODAS,
}
PLANES_VALIDOS = tuple(EMISORAS_POR_PLAN)
ROLES_VALIDOS = ("user", "admin")


@dataclass(frozen=True)
class Usuario:
    id: str
    email: str
    nombre: str
    rol: str
    plan: str

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin"

    @property
    def emisoras(self) -> list[str]:
        return EMISORAS_POR_PLAN.get(self.plan, EMISORAS_POR_PLAN["explorer"])

    def puede_ver(self, emisora: str) -> bool:
        return emisora in self.emisoras


# ------------------------------------------------------------------------------
# HTTP mínimo hacia Supabase
# ------------------------------------------------------------------------------
def _cfg(nombre: str) -> str:
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise HTTPException(status_code=500, detail=f"Falta configurar {nombre} en el servidor.")
    return valor


def _llamar(metodo: str, ruta: str, *, headers: dict[str, str], cuerpo: Any = None) -> Any:
    url = _cfg("SUPABASE_URL").rstrip("/") + ruta
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo)
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            texto = resp.read().decode() or "null"
            return json.loads(texto)
    except urllib.error.HTTPError as e:
        detalle = e.read().decode(errors="replace")
        try:
            detalle = json.loads(detalle).get("msg") or json.loads(detalle).get("message") or detalle
        except Exception:
            pass
        raise _SupabaseError(e.code, str(detalle)) from None
    except (urllib.error.URLError, TimeoutError):
        raise HTTPException(status_code=503, detail="No se pudo contactar el servicio de autenticación.") from None


class _SupabaseError(Exception):
    def __init__(self, status: int, detalle: str):
        super().__init__(detalle)
        self.status = status
        self.detalle = detalle


def _service_headers() -> dict[str, str]:
    key = _cfg("SUPABASE_SERVICE_ROLE_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}"}


# ------------------------------------------------------------------------------
# Caché corta (evita 2 llamadas a Supabase en cada petición del panel)
# ------------------------------------------------------------------------------
_cache: dict[str, tuple[float, Usuario]] = {}
_lock = threading.Lock()


def _cache_get(token: str) -> Usuario | None:
    with _lock:
        item = _cache.get(token)
        if item and item[0] > time.time():
            return item[1]
        _cache.pop(token, None)
    return None


def _cache_put(token: str, usuario: Usuario) -> None:
    with _lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[token] = (time.time() + CACHE_TTL, usuario)


def limpiar_cache() -> None:
    with _lock:
        _cache.clear()


# ------------------------------------------------------------------------------
# Dependencias de FastAPI
# ------------------------------------------------------------------------------
def usuario_actual(authorization: str | None = Header(default=None)) -> Usuario:
    """Exige 'Authorization: Bearer <jwt de Supabase>' y devuelve el usuario con rol y plan."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    token = authorization[7:].strip()

    en_cache = _cache_get(token)
    if en_cache:
        return en_cache

    try:
        auth_user = _llamar(
            "GET", "/auth/v1/user",
            headers={"apikey": _cfg("SUPABASE_ANON_KEY"), "Authorization": f"Bearer {token}"},
        )
    except _SupabaseError:
        raise HTTPException(status_code=401, detail="Sesión inválida o vencida. Inicia sesión de nuevo.") from None

    uid = auth_user.get("id")
    filas = _llamar(
        "GET",
        "/rest/v1/profiles?" + urllib.parse.urlencode({"id": f"eq.{uid}", "select": "id,email,nombre,rol,plan"}),
        headers=_service_headers(),
    )
    if not filas:
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene perfil. Contacta al administrador.")
    p = filas[0]
    usuario = Usuario(id=p["id"], email=p["email"], nombre=p.get("nombre") or "", rol=p["rol"], plan=p["plan"])
    _cache_put(token, usuario)
    return usuario


def requiere_admin(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    if not usuario.es_admin:
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador.")
    return usuario


def exigir_emisora(usuario: Usuario, emisora: str) -> None:
    """403 si el plan del usuario no incluye la emisora."""
    if not usuario.puede_ver(emisora):
        raise HTTPException(
            status_code=403,
            detail=f"Tu plan ({usuario.plan}) no incluye {emisora}. Actualiza tu plan para acceder.",
        )


# ------------------------------------------------------------------------------
# Operaciones de administración (usan service_role)
# ------------------------------------------------------------------------------
def listar_usuarios() -> list[dict[str, Any]]:
    return _llamar(
        "GET",
        "/rest/v1/profiles?select=id,email,nombre,rol,plan,creado_en&order=creado_en.desc",
        headers=_service_headers(),
    )


def crear_usuario(email: str, password: str, nombre: str, rol: str, plan: str) -> dict[str, Any]:
    if rol not in ROLES_VALIDOS:
        raise HTTPException(status_code=400, detail="Rol inválido.")
    if plan not in PLANES_VALIDOS:
        raise HTTPException(status_code=400, detail="Plan inválido.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres.")
    try:
        creado = _llamar(
            "POST", "/auth/v1/admin/users",
            headers=_service_headers(),
            # email_confirm=True: el usuario nace ya confirmado (alta hecha por el admin)
            cuerpo={"email": email, "password": password, "email_confirm": True, "user_metadata": {"nombre": nombre}},
        )
    except _SupabaseError as e:
        raise HTTPException(status_code=400, detail=f"No se pudo crear el usuario: {e.detalle}") from None
    # El trigger ya creó el perfil como user/explorer; aquí se ajusta rol y plan.
    return actualizar_usuario(creado["id"], rol=rol, plan=plan)


def actualizar_usuario(uid: str, *, rol: str | None = None, plan: str | None = None, nombre: str | None = None) -> dict[str, Any]:
    cambios: dict[str, str] = {}
    if rol is not None:
        if rol not in ROLES_VALIDOS:
            raise HTTPException(status_code=400, detail="Rol inválido.")
        cambios["rol"] = rol
    if plan is not None:
        if plan not in PLANES_VALIDOS:
            raise HTTPException(status_code=400, detail="Plan inválido.")
        cambios["plan"] = plan
    if nombre is not None:
        cambios["nombre"] = nombre
    if not cambios:
        raise HTTPException(status_code=400, detail="Nada que actualizar.")
    filas = _llamar(
        "PATCH",
        "/rest/v1/profiles?" + urllib.parse.urlencode({"id": f"eq.{uid}"}),
        headers={**_service_headers(), "Prefer": "return=representation"},
        cuerpo=cambios,
    )
    if not filas:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    limpiar_cache()
    return filas[0]
