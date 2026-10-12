"""Control de acceso vertical (por rol) y horizontal (por propietario).

Toda validación de permisos ocurre en backend (SPEC §8.5, §56.15).
"""

from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .roles import STAFF_ROLES, get_role, has_role


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


def is_owner(user, owner_id):
    return user.is_authenticated and user.pk == owner_id


def check_owner_or_staff(user, owner_id):
    """Control horizontal básico.

    Un Usuario solo accede a recursos propios. Los roles de atención pasan este
    control; su restricción por área/asignación corresponde a BE-T04.
    """
    if is_owner(user, owner_id) or get_role(user) in STAFF_ROLES:
        return
    raise PermissionDenied
