from django.conf import settings

from .roles import get_role


def role(request):
    """Expone el rol efectivo a las plantillas para la navegación por rol."""
    return {
        "user_role": get_role(request.user),
        "new_ticket_poll_seconds": settings.NEW_TICKET_POLL_SECONDS,  # CONTRACT-023
    }
