"""Decisiones propias del agente a partir de sus métricas (ADR-077).

Ciclo: `evaluate()` mide por intención (revisiones humanas, correcciones, SLA) y decide
con reglas explicables; cada decisión guarda su evidencia. Modo mixto:

| Decisión | Aplicación |
|---|---|
| D1 TRUST_UP: deja de pedir revisión humana (con muestreo de control) | Propuesta |
| D2 TRUST_DOWN: vuelve a pedir revisión siempre | Automática |
| D3 KEYWORDS: aprende palabras clave de las correcciones humanas | Propuesta |
| D4 LLM_PAUSE / LLM_RESUME: interruptor del LLM (`apps.ai.circuit`) | Automática |
| D5 PRIORITY_UP: sube la prioridad de una intención que incumple el SLA | Propuesta |

Límites: nunca quita la revisión a una intención N4, nunca sube la prioridad por encima
de Alta, nunca toca datos institucionales; toda decisión aplicada se puede revertir.
"""

import random
from collections import Counter, defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.automation.intents import normalize, parse_keywords
from apps.automation.models import AutomationLevel, Intent, IntentPolicy
from apps.automation.services import AutomationService
from apps.helpdesk import audit
from apps.helpdesk.models import AuditLog, Ticket

from .models import AgentPolicyDecision, AIDecision, Operation

K = AgentPolicyDecision.Kind
S = AgentPolicyDecision.Status
MODE = IntentPolicy.ReviewMode
PRIORITY_ORDER = [p for p in Ticket.Priority.values]  # LOW < MEDIUM < HIGH < CRITICAL
MAX_PRIORITY = Ticket.Priority.HIGH  # el agente nunca marca tickets como críticos
AUTO_KINDS = {K.TRUST_DOWN, K.LLM_PAUSE, K.LLM_RESUME}
STOPWORDS = set(
    "para pero como cuando donde esta este esto estos estas tengo tiene tienen quiero "
    "necesito puedo puede sobre desde hasta porque favor buenas buenos dias tardes noches "
    "hola gracias usted ustedes nuestro nuestra mucho muchas muchos todo todos algo nada "
    "solo tambien otra otro estoy estan hacer hecho saber mismo misma".split()
)


def conf(key):
    return settings.AGENT_POLICY[key]


def policy_for(intent):
    if intent is None:
        return None
    return IntentPolicy.objects.filter(intent=intent).first()


# --- Efecto en el agente --------------------------------------------------------------------


def review_decision(intent, level, default_needs_review):
    """(needs_review, detalle) según la política de la intención (nodo `decide_autonomy`)."""
    policy = policy_for(intent)
    if policy is None or level not in (AutomationLevel.N2, AutomationLevel.N3):
        return default_needs_review, None
    if policy.review_mode == MODE.ALWAYS:
        return True, {"review_mode": MODE.ALWAYS}
    if policy.review_mode == MODE.SKIP:
        sampled = random.random() < conf("review_sample_rate")
        return sampled, {"review_mode": MODE.SKIP, "sampled": sampled}
    return default_needs_review, None


def apply_priority(ticket):
    """D5: prioridad mínima de la intención (lo llama el routing al crear el ticket)."""
    policy = policy_for(ticket.intent) if ticket.intent_id else None
    if (
        policy
        and policy.priority_override
        and _rank(policy.priority_override) > _rank(ticket.priority)
    ):
        ticket.priority = policy.priority_override
        return True
    return False


def _rank(priority):
    return PRIORITY_ORDER.index(priority) if priority in PRIORITY_ORDER else 0


# --- Medición ------------------------------------------------------------------------------


