"""
Migra el usuarios.json heredado (hashes SHA-256 en texto plano) al almacén cifrado.
Las contraseñas se convierten a PBKDF2 en el siguiente inicio de sesión de cada usuario.
Después de migrar, elimine usuarios.json.

Uso: PRISMA_MASTER_KEY=... python scripts/migrar_usuarios_legado.py ruta/usuarios.json
"""
import sys

import _ruta  # noqa: F401

from prisma.security.crypto import AlmacenCifrado, obtener_fernet
from prisma.services.auth import ServicioUsuarios
from prisma.settings import get_settings

if __name__ == "__main__":
    s = get_settings()
    f = obtener_fernet(s.llave_maestra, s.dir_estado, s.es_produccion)
    svc = ServicioUsuarios(AlmacenCifrado(s.dir_estado / "usuarios.enc", f), s.pbkdf2_iteraciones)
    print(f"Usuarios migrados: {svc.importar_legado(sys.argv[1])}")
