"""
Prisma BMV - Autenticación y control de acceso local (FastAPI).

La identidad productiva de Prisma BMV opera exclusivamente sobre Amazon Cognito +
DynamoDB (ver infra/api_gateway_aislada/handler.py). Supabase fue retirado.
Este módulo conserva el modelo `Usuario` y la matriz de planes para pruebas
y ejecución local de `api.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException

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


def limpiar_cache() -> None:
    """No-op tras el retiro de Supabase."""


def usuario_actual(authorization: str | None = Header(default=None)) -> Usuario:
    """Falla cerrado en local sin sesión Cognito verificada por API Gateway."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    raise HTTPException(
        status_code=410,
        detail="La autenticación legada fue retirada; usa la API de AWS con Amazon Cognito.",
    )


def requiere_admin(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    if not usuario.es_admin:
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador.")
    return usuario


def exigir_emisora(usuario: Usuario, emisora: str) -> None:
    if not usuario.puede_ver(emisora):
        raise HTTPException(
            status_code=403,
            detail=f"Tu plan ({usuario.plan}) no incluye {emisora}. Actualiza tu plan para acceder.",
        )


def _retirado() -> Any:
    raise HTTPException(
        status_code=410,
        detail="La administración de usuarios opera exclusivamente en AWS (Cognito + DynamoDB).",
    )


def listar_usuarios() -> list[dict[str, Any]]:
    return _retirado()


def crear_usuario(email: str, password: str, nombre: str, rol: str, plan: str) -> dict[str, Any]:
    return _retirado()


def actualizar_usuario(
    uid: str, *, rol: str | None = None, plan: str | None = None, nombre: str | None = None
) -> dict[str, Any]:
    return _retirado()
