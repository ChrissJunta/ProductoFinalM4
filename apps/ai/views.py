from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.helpdesk import queries

from .agent.runner import REVIEW_ACTIONS, can_review, resume_agent

LABELS = {"accept": "aceptada", "correct": "corregida", "reject": "rechazada"}


@login_required
@require_POST
def ticket_review(request, code):
    """CONTRACT-015: decisión humana sobre la clasificación del agente (reanuda el grafo)."""
    ticket = queries.get_visible_ticket_or_404(request.user, code)
    if not can_review(request.user, ticket):
        raise PermissionDenied
    action = request.POST.get("action", "")
    if action not in REVIEW_ACTIONS:
        messages.error(request, "Acción de revisión inválida.")
        return redirect("helpdesk:ticket_detail", code=code)
    try:
        resume_agent(
            ticket, actor=request.user, action=action, intent_code=request.POST.get("intent")
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, f"Clasificación {LABELS[action]}.")
    return redirect("helpdesk:ticket_detail", code=code)