def intent_metrics(now=None):
    """Métricas por intención en la ventana configurada (evidencia de D1, D2 y D5)."""
    now = now or timezone.now()
    since = now - timedelta(days=conf("window_days"))
    policies = {p.intent_id: p for p in IntentPolicy.objects.all()}
    reviewed = AIDecision.objects.filter(
        operation=Operation.AGENT_RUN, created_at__gte=since, accepted__isnull=False
    ).exclude(intent_code="")
    rows = []
    for intent in Intent.objects.filter(is_active=True).order_by("automation_level", "code"):
        policy = policies.get(intent.pk)
        # Las revisiones cuentan desde el último cambio de política: miden el régimen vigente.
        start = max(since, policy.updated_at) if policy else since
        mine = [d for d in reviewed if d.intent_code == intent.code and d.created_at >= start]
        accepted = sum(1 for d in mine if d.accepted and not d.corrected)
        corrected = sum(1 for d in mine if d.corrected)
        rejected = sum(1 for d in mine if d.accepted is False)
        sla = _sla_stats(intent, since, now)
        rows.append(
            {
                "intent": intent,
                "code": intent.code,
                "level": intent.automation_level,
                "review_mode": policy.review_mode if policy else MODE.DEFAULT,
                "priority_override": policy.priority_override if policy else "",
                "reviewed": len(mine),
                "accepted": accepted,
                "corrected": corrected,
                "rejected": rejected,
                "accept_rate": _rate(accepted, len(mine)),
                "error_rate": _rate(corrected + rejected, len(mine)),
                **sla,
            }
        )
    return rows


def _rate(part, total):
    return round(part / total, 3) if total else None


def _sla_stats(intent, since, now):
    tickets = Ticket.objects.filter(
        intent=intent, created_at__gte=since, sla_due_at__isnull=False
    ).values_list("sla_due_at", "resolved_at")
    decided = breached = 0
    for due, resolved in tickets:
        if resolved is not None:
            decided += 1
            breached += resolved > due
        elif now > due:
            decided += 1
            breached += 1
    return {
        "sla_decided": decided,
        "sla_breached": breached,
        "breach_rate": _rate(breached, decided),
    }


# --- Decisión -----------------------------------------------------------------------------


def evaluate(now=None, *, dry_run=False):
    """Evalúa las métricas y registra las decisiones nuevas (o solo las calcula con
    `dry_run`). Devuelve las decisiones creadas, o las propuestas si es `dry_run`."""
    from . import circuit

    proposals = [
        proposal
        for row in intent_metrics(now)
        for build in (_trust_up, _trust_down, _priority_up)
        if (proposal := build(row)) is not None
    ]
    proposals += _keywords(now)
    if (pause := circuit.check(now)) is not None:
        proposals.append(pause)
    if dry_run:
        return proposals
    return [record(**proposal) for proposal in proposals]


def _pending(kind, intent):
    return AgentPolicyDecision.objects.filter(kind=kind, intent=intent, status=S.PROPOSED).exists()


def _trust_up(row):
    intent = row["intent"]
    if intent.automation_level not in (AutomationLevel.N2, AutomationLevel.N3):
        return None  # límite: N0/N1 no tienen revisión y N4 siempre la conserva
    if row["review_mode"] == MODE.SKIP or _pending(K.TRUST_UP, intent):
        return None
    if row["reviewed"] < conf("trust_up_min_reviews") or row["accept_rate"] < conf("trust_up_rate"):
        return None
    return _proposal(
        K.TRUST_UP,
        intent,
        f"{intent.code}: {row['accepted']}/{row['reviewed']} clasificaciones aceptadas "
        f"({row['accept_rate']:.0%}); dejar de pedir revisión humana (muestreo "
        f"{conf('review_sample_rate'):.0%}).",
        _evidence(row, "reviewed", "accepted", "corrected", "rejected", "accept_rate"),
        {"review_mode": MODE.SKIP, "previous": row["review_mode"]},
    )


def _trust_down(row):
    intent = row["intent"]
    if intent.automation_level not in (AutomationLevel.N2, AutomationLevel.N3):
        return None  # N4 ya se revisa siempre; N0/N1 no crean tickets que revisar
    if row["review_mode"] == MODE.ALWAYS:
        return None
    if row["reviewed"] < conf("trust_down_min_reviews") or row["error_rate"] < conf(
        "trust_down_rate"
    ):
        return None
    return _proposal(
        K.TRUST_DOWN,
        intent,
        f"{intent.code}: {row['corrected'] + row['rejected']}/{row['reviewed']} "
        f"clasificaciones corregidas o rechazadas ({row['error_rate']:.0%}); revisar siempre.",
        _evidence(row, "reviewed", "accepted", "corrected", "rejected", "error_rate"),
        {"review_mode": MODE.ALWAYS, "previous": row["review_mode"]},
    )


