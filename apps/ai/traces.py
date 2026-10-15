"""Consulta de trazas del agente para Supervisor y Administrador (ADR-076, CONTRACT-020)."""

from datetime import datetime, time, timedelta

from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.automation.models import AutomationLevel
from apps.helpdesk.models import Ticket

from .agent.trace import describe
from .models import AIDecision, Operation

STATUS_CHOICES = [
    ("", "Todas"),
    ("pending", "Revisión pendiente"),
    ("errors", "Con errores"),
    ("llm", "Usó el LLM"),
    ("ticket", "Crearon ticket"),
]
SOURCE_CHOICES = [("", "Todos"), ("RULES", "Reglas"), ("LLM", "LLM"), ("HUMAN", "Humano")]


class TraceFilterForm(forms.Form):
    q = forms.CharField(
        label="Buscar", required=False, max_length=100,
        help_text="Hilo, código de ticket, intención o usuario.",
    )  # fmt: skip
    level = forms.ChoiceField(
        label="Nivel", required=False, choices=[("", "Todos"), *AutomationLevel.choices]
    )
    channel = forms.ChoiceField(
        label="Canal", required=False, choices=[("", "Todos"), *Ticket.Channel.choices]
    )
    source = forms.ChoiceField(label="Origen", required=False, choices=SOURCE_CHOICES)
    status = forms.ChoiceField(label="Estado", required=False, choices=STATUS_CHOICES)
    date_from = forms.DateField(
        label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    date_to = forms.DateField(
        label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )


def runs():
    return AIDecision.objects.filter(operation=Operation.AGENT_RUN).select_related("ticket", "user")


def filter_runs(data):
    qs = runs()
    if q := (data.get("q") or "").strip():
        qs = qs.filter(
            Q(thread_id__icontains=q)
            | Q(ticket__ticket_code__icontains=q)
            | Q(intent_code__icontains=q)
            | Q(user__username__icontains=q)
        )
    for field, column in (
        ("level", "autonomy_level"),
        ("channel", "channel"),
        ("source", "classification_source"),
    ):
        if data.get(field):
            qs = qs.filter(**{column: data[field]})
    status = data.get("status")
    if status == "pending":
        qs = qs.filter(requires_human=True, accepted__isnull=True)
    elif status == "errors":
        qs = qs.exclude(errors=[])
    elif status == "llm":
        qs = qs.filter(node_path__contains=["classify_llm"])
    elif status == "ticket":
        qs = qs.filter(ticket__isnull=False)
    tz = timezone.get_current_timezone()
    if data.get("date_from"):
        qs = qs.filter(
            created_at__gte=timezone.make_aware(datetime.combine(data["date_from"], time.min), tz)
        )
    if data.get("date_to"):
        end = datetime.combine(data["date_to"] + timedelta(days=1), time.min)
        qs = qs.filter(created_at__lt=timezone.make_aware(end, tz))
    return qs


def _llm_calls(trace):
    return [call for step in trace for call in step.get("llm_calls", [])]


def row(decision):
    """Fila del listado."""
    calls = _llm_calls(decision.trace)
    return {
        "id": decision.pk,
        "created_at": decision.created_at,
        "user": decision.user,
        "channel": decision.channel,
        "intent_code": decision.intent_code,
        "autonomy_level": decision.autonomy_level,
        "classification_source": decision.classification_source,
        "confidence": decision.confidence,
        "duration_ms": decision.duration_ms,
        "steps": len(decision.node_path or []),
        "used_llm": "classify_llm" in (decision.node_path or []),
        "llm_calls": len(calls),
        "has_errors": bool(decision.errors),
        "pending_review": decision.pending_review,
        "ticket_code": decision.ticket.ticket_code if decision.ticket_id else None,
        "message": next(
            (s["data"].get("message") for s in decision.trace if s.get("data", {}).get("message")),
            "",
        ),
    }


def detail(decision):
    """Contexto del detalle (CONTRACT-020)."""
    steps = describe(decision.trace or [])
    calls = _llm_calls(decision.trace or [])
    return {
        "decision": decision,
        "run": row(decision),
        "steps": steps,
        "llm_calls": calls,
        "llm_ms": sum(c.get("latency_ms") or 0 for c in calls),
        "llm_failures": sum(1 for c in calls if not c.get("success")),
        "nodes_ms": round(sum(s.get("ms") or 0 for s in steps), 1),
        "has_trace": bool(steps),
        "review": {
            "pending": decision.pending_review,
            "accepted": decision.accepted,
            "corrected": decision.corrected,
            "corrected_by": decision.corrected_by,
            "reviewed_at": decision.reviewed_at,
            "corrected_to": (decision.parsed_output or {}).get("corrected_to"),
        },
    }


def export(decision):
    """JSON descargable de una ejecución (sin la respuesta al usuario)."""
    return {
        "id": decision.pk,
        "thread_id": decision.thread_id,
        "created_at": decision.created_at.isoformat(),
        "graph_version": decision.graph_version,
        "channel": decision.channel,
        "user": decision.user.username if decision.user_id else None,
        "ticket": decision.ticket.ticket_code if decision.ticket_id else None,
        "intent": decision.intent_code,
        "autonomy_level": decision.autonomy_level,
        "classification_source": decision.classification_source,
        "confidence": float(decision.confidence) if decision.confidence is not None else None,
        "duration_ms": decision.duration_ms,
        "node_path": decision.node_path,
        "errors": decision.errors,
        "llm_raw_output": decision.raw_output,
        "parsed_output": decision.parsed_output,
        "review": {
            "pending": decision.pending_review,
            "accepted": decision.accepted,
            "corrected": decision.corrected,
            "reviewed_at": decision.reviewed_at.isoformat() if decision.reviewed_at else None,
        },
        "trace": decision.trace,
    }
