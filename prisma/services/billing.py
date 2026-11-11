"""
Prisma BMV - Pasarela de pago simulada (entorno Sandbox).

Garantías:
* Solo acepta las tarjetas de prueba documentadas. Una tarjeta real con Luhn válido se
  rechaza con TARJETA_NO_ES_DE_PRUEBA para que nunca entren datos de pago reales.
* Nunca persiste el número completo ni el CVC: el libro de transacciones (cifrado) solo
  guarda marca, últimos 4 dígitos, monto, plan y resultado.
* La interfaz `cobrar()` es la misma que tendría un adaptador real (Stripe, Conekta, etc.),
  de modo que sustituir el sandbox no toca las vistas.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone

from prisma.plans import PLANES
from prisma.security.crypto import AlmacenCifrado

TARJETAS_PRUEBA = {
    "4242424242424242": ("APROBADA", None),
    "5555555555554444": ("APROBADA", None),
    "4000000000000002": ("RECHAZADA", "TARJETA_DECLINADA"),
    "4000000000009995": ("RECHAZADA", "FONDOS_INSUFICIENTES"),
}
MENSAJES_RECHAZO = {
    "TARJETA_DECLINADA": "El emisor rechazó la tarjeta. Use otra tarjeta de prueba.",
    "FONDOS_INSUFICIENTES": "Fondos insuficientes. Use otra tarjeta de prueba.",
    "TARJETA_NO_ES_DE_PRUEBA": "En el entorno sandbox solo se aceptan tarjetas de prueba.",
}


@dataclass(frozen=True)
class Transaccion:
    id: str
    email: str
    plan: str
    monto_usd: int
    marca: str
    ultimos4: str
    estado: str
    motivo: str | None
    fecha_utc: str
    entorno: str = "SANDBOX"


def luhn_valido(numero: str) -> bool:
    digitos = [int(d) for d in numero][::-1]
    total = 0
    for i, d in enumerate(digitos):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def marca_tarjeta(numero: str) -> str:
    if numero.startswith("4"):
        return "Visa"
    if re.match(r"^5[1-5]", numero) or re.match(r"^2[2-7]", numero):
        return "Mastercard"
    if re.match(r"^3[47]", numero):
        return "American Express"
    return "Otra"


def validar_datos(numero: str, vencimiento: str, cvc: str, titular: str, hoy: date | None = None) -> str | None:
    hoy = hoy or date.today()
    if not titular.strip():
        return "Escriba el nombre del titular."
    if not re.fullmatch(r"\d{13,19}", numero) or not luhn_valido(numero):
        return "El número de tarjeta no es válido."
    m = re.fullmatch(r"(0[1-9]|1[0-2])/(\d{2})", vencimiento.strip())
    if not m:
        return "Use el formato MM/AA para el vencimiento."
    mes, anio = int(m.group(1)), 2000 + int(m.group(2))
    if (anio, mes) < (hoy.year, hoy.month):
        return "La tarjeta está vencida."
    if not re.fullmatch(r"\d{3,4}", cvc):
        return "El CVC debe tener 3 o 4 dígitos."
    return None


class PasarelaSandbox:
    def __init__(self, libro: AlmacenCifrado):
        self._libro = libro

    def cobrar(self, email: str, plan_id: str, numero: str, vencimiento: str, cvc: str, titular: str) -> tuple[Transaccion | None, str]:
        if plan_id not in PLANES or PLANES[plan_id].precio_usd_mes == 0:
            return None, "Ese plan no requiere pago."
        numero = re.sub(r"[\s-]", "", numero)
        if err := validar_datos(numero, vencimiento, cvc, titular):
            return None, err

        estado, motivo = TARJETAS_PRUEBA.get(numero, ("RECHAZADA", "TARJETA_NO_ES_DE_PRUEBA"))
        tx = Transaccion(
            id=f"txn_sbx_{secrets.token_hex(8)}",
            email=email.strip().lower(),
            plan=plan_id,
            monto_usd=PLANES[plan_id].precio_usd_mes,
            marca=marca_tarjeta(numero),
            ultimos4=numero[-4:],
            estado=estado,
            motivo=motivo,
            fecha_utc=datetime.now(timezone.utc).isoformat(),
        )
        datos = self._libro.cargar()
        datos.setdefault("transacciones", []).append(asdict(tx))
        self._libro.guardar(datos)
        if estado != "APROBADA":
            return tx, MENSAJES_RECHAZO.get(motivo or "", "Pago rechazado.")
        return tx, "Pago aprobado."

    def historial(self, email: str) -> list[dict]:
        email = email.strip().lower()
        return [t for t in self._libro.cargar().get("transacciones", []) if t["email"] == email]