def _priority_up(row):
    intent = row["intent"]
    if _pending(K.PRIORITY_UP, intent):
        return None
    if row["sla_decided"] < conf("sla_min_tickets") or row["breach_rate"] < conf("sla_breach_rate"):
        return None
    current = row["priority_override"] or _routing_priority(intent)
    if _rank(current) >= _rank(MAX_PRIORITY):
        return None
    target = PRIORITY_ORDER[_rank(current) + 1]
    labels = dict(Ticket.Priority.choices)
    return _proposal(
        K.PRIORITY_UP,
        intent,
        f"{intent.code}: {row['sla_breached']}/{row['sla_decided']} tickets incumplieron el "
        f"SLA ({row['breach_rate']:.0%}); subir la prioridad de {labels[current]} a "
        f"{labels[target]}.",
        _evidence(row, "sla_decided", "sla_breached", "breach_rate"),
        {"priority": target, "previous": row["priority_override"], "from": current},
    )


def _routing_priority(intent):
    rule = AutomationService.matching_rule(intent_id=intent.pk)
    return (rule.priority if rule and rule.priority else None) or Ticket.Priority.MEDIUM


def _keywords(now=None):
    """D3: palabras que se repiten en mensajes que las personas corrigieron a una intención."""
    now = now or timezone.now()
    since = now - timedelta(days=conf("window_days"))
    corrected = AIDecision.objects.filter(
        operation=Operation.AGENT_RUN, corrected=True, created_at__gte=since, ticket__isnull=False
    ).select_related("ticket")
    by_intent = defaultdict(list)
    for decision in corrected:
        target = (decision.parsed_output or {}).get("corrected_to")
        if target:
            by_intent[target].append(decision.ticket.description)
    intents = {i.code: i for i in Intent.objects.filter(is_active=True)}
    known = {code: _keyword_words(i.keywords) for code, i in intents.items()}
    already = defaultdict(set)  # palabras ya propuestas, aplicadas o rechazadas
    for d in AgentPolicyDecision.objects.filter(kind=K.KEYWORDS).select_related("intent"):
        already[d.intent.code].update(d.change.get("add", []))
    proposals = []
    for code, messages in sorted(by_intent.items()):
        intent = intents.get(code)
        if intent is None:
            continue
        others = set().union(*(w for c, w in known.items() if c != code))
        counts = Counter(
            word for text in messages for word in set(normalize(text).split()) if _useful(word)
        )
        words = [
            w
            for w, n in counts.most_common()
            if n >= conf("keyword_min_messages")
            and w not in known[code]
            and w not in others
            and w not in already[code]
        ][: conf("keyword_max")]
        if not words:
            continue
        proposals.append(
            _proposal(
                K.KEYWORDS,
                intent,
                f"{code}: aprender {', '.join(words)} (repetidas en mensajes que las personas "
                f"corrigieron a esta intención).",
                {"corrected_messages": len(messages), "counts": {w: counts[w] for w in words}},
                {"add": words},
            )
        )
    return proposals


def _keyword_words(raw):
    return {word for parts in parse_keywords(raw) for part in parts for word in part.split()}


def _useful(word):
    return len(word) >= 4 and not word.isdigit() and word not in STOPWORDS


def _evidence(row, *keys):
    return {key: row[key] for key in keys} | {"window_days": conf("window_days")}


def _proposal(kind, intent, summary, evidence, change):
    return {
        "kind": kind,
        "intent": intent,
        "summary": summary,
        "evidence": evidence,
        "change": change,
    }


# --- Registro, aprobación y reversión -------------------------------------------------------


@transaction.atomic
def record(*, kind, intent, summary, evidence, change):
    """Registra una decisión: las seguras se aplican en el acto; las demás quedan propuestas."""
    decision = AgentPolicyDecision.objects.create(
        kind=kind,
        intent=intent,
        status=S.PROPOSED,
        auto=kind in AUTO_KINDS,
        summary=summary[:255],
        evidence=evidence,
        change=change,
    )
    _audit("POLICY_PROPOSE", decision, None)
    if decision.auto:
        _apply(decision, actor=None)
    return decision


@transaction.atomic
def approve(decision, actor, note=""):
    decision = _locked(decision)
    if decision.status != S.PROPOSED:
        raise ValidationError("Solo se puede aprobar una decisión propuesta.")
    _apply(decision, actor=actor, note=note)
    return decision


