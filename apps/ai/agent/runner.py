"""Ejecución del agente: `run_agent(...)` y `resume_agent(...)` (SPEC §46A.2, §46A.7).

Hilos: cada mensaje se ejecuta en su propio hilo (`run-…`). La memoria entre
mensajes vive en `Conversation` (intención activa y hora del último mensaje),
porque en LangGraph un mensaje nuevo en un hilo pausado descarta la revisión
humana pendiente (CR-008). El hilo pausado se reanuda con `resume_agent`.
"""

import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone
from langgraph.types import Command

from apps.accounts.roles import Role, has_role
from apps.automation.catalog import category_for
from apps.automation.models import Intent
from apps.automation.services import AutomationService
from apps.helpdesk import alerts, audit, queries, sla
from apps.helpdesk.conversations import get_conversation
from apps.helpdesk.models import Alert, Ticket
from apps.helpdesk.tickets import TicketService

from ..models import AIDecision, Operation
from ..service import AIService
from .graph import GRAPH_VERSION, build_graph

logger = logging.getLogger(__name__)

REVIEW_ACTIONS = ("accept", "correct", "reject")
FALLBACK_RESPONSE = "Registramos tu solicitud {code}. Un agente la revisará para orientarte."
_graph = None
_saver = None


@dataclass
class AgentResult:
    response: str
    level: str
    intent_code: str | None
    confidence: float
    source: str
    ticket: Ticket | None
    requires_human: bool
    path: list[str]
    thread_id: str
    decision: AIDecision | None = None
    pending_review: bool = False
    errors: list[str] = field(default_factory=list)


# --- Checkpointer y grafo compilado (singletons de proceso) --------------------------------


def get_checkpointer():
    global _saver
    if _saver is not None:
        return _saver
    if settings.AGENT_CHECKPOINTER == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        _saver = InMemorySaver()
        return _saver
    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row

    db = connection.settings_dict
    conn = psycopg.connect(
        dbname=db["NAME"],
        user=db["USER"],
        password=db["PASSWORD"],
        host=db["HOST"] or None,
        port=db["PORT"] or None,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )
    saver = PostgresSaver(conn)
    saver.setup()  # crea/actualiza sus tablas propias; idempotente
    _saver = saver
    return _saver


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph(checkpointer=get_checkpointer())
    return _graph


def reset():
    """Solo pruebas: descarta grafo y checkpointer del proceso (cierra su conexión)."""
    global _graph, _saver
    conn = getattr(_saver, "conn", None)
    if conn is not None:
        conn.close()
    _graph, _saver = None, None


def _config(thread_id):
    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.AGENT_MAX_STEPS,
    }


# --- Ejecución -------------------------------------------------------------------------------


