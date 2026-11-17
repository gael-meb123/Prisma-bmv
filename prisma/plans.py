"""
Prisma BMV - Planes de suscripción y matriz de derechos (entitlements).

Toda decisión de acceso de la interfaz pasa por `tiene_acceso()`; ninguna vista compara
nombres de plan directamente. Así un cambio comercial se hace aquí y en ningún otro lugar.
"""

from __future__ import annotations

from dataclasses import dataclass

EXPLORER, PROFESSIONAL, ENTERPRISE = "explorer", "professional", "enterprise"
ORDEN_PLANES = (EXPLORER, PROFESSIONAL, ENTERPRISE)


@dataclass(frozen=True)
class Plan:
    id: str
    nombre: str
    precio_usd_mes: int
    resumen: str
    incluye: tuple[str, ...]
    color: str


PLANES: dict[str, Plan] = {
    EXPLORER: Plan(
        EXPLORER, "Explorer", 0,
        "Para conocer la plataforma y seguir el mercado con retraso.",
        (
            "Boletín BMV diferido una sesión (15 emisoras)",
            "Modelo base de 1ª generación para WALMEX",
            "Auditoría temporal de WALMEX",
            "Prismi con 5 consultas diarias a Claude",
        ),
        "#8A93A3",
    ),
    PROFESSIONAL: Plan(
        PROFESSIONAL, "Professional", 49,
        "Para analistas y operadores que necesitan la señal al cierre.",
        (
            "Boletín BMV al cierre del día (16:45 CDMX)",
            "Panel multiemisora G2: WALMEX, GMEXICO, GFNORTE y AMX",
            "Retorno relativo ret_10_rel_panel y descomposición de la señal",
            "Semáforo de consenso G1 + G2 y alertas de divergencia",
            "Auditoría t+1 a t+5 de todo el panel",
            "Prismi ilimitado con Claude",
        ),
        "#F2A900",
    ),
    ENTERPRISE: Plan(
        ENTERPRISE, "Enterprise", 249,
        "Para mesas de dinero y equipos cuantitativos que integran los datos.",
        (
            "Todo lo de Professional",
            "Consola SQL sobre el lakehouse (Amazon Athena / S3)",
            "Exportación masiva en CSV, Parquet y JSON",
            "Auditoría forense SHA-256 contra el boletín oficial",
        ),
        "#4CC3D9",
    ),
}

# Derecho -> plan mínimo que lo otorga
DERECHOS: dict[str, str] = {
    "boletin_al_cierre": PROFESSIONAL,
    "g1_todos_los_modelos": PROFESSIONAL,
    "panel_g2": PROFESSIONAL,
    "ret_10_rel_panel": PROFESSIONAL,
    "consenso_semaforo": PROFESSIONAL,
    "auditoria_panel_completo": PROFESSIONAL,
    "prismi_ilimitado": PROFESSIONAL,
    "lakehouse_athena": ENTERPRISE,
    "exportacion_masiva": ENTERPRISE,
    "auditoria_sha256_forense": ENTERPRISE,
}

RETRASO_BOLETIN_SESIONES = {EXPLORER: 1, PROFESSIONAL: 0, ENTERPRISE: 0}
EMISORAS_SENALES = {
    EXPLORER: ("WALMEX",),
    PROFESSIONAL: ("WALMEX", "GMEXICO", "GFNORTE", "AMX"),
    ENTERPRISE: ("WALMEX", "GMEXICO", "GFNORTE", "AMX"),
}


def nivel(plan_id: str) -> int:
    return ORDEN_PLANES.index(plan_id) if plan_id in ORDEN_PLANES else 0


def tiene_acceso(plan_id: str, derecho: str) -> bool:
    if derecho not in DERECHOS:
        raise KeyError(f"Derecho desconocido: {derecho}")
    return nivel(plan_id) >= nivel(DERECHOS[derecho])


def plan_minimo(derecho: str) -> Plan:
    return PLANES[DERECHOS[derecho]]
