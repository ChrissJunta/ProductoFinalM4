"""Configuración de desarrollo local."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "dev-insecure-secret-key-no-usar-en-produccion")
os.environ.setdefault("DJANGO_DEBUG", "True")

from .base import *  # noqa: E402,F403

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