def run_agent(*, text, user=None, channel=Ticket.Channel.WEB, is_verified=True):
    """Procesa un mensaje con el grafo. Nunca pierde la solicitud (SPEC §46A, BE-T18A)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("El mensaje está vacío.")
    if user is not None and not user.is_authenticated:
        user = None
    text = text[:5000]
    thread_id = f"run-{uuid.uuid4().hex}"
    initial = {
        "thread_id": thread_id,
        "user_id": user.pk if user else None,
        "channel": channel,
        "is_verified": bool(user) and is_verified,
        "message": text,
        "entities": {},
        "candidates": [],
        "tool_calls": [],
        "errors": [],
        "node_path": [],
        "attempts": 0,
    }
    try:
        state = get_graph().invoke(initial, _config(thread_id))
    except Exception as exc:  # error del grafo, límite de pasos, bug: la solicitud sigue
        logger.exception("Fallo del agente en %s", thread_id)
        state = _fallback(initial, user, exc)
    pending = bool(state.get("__interrupt__"))
    ticket = Ticket.objects.filter(pk=state.get("ticket_id")).first()
    decision = _record(state, user, ticket, pending)
    if user is not None:
        conversation = get_conversation(user, channel)
        conversation.active_intent = state.get("intent") or ""
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["active_intent", "last_message_at"])
    return AgentResult(
        response=state.get("response") or "",
        level=state.get("autonomy_level") or "N4",
        intent_code=state.get("intent") if state.get("classification_valid", True) else None,
        confidence=state.get("confidence") or 0.0,
        source=state.get("classification_source") or "",
        ticket=ticket,
        requires_human=bool(state.get("requires_human")),
        path=list(state.get("node_path") or []),
        thread_id=thread_id,
        decision=decision,
        pending_review=pending,
        errors=list(state.get("errors") or []),
    )


@transaction.atomic
def _fallback(initial, user, exc):
    """Fuera del grafo y sin LLM: ticket N4 + alerta, o instrucciones si no hay usuario."""
    state = {
        **initial,
        "autonomy_level": "N4",
        "requires_human": True,
        "errors": [f"{exc.__class__.__name__}: {exc}"[:300]],
        "node_path": ["agent_error"],
    }
    if user is None:
        from apps.automation.responses import LOGIN_FOR_TICKET

        return {**state, "response": LOGIN_FOR_TICKET}
    unknown = Intent.objects.filter(code="UNKNOWN_REQUEST").first()
    category, subcategory = category_for("UNKNOWN_REQUEST")
    ticket = TicketService.create(
        user=user,
        subject=unknown.name if unknown else "Solicitud no identificada",
        description=initial["message"],
        channel=initial["channel"],
        intent=unknown,
        category=category,
        subcategory=subcategory,
    )
    alerts.open_alert(
        ticket,
        Alert.Type.HUMAN_REVIEW,
        severity=Alert.Severity.WARNING,
        message="El agente falló al procesar el mensaje; revisar manualmente.",
    )
    return {
        **state,
        "ticket_id": ticket.pk,
        "ticket_code": ticket.ticket_code,
        "response": FALLBACK_RESPONSE.format(code=ticket.ticket_code),
    }


def _record(state, user, ticket, pending):
    """AIDecision por ejecución con versión del grafo y recorrido (SPEC §43, §46A.7)."""
    used_llm = "classify_llm" in (state.get("node_path") or [])
    confidence = state.get("confidence")
    return AIDecision.objects.create(
        ticket=ticket,
        user=user,
        prompt_version=AIService.prompt_for(Operation.CLASSIFY) if used_llm else None,
        operation=Operation.AGENT_RUN,
        channel=state.get("channel", ""),
        intent_code=state.get("intent") or "",
        autonomy_level=state.get("autonomy_level") or "",
        classification_source=state.get("classification_source") or "",
        raw_output=state.get("llm_raw") or "",
        parsed_output={
            "intent": state.get("intent"),
            "candidates": state.get("candidates") or [],
            "category": state.get("category"),
            "subcategory": state.get("subcategory"),
            "summary": state.get("summary") or "",
            "classification_valid": state.get("classification_valid", True),
            "tool_calls": state.get("tool_calls") or [],
        },
        confidence=Decimal(str(round(confidence, 3))) if confidence is not None else None,
        requires_human=pending,
        graph_version=GRAPH_VERSION,
        node_path=list(state.get("node_path") or []),
        thread_id=state["thread_id"],
        errors=list(state.get("errors") or []),
    )


# --- Revisión humana -------------------------------------------------------------------------


def pending_decision(ticket):
    return ticket.ai_decisions.filter(requires_human=True, accepted__isnull=True).first()


def can_review(user, ticket):
    return has_role(user, Role.AGENTE, Role.SUPERVISOR) and (
        queries.visible_tickets(user).filter(pk=ticket.pk).exists()
    )


def review_options(ticket, user):
    """Contexto para la UI de revisión (CONTRACT-015)."""
    decision = pending_decision(ticket)
    if decision is None or not can_review(user, ticket):
        return None
    return {
        "decision_id": decision.pk,
        "intent_code": decision.intent_code,
        "candidates": decision.parsed_output.get("candidates", [])
        if decision.parsed_output
        else [],
        "confidence": decision.confidence,
        "can_correct": ticket.status == Ticket.Status.NEW,
        "intents": list(
            Intent.objects.filter(is_active=True).order_by("code").values_list("code", "name")
        ),
    }


def resume_agent(ticket, *, actor, action, intent_code=None):
    """Aplica la decisión humana y reanuda el hilo pausado (`Command(resume=…)`)."""
    if action not in REVIEW_ACTIONS:
        raise ValidationError("Acción de revisión inválida.")
    if not can_review(actor, ticket):
        raise PermissionDenied
    with transaction.atomic():
        decision = (
            AIDecision.objects.select_for_update()
            .filter(ticket=ticket, requires_human=True, accepted__isnull=True)
            .first()
        )
        if decision is None:
            raise ValidationError("No hay una revisión pendiente para este ticket.")
        locked = Ticket.objects.select_for_update(of=("self",)).get(pk=ticket.pk)
        if action == "correct":
            _correct(locked, actor, intent_code)
        decision.accepted = action != "reject"
        decision.corrected = action == "correct"
        decision.corrected_by = actor
        decision.reviewed_at = timezone.now()
        if action == "correct":
            decision.parsed_output = {**(decision.parsed_output or {}), "corrected_to": intent_code}
        alerts.resolve_alerts(locked, [Alert.Type.HUMAN_REVIEW])

    graph = get_graph()
    config = _config(decision.thread_id)
    if "human_review" in (graph.get_state(config).next or ()):
        state = graph.invoke(
            Command(resume={"action": action, "intent": intent_code, "by": actor.pk}), config
        )
        decision.node_path = list(state.get("node_path") or decision.node_path)
    else:  # checkpoint perdido (p. ej. memoria tras reinicio): la decisión igual queda aplicada
        decision.errors = [*decision.errors, "Hilo no disponible para reanudar."]
    decision.save()
    return decision


def _correct(ticket, actor, intent_code):
    intent = Intent.objects.filter(code=intent_code, is_active=True).first()
    if intent is None:
        raise ValidationError("Intención inválida.")
    if ticket.status != Ticket.Status.NEW:
        raise ValidationError("Solo se puede reclasificar un ticket nuevo.")
    previous = audit.snapshot(ticket, Ticket.audit_fields)
    ticket.intent = intent
    ticket.category, ticket.subcategory = category_for(intent.code)
    ticket.assigned_area = ticket.category.default_area if ticket.category else None
    AutomationService.route_ticket(ticket)
    sla.apply_due_dates(ticket)  # la prioridad puede cambiar con el nuevo routing
    ticket.classification_source = Ticket.ClassificationSource.HUMAN
    ticket.classification_score = None
    ticket.version += 1
    ticket.save()
    audit.record(
        audit.Action.UPDATE,
        ticket,
        actor=actor,
        previous=previous,
        new=audit.snapshot(ticket, Ticket.audit_fields),
        metadata={"reason": "Revisión humana de la clasificación (BE-T18A)"},
    )
