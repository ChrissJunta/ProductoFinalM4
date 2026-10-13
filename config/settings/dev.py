"""Configuración de desarrollo local.

Los valores de desarrollo solo se aplican si ni el entorno ni `.env` los definen:
el `.env` se lee ANTES de fijar los valores por defecto (hallazgo de seguridad de
BE-T20: antes los valores de desarrollo tapaban a los del `.env`).
"""

import os
from pathlib import Path

import environ

environ.Env.read_env(Path(__file__).resolve().parent.parent.parent / ".env")
os.environ.setdefault("DJANGO_SECRET_KEY", "dev-insecure-secret-key-no-usar-en-produccion")
os.environ.setdefault("DJANGO_DEBUG", "True")

from .base import *  # noqa: E402,F403

ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "[::1]"]  # noqa: F405

# WhatsApp simulado en desarrollo (ADR-049): secretos de prueba, no reales.
WHATSAPP_VERIFY_TOKEN = WHATSAPP_VERIFY_TOKEN or "dev-verify-token"  # noqa: F405
WHATSAPP_APP_SECRET = WHATSAPP_APP_SECRET or "dev-app-secret"  # noqa: F405
