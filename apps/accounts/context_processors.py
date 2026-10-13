from .roles import get_role


def role(request):
    """Expone el rol efectivo a las plantillas para la navegación por rol."""
    return {"user_role": get_role(request.user)}
