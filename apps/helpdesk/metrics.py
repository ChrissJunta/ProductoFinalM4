"""Métricas operativas (BE-T10, SPEC §49, FE-009). Definiciones en CONTRACT-017.

- Universo: tickets **creados** en el periodo (fechas locales `TIME_ZONE`, ambos
  extremos incluidos) que cumplan los filtros de área, categoría y canal.
- Tiempos en minutos de reloj (no laborables) desde `created_at`.
- SLA: un ticket «cumple» si se resolvió antes o en su vencimiento; «incumple»
  si se resolvió después o sigue sin resolver con el plazo vencido; «en curso»
  si no se resolvió y aún no vence; «sin SLA» si no tiene plazo. El cumplimiento
  es cumple / (cumple + incumple); `None` si no hay casos decididos.
"""

import statistics
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from .models import AuditLog, Ticket, TicketStatusHistory

S = Ticket.Status
OPEN = [s for s in S.values if s not in (S.RESOLVED, S.CLOSED, S.CANCELLED)]
DEFAULT_DAYS = 30


def default_period(today=None):
    today = today or timezone.localdate()
    return today - timedelta(days=DEFAULT_DAYS - 1), today


def _bounds(date_from, date_to):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min), tz)
    return start, end


def ticket_queryset(date_from, date_to, *, area=None, category=None, channel=None):
    start, end = _bounds(date_from, date_to)
    qs = Ticket.objects.filter(created_at__gte=start, created_at__lt=end)
    if area is not None:
        qs = qs.filter(assigned_area=area)
    if category is not None:
        qs = qs.filter(category=category)
    if channel:
        qs = qs.filter(channel=channel)
    return qs


def _minutes(delta):
    return delta.total_seconds() / 60


def _stats(values):
    if not values:
        return {"count": 0, "avg": None, "median": None, "p90": None}
    ordered = sorted(values)
    p90 = ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]
    return {
        "count": len(values),
        "avg": round(statistics.fmean(values), 1),
        "median": round(statistics.median(values), 1),
        "p90": round(p90, 1),
    }


def _sla(rows, due_field, done_field, now):
    out = {"within": 0, "breached": 0, "pending": 0, "no_sla": 0}
    for row in rows:
        due, done = row[due_field], row[done_field]
        if due is None:
            out["no_sla"] += 1
        elif done is not None:
            out["within" if done <= due else "breached"] += 1
        elif now > due:
            out["breached"] += 1
        else:
            out["pending"] += 1
    decided = out["within"] + out["breached"]
    out["compliance_pct"] = round(100 * out["within"] / decided, 1) if decided else None
    return out


def _summary(rows, now):
    total = len(rows)
    by_status = {s: 0 for s in S.values}
    for r in rows:
        by_status[r["status"]] += 1
    return {
        "total": total,
        "open": sum(by_status[s] for s in OPEN),
        "resolved": by_status[S.RESOLVED],
        "closed": by_status[S.CLOSED],
        "cancelled": by_status[S.CANCELLED],
        "sla_resolution": _sla(rows, "sla_due_at", "resolved_at", now),
    }


def _breakdown(rows, key, label, empty_label, now):
    groups = {}
    for r in rows:
        groups.setdefault((r[key], r[label] or empty_label), []).append(r)
    result = [{"id": k, "label": lbl, **_summary(items, now)} for (k, lbl), items in groups.items()]
    return sorted(result, key=lambda g: (-g["total"], g["label"]))


