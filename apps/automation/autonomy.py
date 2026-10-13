"""Autonomy Engine (SPEC §31, BE-T14): decide N0–N4 y ejecuta la acción.

La decisión es determinística (catálogo `Intent.automation_level` + confianza):
el LLM nunca elige el nivel. Los nombres de `path` son los nodos del grafo
LangGraph de SPEC §46A, que en BE-T18A envolverá estas mismas funciones.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from apps.helpdesk import alerts
from apps.helpdesk.models import Alert, Ticket
from apps.helpdesk.tickets import TicketService
from apps.integrations.institutional.base import ProviderError
from apps.integrations.institutional.service import InstitutionalQueryService

from . import responses
from .intents import identify_intent
from .models import AutomationLevel, Intent, IntentAction

L = AutomationLevel
A = IntentAction.ActionType

MIN_CONFIDENCE = 0.70  # por debajo → N4 (SPEC §46)
REVIEW_CONFIDENCE = 0.85  # 0.70–0.849 → revisión humana antes de N2/N3 (SPEC §46A.4)
MAX_MESSAGE_LENGTH = 5000  # = Ticket.description


@dataclass
class AutomationResult:
    response: str
    level: str
    intent_code: str | None
    confidence: float
    source: str = "RULES"
    ticket: Ticket | None = None
    requires_human: bool = False
    path: list[str] = field(default_factory=list)


def active_action(intent):
    if intent is None:
        return None
    return intent.actions.filter(is_active=True).first()


def determine_autonomy(intent, confidence, action=None):
    """Nivel N0–N4 para una intención ya clasificada."""
    if intent is None or confidence < MIN_CONFIDENCE:
        return L.N4
    level = intent.automation_level
    # Sin acción automática válida no se responde solo: baja a ticket (SPEC §31.1).
    if level == L.N0 and (action is None or action.action_type != A.PROVIDER_QUERY):
        return L.N3
    if level == L.N1 and (
        action is None
        or action.action_type != A.TEMPLATE_RESPONSE
        or not action.response_template.strip()
    ):
        return L.N3
    return level


def handle_message(*, text, user=None, channel=Ticket.Channel.WEB):
    """Punto de entrada único Web/WhatsApp (SPEC §32).

    `user=None` significa remitente no identificado (p. ej. número de WhatsApp sin
    verificar, SPEC §35.1): solo recibe respuestas que no requieren autenticación.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("El mensaje está vacío.")
    if user is not None and not user.is_authenticated:
        user = None
    text = text[:MAX_MESSAGE_LENGTH]

    match = identify_intent(text)
    path = ["classify_rules", "decide_autonomy"]
    action = active_action(match.intent)
    level = determine_autonomy(match.intent, match.confidence, action)
    result = AutomationResult(
        response="",
        level=level,
        intent_code=match.intent.code if match.intent else None,
        confidence=match.confidence,
        source=match.source,
        path=path,
    )
    return execute_intent_action(result, match, action, text=text, user=user, channel=channel)


def execute_intent_action(result, match, action, *, text, user, channel):
    intent, level, path = match.intent, result.level, result.path

    if intent is not None and intent.requires_authentication and user is None:
        path += ["check_auth", "respond_link_instructions"]
        result.response = responses.LINK_INSTRUCTIONS
        return result

    if level == L.N0:
        path += ["check_auth", "call_tool"]
        try:
            result.response = _query(action.provider_method, user, match.entities, channel)
        except ProviderError:
            # El proveedor falló: la solicitud no se pierde (SPEC §39).
            path.append("provider_error")
            fallback = L.N4 if action.fallback_action == A.HUMAN_REVIEW else L.N3
            return _ticket(result, match, text, user, channel, fallback, provider_failed=True)
        path.append("respond")
        return result

    if level == L.N1:
        path.append("respond_template")
        result.response = action.response_template.strip()
        return result

    return _ticket(result, match, text, user, channel, level)


def _query(method, user, entities, channel):
    if method == "get_ticket_status":
        return responses.ticket_status(user, entities.get("ticket_code"))
    data = InstitutionalQueryService().query(user, method)
    return responses.format_query(method, data, channel=channel)


@transaction.atomic
def _ticket(result, match, text, user, channel, level, provider_failed=False):
    if user is None:
        result.path.append("respond_link_instructions")
        result.response = responses.LOGIN_FOR_TICKET
        return result

    intent = match.intent or Intent.objects.filter(code="UNKNOWN_REQUEST").first()
    needs_review = level == L.N4 or (level in (L.N2, L.N3) and match.confidence < REVIEW_CONFIDENCE)
    ticket = TicketService.create(
        user=user,
        subject=intent.name if intent else "Solicitud no identificada",
        description=text,
        channel=channel,
        intent=intent,
        classification_source=Ticket.ClassificationSource.RULES if match.intent else "",
        classification_score=Decimal(str(match.confidence)) if match.intent else None,
    )
    result.path += ["create_ticket", "route_ticket"]
    if needs_review:
        result.path.append("human_review")
        detail = (
            f"candidatas: {', '.join(match.candidates)}"
            if match.ambiguous
            else f"intención {intent.code if intent else '—'}"
        )
        alerts.open_alert(
            ticket,
            Alert.Type.HUMAN_REVIEW,
            severity=Alert.Severity.WARNING,
            message=f"Revisar clasificación ({detail}, confianza {match.confidence:.2f})"[:255],
        )
    result.path.append("respond")
    result.level, result.ticket, result.requires_human = level, ticket, True
    result.response = responses.ticket_created(ticket, level, provider_failed=provider_failed)
    return result
