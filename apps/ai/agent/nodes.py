"""Nodos del grafo (SPEC §46A.4). Cada nodo devuelve una actualización parcial del
estado y añade su nombre a `node_path`.

Los nodos reutilizan los motores existentes (Intent Engine BE-T13, Autonomy
Engine BE-T14, InstitutionalQueryService BE-T15, AIService BE-T17): el grafo
decide el orden; la lógica de negocio sigue en los servicios.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from langgraph.types import interrupt

from apps.automation import responses
from apps.automation.autonomy import (
    MIN_CONFIDENCE,
    REVIEW_CONFIDENCE,
    active_action,
    determine_autonomy,
)
from apps.automation.catalog import category_for
from apps.automation.intents import identify_intent, normalize
from apps.automation.models import AutomationLevel, Intent, IntentAction
from apps.automation.services import AutomationService
from apps.helpdesk import alerts
from apps.helpdesk.conversations import get_conversation
from apps.helpdesk.models import Alert, Category, Subcategory, Ticket
from apps.helpdesk.tickets import TicketService
from apps.integrations.institutional.base import ProviderError

from .. import policies
from ..service import AIInvalidOutput, AIService, AIUnavailable
from .tools import ToolNotAllowed, run_read_tool

L = AutomationLevel
A = IntentAction.ActionType
CONTEXT_WINDOW = timedelta(minutes=30)  # memoria de conversación para CA-010
CONTEXT_CONFIDENCE = 0.85


def _step(name, **update):
    return {"node_path": [name], **update}


def _user(state):
    if not state.get("user_id"):
        return None
    return get_user_model().objects.filter(pk=state["user_id"], is_active=True).first()


def _intent(code):
    return Intent.objects.filter(code=code, is_active=True).first() if code else None


def _date_entity(norm):
    today = timezone.localdate()
    if "pasado manana" in norm:
        return (today + timedelta(days=2)).isoformat()
    if "manana" in norm.split():
        return (today + timedelta(days=1)).isoformat()
    return None


# --- Percepción ------------------------------------------------------------------------


def load_context(state):
    """Usuario, verificación y memoria de la conversación (SPEC §46A.6)."""
    user = _user(state)
    update = {"is_verified": bool(user) and state.get("is_verified", True)}
    if user is not None:
        conversation = get_conversation(user, state["channel"])
        recent = (
            conversation.last_message_at
            and timezone.now() - conversation.last_message_at <= CONTEXT_WINDOW
        )
        update["entities"] = {
            "previous_intent": conversation.active_intent if recent else "",
        }
    else:
        update["user_id"] = None
    return _step("load_context", **update)


# --- Razonamiento: Intent Engine ------------------------------------------------------------


def classify_rules(state):
    entities = dict(state.get("entities") or {})
    match = identify_intent(state["message"])
    norm = normalize(state["message"])
    if (day := _date_entity(norm)) is not None:
        entities["date"] = day
    entities.update(match.entities)
    if match.intent is not None:
        return _step(
            "classify_rules",
            intent=match.intent.code,
            confidence=match.confidence,
            classification_source="RULES",
            candidates=list(match.candidates),
            entities=entities,
        )
    previous = entities.get("previous_intent")
    if previous and norm.startswith("y ") and _intent(previous):
        # CA-010: «¿y mañana?» continúa la consulta anterior de la misma conversación.
        return _step(
            "classify_rules",
            intent=previous,
            confidence=CONTEXT_CONFIDENCE,
            classification_source="RULES",
            candidates=[previous],
            entities={**entities, "from_context": True},
        )
    return _step(
        "classify_rules",
        intent=None,
        confidence=match.confidence,
        candidates=list(match.candidates),
        entities=entities,
    )


def classify_llm(state):
    """Solo se visita si las reglas no resolvieron (SPEC §30)."""
    service = AIService()
    try:
        result = service.classify(state["message"])
    except AIUnavailable as exc:
        return _step(
            "classify_llm",
            errors=[f"LLM no disponible: {exc}"],
            attempts=len(str(exc).split(";")),
            llm_raw="",
        )
    except AIInvalidOutput as exc:
        return _step("classify_llm", errors=[f"Salida LLM inválida: {exc}"], llm_raw=exc.raw)
    return _step(
        "classify_llm",
        intent=result.intent.code,
        confidence=result.confidence,
        classification_source="LLM",
        category=result.category.code if result.category else None,
        subcategory=result.subcategory.code if result.subcategory else None,
        summary=result.summary,
        llm_raw=result.raw,
        candidates=[result.intent.code],
    )


def validate_output(state):
    """Sin clasificación válida o confianza < 0.70 → revisión humana (SPEC §46)."""
    if state.get("classification_source") != "LLM":
        return _step("validate_output", classification_valid=False)
    if (state.get("confidence") or 0) < MIN_CONFIDENCE:
        return _step("validate_output", classification_valid=False, errors=["LLM: confianza baja"])
    return _step("validate_output", classification_valid=True)


# --- Decisión -------------------------------------------------------------------------------


def decide_autonomy(state):
    intent = _intent(state.get("intent")) if state.get("classification_valid", True) else None
    confidence = state.get("confidence") or 0.0
    level = determine_autonomy(intent, confidence, active_action(intent))
    needs_review = level == L.N4 or (level in (L.N2, L.N3) and confidence < REVIEW_CONFIDENCE)
    # Decisiones propias del agente D1/D2 (ADR-077): política de revisión por intención.
    needs_review, policy = policies.review_decision(intent, level, needs_review)
    update = {"policy": policy} if policy else {}
    return _step(
        "decide_autonomy",
        autonomy_level=level,
        needs_review=needs_review,
        requires_human=level in (L.N2, L.N3, L.N4),
        **update,
    )


def check_auth(state):
    return _step("check_auth")


def respond_link_instructions(state):
    ticket_level = state.get("autonomy_level") in (L.N2, L.N3, L.N4)
    text = responses.LOGIN_FOR_TICKET if ticket_level else responses.LINK_INSTRUCTIONS
    return _step("respond_link_instructions", response=text)


# --- Acción ------------------------------------------------------------------------------------


def call_tool(state):
    """Consulta de lectura autorizada (N0). Un error del proveedor no pierde la solicitud."""
    action = active_action(_intent(state["intent"]))
    entities = state.get("entities") or {}
    args = {}
    if action.provider_method == "get_ticket_status":
        args["ticket_code"] = entities.get("ticket_code")
    if action.provider_method == "get_schedule" and entities.get("date"):
        args["date"] = entities["date"]
    call = {"tool": action.provider_method, "ok": True}
    try:
        text = run_read_tool(
            action.provider_method, user_id=state["user_id"], channel=state["channel"], args=args
        )
    except (ProviderError, ToolNotAllowed) as exc:
        call["ok"] = False
        level = L.N4 if action.fallback_action == A.HUMAN_REVIEW else L.N3
        return _step(
            "call_tool",
            tool_calls=[call],
            errors=[f"{action.provider_method}: {exc.__class__.__name__}"],
            autonomy_level=level,
            needs_review=level == L.N4,
            requires_human=True,
        )
    return _step("call_tool", tool_calls=[call], response=text)


def respond(state):
    return _step("respond")


def respond_template(state):
    action = active_action(_intent(state["intent"]))
    template = action.response_template.strip()
    # El LLM solo puede reformular sin añadir hechos; si no, se usa la plantilla (SPEC §31.1).
    return _step("respond_template", response=AIService().generate_response(template))


@transaction.atomic
def create_ticket(state):
    """Herramienta de escritura: solo este nodo determinístico la invoca."""
    user = _user(state)
    valid = state.get("classification_valid", True) and _intent(state.get("intent")) is not None
    intent = _intent(state["intent"]) if valid else _intent("UNKNOWN_REQUEST")
    if valid and state.get("category"):
        category = Category.objects.filter(code=state["category"], is_active=True).first()
        subcategory = (
            Subcategory.objects.filter(
                category=category, code=state.get("subcategory"), is_active=True
            ).first()
            if category and state.get("subcategory")
            else None
        )
    else:
        category, subcategory = category_for(intent.code if intent else "")
    ticket = TicketService.create(
        user=user,
        subject=intent.name if intent else "Solicitud no identificada",
        description=state["message"],
        channel=state["channel"],
        intent=intent,
        category=category,
        subcategory=subcategory,
        classification_source=state.get("classification_source", "") if valid else "",
        classification_score=Decimal(str(state["confidence"])) if valid else None,
    )
    return _step("create_ticket", ticket_id=ticket.pk, ticket_code=ticket.ticket_code)


def route_ticket(state):
    """El routing ya se aplicó al crear (BE-T09); aquí se deja constancia de la regla usada."""
    ticket = Ticket.objects.select_related("assigned_area").get(pk=state["ticket_id"])
    rule = AutomationService.matching_rule(
        intent_id=ticket.intent_id,
        category_id=ticket.category_id,
        subcategory_id=ticket.subcategory_id,
    )
    return _step(
        "route_ticket",
        tool_calls=[
            {
                "tool": "route_ticket",
                "ok": True,
                "area": ticket.assigned_area.code if ticket.assigned_area_id else None,
                "rule_id": rule.pk if rule else None,
            }
        ],
    )


def respond_ticket(state):
    ticket = Ticket.objects.select_related("assigned_area").get(pk=state["ticket_id"])
    provider_failed = any(not c.get("ok", True) for c in state.get("tool_calls") or [])
    text = responses.ticket_created(
        ticket, state["autonomy_level"], provider_failed=provider_failed
    )
    return _step("respond_ticket", response=text)


def request_review(state):
    """Abre la alerta HUMAN_REVIEW. Va separado de `human_review` porque LangGraph
    re-ejecuta el nodo interrumpido al reanudar y la alerta no debe duplicarse."""
    ticket = Ticket.objects.get(pk=state["ticket_id"])
    candidates = state.get("candidates") or []
    detail = (
        f"candidatas: {', '.join(candidates)}"
        if len(candidates) > 1
        else f"intención {state.get('intent') or '—'}"
    )
    alerts.open_alert(
        ticket,
        Alert.Type.HUMAN_REVIEW,
        severity=Alert.Severity.WARNING,
        message=(f"Revisar clasificación ({detail}, confianza {state.get('confidence') or 0:.2f})")[
            :255
        ],
    )
    return _step("request_review")


def human_review(state):
    """Pausa el hilo hasta que un Agente/Supervisor decide (SPEC §46A.4, `interrupt`).

    La respuesta al usuario ya se envió: la pausa no lo deja esperando.
    """
    candidates = state.get("candidates") or []
    decision = interrupt(
        {
            "ticket_code": state["ticket_code"],
            "intent": state.get("intent"),
            "candidates": candidates,
            "confidence": state.get("confidence"),
        }
    )
    return _step("human_review", review=decision)


def apply_review(state):
    """La decisión humana ya fue aplicada y auditada por `runner.resume_agent`."""
    return _step("apply_review")
