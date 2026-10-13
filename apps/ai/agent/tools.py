"""Herramientas autorizadas del agente (SPEC §46A.5).

- Lectura (`READ_TOOLS`): puede proponerlas el LLM; se validan nombre,
  argumentos y siempre actúan sobre el usuario del estado.
- Escritura (`create_ticket`, `route_ticket`): NO están en `READ_TOOLS`; solo
  las invocan nodos determinísticos. Cambiar estados, asignar o tocar notas y
  deuda no existe como herramienta (SPEC §45).
"""

import re
from datetime import date

from django.contrib.auth import get_user_model

from apps.automation import responses
from apps.integrations.institutional.service import QUERY_METHODS, InstitutionalQueryService

TICKET_CODE = re.compile(r"^HD-\d{4}-\d{6}$")


class ToolNotAllowed(Exception):
    pass


def _ticket_status(user, channel, ticket_code=None):
    if ticket_code is not None and not TICKET_CODE.match(str(ticket_code)):
        raise ToolNotAllowed("Código de ticket con formato inválido.")
    return responses.ticket_status(user, ticket_code)


def _institutional(method):
    def run(user, channel, **kwargs):
        if "date" in kwargs:
            try:
                kwargs["date"] = date.fromisoformat(str(kwargs["date"]))
            except ValueError as exc:
                raise ToolNotAllowed("Fecha inválida.") from exc
        data = InstitutionalQueryService().query(user, method, **kwargs)
        extra = {"day": kwargs["date"]} if "date" in kwargs else {}
        return responses.format_query(method, data, channel=channel, **extra)

    return run


# nombre → (función, argumentos permitidos)
READ_TOOLS = {name: (_institutional(name), set()) for name in QUERY_METHODS}
READ_TOOLS["get_schedule"] = (_institutional("get_schedule"), {"date"})
READ_TOOLS["get_ticket_status"] = (_ticket_status, {"ticket_code"})


def run_read_tool(name, *, user_id, channel, args=None):
    """Ejecuta una herramienta de lectura validada. Devuelve el texto de respuesta."""
    if name not in READ_TOOLS:
        raise ToolNotAllowed(f"Herramienta no autorizada: {name!r}.")
    func, allowed = READ_TOOLS[name]
    args = {k: v for k, v in (args or {}).items() if v is not None}
    extra = set(args) - allowed
    if extra:
        raise ToolNotAllowed(f"Argumentos no permitidos: {', '.join(sorted(extra))}.")
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        raise ToolNotAllowed("Las herramientas actúan solo sobre el usuario autenticado.")
    return func(user, channel, **args)
