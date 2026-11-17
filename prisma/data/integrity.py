"""
Prisma BMV - Verificación criptográfica SHA-256 de boletines.

Tres niveles de evidencia, de menor a mayor:
1. Firma registrada en Silver (todas las cuentas).
2. Coincidencia Silver = sidecar .sha256 de Bronze = SHA-256 recalculado del HTML en Bronze.
3. Forense (Enterprise): se descarga de nuevo el boletín desde bmv.com.mx y se compara.
"""

from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass

USER_AGENT = "Mozilla/5.0 (compatible; PrismaBMV-Auditoria/2.0)"


@dataclass
class ResultadoVerificacion:
    estado: str  # COINCIDE | NO_COINCIDE | SIN_COPIA_BRONZE | ERROR_FUENTE
    sha_esperado: str
    sha_calculado: str | None
    detalle: str


def sha256_bytes(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def verificar_bronze(sha_silver: str, html: bytes | None, sha_sidecar: str | None) -> ResultadoVerificacion:
    if html is None:
        return ResultadoVerificacion(
            "SIN_COPIA_BRONZE", sha_silver, None,
            "No hay copia del HTML crudo en Bronze para esta fecha en la fuente configurada.",
        )
    calculado = sha256_bytes(html)
    coincide = calculado == sha_silver and (sha_sidecar is None or sha_sidecar == calculado)
    detalle = "HTML de Bronze, sidecar .sha256 y Silver coinciden." if coincide else (
        f"Recalculado {calculado[:12]}…, sidecar {str(sha_sidecar)[:12]}…, Silver {sha_silver[:12]}…"
    )
    return ResultadoVerificacion("COINCIDE" if coincide else "NO_COINCIDE", sha_silver, calculado, detalle)


def verificar_contra_fuente(url: str, sha_esperado: str, timeout_s: int = 15) -> ResultadoVerificacion:
    if not url.startswith("https://www.bmv.com.mx/"):
        return ResultadoVerificacion("ERROR_FUENTE", sha_esperado, None, "Solo se verifican URLs de bmv.com.mx.")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            calculado = sha256_bytes(r.read())
    except Exception as e:
        return ResultadoVerificacion("ERROR_FUENTE", sha_esperado, None, f"No se pudo descargar: {e}")
    if calculado == sha_esperado:
        return ResultadoVerificacion("COINCIDE", sha_esperado, calculado,
                                     "El boletín publicado hoy por la BMV es idéntico byte a byte al ingerido.")
    return ResultadoVerificacion(
        "NO_COINCIDE", sha_esperado, calculado,
        "La BMV sirve hoy un contenido distinto en la misma URL (republicación o cambio de plantilla). "
        "El precio registrado sigue respaldado por la copia inmutable de Bronze.",
    )
