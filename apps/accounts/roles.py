"""Roles del sistema (SPEC §25), implementados como Groups de Django."""


class Role:
    USUARIO = "Usuario"
    AGENTE = "Agente"
    SUPERVISOR = "Supervisor"
    ADMINISTRADOR = "Administrador"


# De mayor a menor privilegio: un usuario con varios grupos asume el más alto.
ROLE_PRIORITY = [Role.ADMINISTRADOR, Role.SUPERVISOR, Role.AGENTE, Role.USUARIO]

STAFF_ROLES = frozenset({Role.AGENTE, Role.SUPERVISOR, Role.ADMINISTRADOR})


def get_role(user):
    """Devuelve el rol efectivo del usuario, o None si no está autenticado.

    Un superusuario es Administrador. Un usuario autenticado sin grupo recibe
    el rol de menor privilegio (Usuario).
    """
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return Role.ADMINISTRADOR
    if not hasattr(user, "_cached_role"):
        names = set(user.groups.values_list("name", flat=True))
        user._cached_role = next((r for r in ROLE_PRIORITY if r in names), Role.USUARIO)
    return user._cached_role


def has_role(user, *roles):
    return get_role(user) in roles
