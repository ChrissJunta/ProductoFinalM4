"""InstitutionalQueryService (SPEC §33): único punto de consulta al proveedor.

Solo expone lecturas del propio usuario (SPEC §46A.5, regla 3): el usuario se
pasa siempre desde el contexto autenticado, nunca desde el texto del mensaje.
"""

from . import get_provider
from .base import ProviderError

# Métodos de lectura del contrato (SPEC §39). `get_ticket_status` no es del
# proveedor: lo resuelve el helpdesk con los tickets del propio usuario.
QUERY_METHODS = ("get_schedule", "get_grades", "get_debt", "get_enrollment", "get_subjects")


class InstitutionalQueryService:
    def __init__(self, provider=None):
        self.provider = provider or get_provider()

    def query(self, user, method, **kwargs):
        """Ejecuta una lectura autorizada. Errores inesperados se convierten en ProviderError."""
        if method not in QUERY_METHODS:
            raise ValueError(f"Consulta institucional no autorizada: {method!r}.")
        if user is None or not user.is_authenticated:
            raise PermissionError("Las consultas institucionales requieren usuario autenticado.")
        try:
            return getattr(self.provider, method)(user, **kwargs)
        except ProviderError:
            raise
        except Exception as exc:  # proveedor caído, respuesta inválida, timeout…
            raise ProviderError(str(exc) or exc.__class__.__name__) from exc
