"""Genera una llave Fernet para PRISMA_MASTER_KEY. Guárdela en un gestor de secretos, nunca en el repositorio."""
from cryptography.fernet import Fernet

if __name__ == "__main__":
    print(Fernet.generate_key().decode())
