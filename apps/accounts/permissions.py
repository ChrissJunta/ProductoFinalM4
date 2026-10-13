"""Control de acceso vertical (por rol).

El control horizontal (qué tickets puede ver cada usuario) vive en
`apps.helpdesk.queries` (BE-T04). Toda validación ocurre en backend (SPEC §8.5, §56.15).
"""

from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .roles import has_role


def role_required(*roles):
    """Decorador de vista: exige sesión y uno de los roles indicados."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not has_role(request.user, *roles):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


class RoleRequiredMixin(AccessMixin):
    """Equivalente a `role_required` para vistas basadas en clase."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not has_role(request.user, *self.allowed_roles):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
