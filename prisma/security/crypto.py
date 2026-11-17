"""
Prisma BMV - Primitivas de seguridad.

* Contraseñas: PBKDF2-HMAC-SHA256 con sal aleatoria de 16 bytes y 600 000 iteraciones
  (recomendación OWASP vigente). El número de iteraciones viaja dentro del hash, de modo
  que se puede endurecer sin invalidar cuentas existentes.
* Persistencia: el almacén de usuarios y el libro de pagos se guardan cifrados con Fernet
  (AES-128-CBC + HMAC-SHA256, autenticado). Un archivo alterado no se descifra.
* La llave maestra llega por PRISMA_MASTER_KEY. Solo en desarrollo se genera una llave
  local en .estado/llave_maestra.key (permisos 0600) para no bloquear el arranque.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

ALGORITMO = "pbkdf2_sha256"


class ErrorConfiguracionSeguridad(RuntimeError):
    pass


def hash_password(password: str, iteraciones: int) -> str:
    sal = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, iteraciones)
    return "$".join(
        (ALGORITMO, str(iteraciones), base64.b64encode(sal).decode(), base64.b64encode(dk).decode())
    )


def verificar_password(password: str, codificado: str) -> bool:
    try:
        algoritmo, iter_txt, sal_b64, dk_b64 = codificado.split("$")
        if algoritmo != ALGORITMO:
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(sal_b64), int(iter_txt)
        )
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except (ValueError, TypeError):
        return False


def requiere_rehash(codificado: str, iteraciones: int) -> bool:
    try:
        algoritmo, iter_txt, *_ = codificado.split("$")
        return algoritmo != ALGORITMO or int(iter_txt) < iteraciones
    except ValueError:
        return True


def verificar_password_legado(password: str, hash_hex: str, sal: str) -> bool:
    """Formato heredado sha256(sal + password). Solo se usa para migrar al iniciar sesión."""
    calculado = hashlib.sha256((sal + password).encode("utf-8")).hexdigest()
    return hmac.compare_digest(calculado, hash_hex)


def obtener_fernet(llave_maestra: str, dir_estado: Path, es_produccion: bool) -> Fernet:
    if llave_maestra:
        try:
            return Fernet(llave_maestra.encode())
        except (ValueError, TypeError) as e:
            raise ErrorConfiguracionSeguridad(
                "PRISMA_MASTER_KEY no es una llave Fernet válida (32 bytes en base64 url-safe)."
            ) from e
    if es_produccion:
        raise ErrorConfiguracionSeguridad(
            "PRISMA_MASTER_KEY es obligatoria en producción. Genérela con "
            "`python scripts/generar_llave_maestra.py`."
        )
    dir_estado.mkdir(parents=True, exist_ok=True)
    ruta = dir_estado / "llave_maestra.key"
    if not ruta.exists():
        ruta.write_bytes(Fernet.generate_key())
        os.chmod(ruta, 0o600)
    return Fernet(ruta.read_bytes().strip())


class AlmacenCifrado:
    """Documento JSON cifrado en disco con escritura atómica.

    Adecuado para un despliegue de una sola instancia. Para varias réplicas, el mismo
    contrato (cargar/guardar) se implementa sobre DynamoDB o RDS con cifrado KMS.
    """

    _candado = threading.RLock()

    def __init__(self, ruta: Path, fernet: Fernet):
        self.ruta = ruta
        self._fernet = fernet

    def cargar(self) -> dict[str, Any]:
        with self._candado:
            if not self.ruta.exists():
                return {}
            try:
                claro = self._fernet.decrypt(self.ruta.read_bytes())
            except InvalidToken as e:
                raise ErrorConfiguracionSeguridad(
                    f"No se pudo descifrar {self.ruta.name}: llave incorrecta o archivo alterado."
                ) from e
            return json.loads(claro.decode("utf-8"))

    def guardar(self, datos: dict[str, Any]) -> None:
        with self._candado:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            cifrado = self._fernet.encrypt(json.dumps(datos, ensure_ascii=False).encode("utf-8"))
            fd, tmp = tempfile.mkstemp(dir=self.ruta.parent, prefix=".tmp_")
            with os.fdopen(fd, "wb") as f:
                f.write(cifrado)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.ruta)
