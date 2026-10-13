from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts import ratelimit
from apps.accounts.permissions import role_required
from apps.accounts.roles import Role
from apps.helpdesk.models import Ticket

from .forms import AssistantForm
from .services import AutomationService

SESSION_KEY = "assistant_exchange"
EXAMPLES = [
    "¿Cuál es mi horario de hoy?",
    "¿Cuáles son mis notas?",
    "¿Cuánto debo?",
    "Ya pagué y sigue apareciendo la deuda",
    "¿Cuáles son los requisitos para un certificado?",
]


@role_required(Role.USUARIO)
@require_http_methods(["GET", "POST"])
def assistant(request):
    """CONTRACT-014: canal web del agente de atención (SPEC §46A.7, CA-001 a CA-003).

    POST → Autonomy Engine → redirect (PRG). La última respuesta se muestra una vez.
    """
    form = AssistantForm(request.POST or None)
    if request.method == "POST" and ratelimit.hit("assistant", request.user.pk):
        form.add_error(None, "Ha enviado demasiadas consultas seguidas. Espere unos minutos.")
        context = {"form": form, "exchange": None, "examples": EXAMPLES}
        return render(request, "automation/assistant.html", context, status=429)
    if request.method == "POST" and form.is_valid():
        text = form.cleaned_data["message"]
        result = AutomationService.handle_message(
            text=text, user=request.user, channel=Ticket.Channel.WEB
        )
        request.session[SESSION_KEY] = {
            "question": text,
            "response": result.response,
            "level": result.level,
            "intent_code": result.intent_code,
            "ticket_code": result.ticket.ticket_code if result.ticket else None,
        }
        return redirect("automation:assistant")
    exchange = request.session.pop(SESSION_KEY, None) if request.method == "GET" else None
    return render(
        request,
        "automation/assistant.html",
        {"form": form, "exchange": exchange, "examples": EXAMPLES},
    )
