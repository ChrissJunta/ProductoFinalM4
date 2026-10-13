"""Integración institucional (SPEC §39-§41).

La lógica de negocio obtiene el proveedor con `get_provider()` y consulta a
través de `InstitutionalQueryService`; nunca instancia un proveedor concreto.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_provider():
    """Proveedor configurado en `INSTITUTIONAL_PROVIDER` (SPEC §39)."""
    name = settings.INSTITUTIONAL_PROVIDER
    if name == "local":
        from .local import LocalProvider

        return LocalProvider()
    if name == "sga":
        from .sga import SGAProvider

        if not settings.SGA_BASE_URL:
            raise ImproperlyConfigured("INSTITUTIONAL_PROVIDER=sga requiere SGA_BASE_URL.")
        return SGAProvider(
            settings.SGA_BASE_URL, token=settings.SGA_TOKEN, timeout=settings.SGA_TIMEOUT
        )
    raise ImproperlyConfigured(f"INSTITUTIONAL_PROVIDER desconocido: {name!r}.")
