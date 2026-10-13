"""Configuración de producción (BE-T20, ADR-067).

Sin valores por defecto inseguros: `DJANGO_SECRET_KEY` y `DJANGO_ALLOWED_HOSTS`
son obligatorios y `DEBUG` queda siempre en False. Lo usan por defecto
`config/wsgi.py` y `config/asgi.py`; para comandos (`migrate`, cron) exportar
`DJANGO_SETTINGS_MODULE=config.settings.prod`.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS es obligatorio en producción.")
if SECRET_KEY.startswith(("dev-", "test-", "cambiar-")) or len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY de producción: aleatoria y de 50+ caracteres.")
if WHATSAPP_APP_SECRET in ("dev-app-secret", "test-app-secret"):  # noqa: F405
    raise ImproperlyConfigured("WHATSAPP_APP_SECRET de desarrollo no admitido en producción.")
