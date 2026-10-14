"""Contraseñas generadas por el sistema (ADR-072)."""

import secrets
import string

ALPHABET = string.ascii_letters + string.digits
# Contraseña pública de versiones anteriores de `seed_demo`: el check de despliegue
# avisa si alguna cuenta activa la sigue usando.
LEGACY_DEMO_PASSWORD = "Demo-2026!"


def generate(length=14):
    """Contraseña aleatoria criptográficamente segura con letras y números."""
    while True:
        value = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if any(c.isdigit() for c in value) and any(c.isalpha() for c in value):
            return value
