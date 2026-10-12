"""Configuración para pytest y CI. Usa PostgreSQL real (SPEC §51)."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DJANGO_DEBUG", "False")

from .base import *  # noqa: E402,F403

ALLOWED_HOSTS = ["testserver", "localhost"]

# Hash rápido: las pruebas no evalúan la robustez del algoritmo.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
