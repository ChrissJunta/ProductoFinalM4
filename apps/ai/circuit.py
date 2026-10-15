"""Interruptor del LLM (D4, ADR-077).

Si en la última hora fallan más de la mitad de las llamadas al LLM (con un mínimo de
llamadas), el agente lo pone en pausa: deja de llamarlo y los mensajes que lo necesitarían
van a revisión humana sin esperar timeouts. Pasado `llm_pause_minutes` deja pasar una
llamada de prueba: si responde, lo reactiva solo; si falla, extiende la pausa.
Cada pausa y reactivación queda como decisión automática con su evidencia.
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AgentPolicyDecision, AIUsage, LLMCircuit

K = AgentPolicyDecision.Kind


def conf(key):
    return settings.AGENT_POLICY[key]


def state():
    circuit, _ = LLMCircuit.objects.get_or_create(pk=1)
    return circuit


def allow(now=None):
    """¿Se puede llamar al LLM? En pausa solo pasa la llamada de prueba tras `retry_at`."""
    circuit = LLMCircuit.objects.filter(pk=1).first()
    if circuit is None or circuit.state == LLMCircuit.State.CLOSED:
        return True
    return (now or timezone.now()) >= circuit.retry_at


def failure_stats(now=None):
    since = (now or timezone.now()) - timedelta(minutes=conf("llm_window_minutes"))
    usage = AIUsage.objects.filter(created_at__gte=since)
    total = usage.count()
    failed = usage.filter(success=False).count()
    return {
        "calls": total,
        "failed": failed,
        "failure_rate": round(failed / total, 3) if total else None,
        "window_minutes": conf("llm_window_minutes"),
    }


def check(now=None):
    """Propuesta de pausa si el LLM está activo y falla por encima del umbral."""
    if state().state == LLMCircuit.State.OPEN:
        return None
    stats = failure_stats(now)
    if stats["calls"] < conf("llm_min_calls") or stats["failure_rate"] <= conf("llm_failure_rate"):
        return None
    return {
        "kind": K.LLM_PAUSE,
        "intent": None,
        "summary": (
            f"LLM: {stats['failed']}/{stats['calls']} llamadas fallidas en "
            f"{stats['window_minutes']} min ({stats['failure_rate']:.0%}); pausar "
            f"{conf('llm_pause_minutes')} min y derivar a revisión humana."
        ),
        "evidence": stats,
        "change": {"pause_minutes": conf("llm_pause_minutes")},
    }


def after_call(success, now=None):
    """Lo llama `AIService` al terminar cada operación (con o sin éxito)."""
    from . import policies

    circuit = state()
    if circuit.state == LLMCircuit.State.OPEN:
        if success:  # la llamada de prueba respondió
            policies.record(
                kind=K.LLM_RESUME,
                intent=None,
                summary="LLM: la llamada de prueba respondió; reactivar.",
                evidence=failure_stats(now),
                change={},
            )
        else:
            pause(now)  # sigue fallando: se extiende la pausa
        return
    if not success and (proposal := check(now)) is not None:
        policies.record(**proposal)


@transaction.atomic
def pause(now=None):
    circuit = LLMCircuit.objects.select_for_update().get_or_create(pk=1)[0]
    circuit.state = LLMCircuit.State.OPEN
    circuit.retry_at = (now or timezone.now()) + timedelta(minutes=conf("llm_pause_minutes"))
    circuit.save()


@transaction.atomic
def resume():
    circuit = LLMCircuit.objects.select_for_update().get_or_create(pk=1)[0]
    circuit.state = LLMCircuit.State.CLOSED
    circuit.retry_at = None
    circuit.save()