def compute(date_from, date_to, *, area=None, category=None, channel=None, now=None):
    """Diccionario de métricas para la vista (CONTRACT-017)."""
    now = now or timezone.now()
    qs = ticket_queryset(date_from, date_to, area=area, category=category, channel=channel)
    rows = list(
        qs.values(
            "pk", "status", "channel", "created_at", "first_response_at", "resolved_at",
            "first_response_due_at", "sla_due_at", "assigned_area_id", "assigned_area__name",
            "category_id", "category__name",
        )
    )  # fmt: skip
    channel_labels = dict(Ticket.Channel.choices)
    for r in rows:
        r["channel_label"] = channel_labels.get(r["channel"], r["channel"])
    ids = [r["pk"] for r in rows]
    return {
        **_summary(rows, now),
        "by_status": [
            {"status": s, "label": lbl, "count": sum(1 for r in rows if r["status"] == s)}
            for s, lbl in S.choices
        ],
        "sla_first_response": _sla(rows, "first_response_due_at", "first_response_at", now),
        "first_response_minutes": _stats(
            [
                _minutes(r["first_response_at"] - r["created_at"])
                for r in rows
                if r["first_response_at"]
            ]
        ),
        "resolution_minutes": _stats(
            [_minutes(r["resolved_at"] - r["created_at"]) for r in rows if r["resolved_at"]]
        ),
        "reassignments": AuditLog.objects.filter(
            entity_type="helpdesk.ticket", action="REASSIGN", entity_id__in=[str(i) for i in ids]
        ).count(),
        "reopenings": TicketStatusHistory.objects.filter(
            ticket_id__in=ids, new_status=S.REOPENED
        ).count(),
        "by_area": _breakdown(rows, "assigned_area_id", "assigned_area__name", "Sin área", now),
        "by_category": _breakdown(rows, "category_id", "category__name", "Sin categoría", now),
        "by_channel": _breakdown(rows, "channel", "channel_label", "—", now),
        "ai": ai_metrics(date_from, date_to, channel=channel),
        "whatsapp": whatsapp_metrics(date_from, date_to),
    }


def whatsapp_metrics(date_from, date_to):
    """SPEC §49 WhatsApp: mensajes, reintentos, fallos y conversaciones (simulado: ADR-049)."""
    from django.db.models import Sum

    from apps.integrations.models import IntegrationInbox, IntegrationOutbox

    start, end = _bounds(date_from, date_to)
    inbox = IntegrationInbox.objects.filter(received_at__gte=start, received_at__lt=end)
    outbox = IntegrationOutbox.objects.filter(created_at__gte=start, created_at__lt=end)

    def retries(qs):
        total = qs.aggregate(n=Sum("attempts"))["n"] or 0
        return max(total - qs.filter(attempts__gt=0).count(), 0)

    return {
        "inbound": inbox.count(),
        "inbound_failed": inbox.filter(status="FAILED").count(),
        "outbound_sent": outbox.filter(status="SENT").count(),
        "outbound_failed": outbox.filter(status="FAILED").count(),
        "outbound_pending": outbox.filter(status="PENDING").count(),
        "retries": retries(inbox) + retries(outbox),
        "conversations": inbox.values("payload_json__from").distinct().count(),
    }


def ai_metrics(date_from, date_to, *, channel=None):
    """SPEC §49 IA: automatización, uso del LLM, fallos, salidas inválidas y correcciones."""
    from apps.ai.models import AIDecision, AIUsage

    start, end = _bounds(date_from, date_to)
    runs = AIDecision.objects.filter(
        operation="AGENT_RUN", created_at__gte=start, created_at__lt=end
    )
    if channel:
        runs = runs.filter(channel=channel)
    levels = dict(runs.order_by().values_list("autonomy_level").annotate(n=Count("id")))
    total_runs = sum(levels.values())
    automatic = levels.get("N0", 0) + levels.get("N1", 0)
    usage = AIUsage.objects.filter(created_at__gte=start, created_at__lt=end)
    latencies = list(usage.filter(success=True).values_list("latency_ms", flat=True))
    reviewed = runs.filter(accepted__isnull=False)
    return {
        "runs": total_runs,
        "by_level": [
            {"level": lvl, "count": levels.get(lvl, 0)} for lvl in ("N0", "N1", "N2", "N3", "N4")
        ],
        "automation_pct": round(100 * automatic / total_runs, 1) if total_runs else None,
        "llm_calls": usage.count(),
        "llm_failures": usage.filter(success=False).count(),
        "invalid_outputs": runs.filter(
            Q(errors__icontains="inválida") | Q(errors__icontains="confianza baja")
        ).count(),
        "pending_reviews": runs.filter(requires_human=True, accepted__isnull=True).count(),
        "reviewed": reviewed.count(),
        "corrected": reviewed.filter(corrected=True).count(),
        "latency_ms": _stats(latencies),
        "estimated_cost": sum(usage.values_list("estimated_cost", flat=True), 0),
    }