@transaction.atomic
def reject(decision, actor, note=""):
    decision = _locked(decision)
    if decision.status != S.PROPOSED:
        raise ValidationError("Solo se puede rechazar una decisión propuesta.")
    _close(decision, S.REJECTED, actor, note)
    _audit("POLICY_REJECT", decision, actor)
    return decision


@transaction.atomic
def revert(decision, actor, note=""):
    from . import circuit

    decision = _locked(decision)
    if decision.status != S.APPLIED:
        raise ValidationError("Solo se puede revertir una decisión aplicada.")
    change = decision.change
    if decision.kind in (K.TRUST_UP, K.TRUST_DOWN):
        policy = _policy(decision.intent)
        if policy.review_mode != change["review_mode"]:
            raise ValidationError("Otra decisión posterior ya cambió esta política.")
        policy.review_mode = change["previous"]
        policy.save()
    elif decision.kind == K.PRIORITY_UP:
        policy = _policy(decision.intent)
        if policy.priority_override != change["priority"]:
            raise ValidationError("Otra decisión posterior ya cambió esta política.")
        policy.priority_override = change["previous"]
        policy.save()
    elif decision.kind == K.KEYWORDS:
        _set_keywords(decision.intent, remove=change["add"], actor=actor)
    elif decision.kind == K.LLM_PAUSE:
        circuit.resume()
    else:  # LLM_RESUME: revertir = volver a pausar
        circuit.pause()
    _close(decision, S.REVERTED, actor, note)
    _audit("POLICY_REVERT", decision, actor)
    return decision


def _apply(decision, *, actor, note=""):
    from . import circuit

    change = decision.change
    if decision.kind in (K.TRUST_UP, K.TRUST_DOWN):
        policy = _policy(decision.intent)
        policy.review_mode = change["review_mode"]
        policy.save()
    elif decision.kind == K.PRIORITY_UP:
        policy = _policy(decision.intent)
        policy.priority_override = change["priority"]
        policy.save()
    elif decision.kind == K.KEYWORDS:
        _set_keywords(decision.intent, add=change["add"], actor=actor)
    elif decision.kind == K.LLM_PAUSE:
        circuit.pause()
    elif decision.kind == K.LLM_RESUME:
        circuit.resume()
    _close(decision, S.APPLIED, actor, note)
    _audit("POLICY_APPLY", decision, actor)


def _set_keywords(intent, *, add=(), remove=(), actor=None):
    intent = Intent.objects.select_for_update().get(pk=intent.pk)
    previous = audit.snapshot(intent, Intent.audit_fields)
    lines = [line for line in intent.keywords.splitlines() if line.strip()]
    lines = [line for line in lines if normalize(line) not in set(remove)]
    lines += [word for word in add if word not in {normalize(x) for x in lines}]
    intent.keywords = "\n".join(lines)
    intent.save(update_fields=["keywords"])
    audit.record(
        audit.Action.UPDATE,
        intent,
        actor=actor,
        actor_type=None if actor else AuditLog.ActorType.AI,
        previous=previous,
        new=audit.snapshot(intent, Intent.audit_fields),
        metadata={"reason": "Decisión del agente D3 (ADR-077)"},
    )


def _policy(intent):
    policy, _ = IntentPolicy.objects.select_for_update().get_or_create(intent=intent)
    return policy


def _locked(decision):
    return AgentPolicyDecision.objects.select_for_update().get(pk=decision.pk)


def _close(decision, status, actor, note):
    decision.status = status
    decision.decided_by = actor
    decision.decided_at = timezone.now()
    decision.note = (note or "")[:255]
    decision.save()


def _audit(action, decision, actor):
    audit.record(
        action,
        decision,
        actor=actor,
        actor_type=None if actor else AuditLog.ActorType.AI,
        new={"kind": decision.kind, "status": decision.status, "change": decision.change},
        metadata={"summary": decision.summary},
    )


def summary():
    """Resumen para la pantalla de decisiones."""
    qs = AgentPolicyDecision.objects.all()
    return {
        "proposed": qs.filter(status=S.PROPOSED).count(),
        "applied": qs.filter(status=S.APPLIED).count(),
        "rejected": qs.filter(status=S.REJECTED).count(),
        "reverted": qs.filter(status=S.REVERTED).count(),
        "active_policies": IntentPolicy.objects.filter(
            ~Q(review_mode=MODE.DEFAULT) | ~Q(priority_override="")
        ).count(),
    }
