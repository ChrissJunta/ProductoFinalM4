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
        raise ImproperlyConfigured("SGAProvider aún no está disponible (BE-T19).")
    raise ImproperlyConfigured(f"INSTITUTIONAL_PROVIDER desconocido: {name!r}.")
