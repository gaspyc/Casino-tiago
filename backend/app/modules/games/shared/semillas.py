"""Semillas de los juegos provably fair.

Está compartido porque el esquema es el mismo en todos: el servidor se
compromete a un seed publicando su SHA-256 antes de que se juegue, y lo revela
después para que cualquiera pueda rehacer la cuenta.
"""

import hashlib
import secrets


def generar_server_seed() -> str:
    """Seed nuevo de 32 bytes del CSPRNG del sistema."""
    return secrets.token_hex(32)


def hashear_seed(server_seed: str) -> str:
    """El compromiso que se publica antes de jugar."""
    return hashlib.sha256(server_seed.encode()).hexdigest()
