"""Checks de seguridad (`manage.py check --deploy`, ADR-075)."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.checks import Tags, Warning, register
from django.db import DatabaseError

from .passwords import LEGACY_DEMO_PASSWORD

DEMO_USERNAMES = ("usuario", "agente_ti", "agente_fin", "supervisor", "admin")


@register(Tags.security, deploy=True)
def check_public_demo_password(app_configs, **kwargs):
    """Avisa si un usuario demo activo conserva la contraseña publicada en el repositorio."""
    try:
        users = list(get_user_model().objects.filter(username__in=DEMO_USERNAMES, is_active=True))
    except DatabaseError:  # base sin migrar: no hay nada que revisar
        return []
    exposed = [u.username for u in users if u.check_password(LEGACY_DEMO_PASSWORD)]
    if not exposed:
        return []
    return [
        Warning(
            f"Usuarios con la contraseña demo pública: {', '.join(sorted(exposed))}.",
            hint="Ejecute `python manage.py seed_demo --rotate` o `reset_password <usuario>`.",
            id="accounts.W001",
        )
    ]


@register(Tags.security, deploy=True)
def check_admin_url(app_configs, **kwargs):
    if settings.ADMIN_URL == "admin/":
        return [
            Warning(
                "El admin de Django está en la ruta por defecto /admin/.",
                hint="Defina DJANGO_ADMIN_URL con una ruta difícil de adivinar.",
                id="accounts.W002",
            )
        ]
    return []
