"""Textos de respuesta del Autonomy Engine (BE-T14).

Formatean resultados del proveedor de forma determinística, sin LLM. Por
WhatsApp los datos sensibles se minimizan (SPEC §35.1: deuda total, sin detalle).
"""

from datetime import timedelta

from django.utils import timezone

from apps.helpdesk.models import Ticket

DAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
OPEN_STATUSES = [s for s in Ticket.Status.values if s not in ("RESOLVED", "CLOSED", "CANCELLED")]

LINK_INSTRUCTIONS = (
    "Para consultar datos personales necesitamos confirmar tu identidad. Inicia sesión en "
    "el portal o vincula tu WhatsApp desde Perfil → WhatsApp y vuelve a escribirnos."
)
LOGIN_FOR_TICKET = (
    "Para registrar tu solicitud necesitamos identificarte. Inicia sesión en el portal o "
    "vincula tu WhatsApp desde Perfil → WhatsApp."
)


TELEGRAM_LINK_INSTRUCTIONS = (
    "Para consultar datos personales necesitamos confirmar tu identidad. Genera un código en el "
    "portal (Perfil → Telegram) y envíamelo aquí."
)
TELEGRAM_LOGIN_FOR_TICKET = (
    "Para registrar tu solicitud necesitamos identificarte. Genera un código en el portal "
    "(Perfil → Telegram) y envíamelo aquí, o inicia sesión en el portal."
)


def link_instructions(channel, *, for_ticket=False):
    """Cómo identificarse, según el canal por el que escribe el usuario."""
    if channel == Ticket.Channel.TELEGRAM:
        return TELEGRAM_LOGIN_FOR_TICKET if for_ticket else TELEGRAM_LINK_INSTRUCTIONS
    return LOGIN_FOR_TICKET if for_ticket else LINK_INSTRUCTIONS


def _date(d):
    return f"{DAY_NAMES[d.weekday()]} {d:%d/%m/%Y}"


def _money(value):
    return f"{value:,.2f}"


def _relative_day(day):
    today = timezone.localdate()
    if day == today:
        return "de hoy"
    if day == today + timedelta(days=1):
        return "de mañana"
    return "del"


def schedule(entries, channel=None, day=None):
    day = entries[0].day if entries else (day or timezone.localdate())
    label = _relative_day(day)
    if not entries:
        if label == "de hoy":
            return "Hoy no tienes clases registradas."
        return f"No tienes clases registradas el {_date(day)}."
    lines = [f"Tu horario {label} ({_date(day)}):"]
    lines += [f"• {e.start:%H:%M}–{e.end:%H:%M} {e.subject} ({e.room})" for e in entries]
    return "\n".join(lines)


def grades(items, channel=None):
    if not items:
        return "No hay notas registradas para el periodo consultado."
    lines = [f"Tus notas del periodo {items[0].period}:"]
    lines += [f"• {g.subject}: {g.value} ({g.status})" for g in items]
    return "\n".join(lines)


def debt(summary, channel=None):
    if not summary.items:
        return "No tienes valores pendientes de pago."
    head = f"Tu saldo pendiente es {summary.currency} {_money(summary.total)}."
    if channel in (Ticket.Channel.WHATSAPP, Ticket.Channel.TELEGRAM):  # mensajería: minimizar
        return f"{head} Puedes ver el detalle en el portal."
    lines = [head]
    lines += [
        f"• {i.concept}: {_money(i.amount)} (vence el {_date(i.due_date)})" for i in summary.items
    ]
    return "\n".join(lines)


def enrollment(e, channel=None):
    return f"Periodo {e.period} · {e.program}: {e.status}."


def subjects(items, channel=None):
    if not items:
        return "No tienes asignaturas registradas en el periodo consultado."
    total = sum(s.credits for s in items)
    lines = [f"Tus asignaturas ({total} créditos):"]
    lines += [f"• {s.code} {s.name} ({s.credits} créditos)" for s in items]
    return "\n".join(lines)


FORMATTERS = {
    "get_schedule": schedule,
    "get_grades": grades,
    "get_debt": debt,
    "get_enrollment": enrollment,
    "get_subjects": subjects,
}


def format_query(method, data, channel=None, **extra):
    return FORMATTERS[method](data, channel=channel, **extra)


def _ticket_line(t):
    area = f", área {t.assigned_area.name}" if t.assigned_area_id else ""
    return f"• {t.ticket_code} «{t.subject}»: {t.get_status_display()}{area}"


def ticket_status(user, code=None):
    """CHECK_TICKET (CA-009): solo tickets del propio usuario (autorización horizontal)."""
    mine = Ticket.objects.filter(user=user).select_related("assigned_area")
    if code:
        ticket = mine.filter(ticket_code=code).first()
        if ticket is None:
            return f"No encontramos el ticket {code} entre tus solicitudes."
        return f"Estado de tu solicitud:\n{_ticket_line(ticket)}"
    open_tickets = list(mine.filter(status__in=OPEN_STATUSES).order_by("-created_at")[:3])
    if not open_tickets:
        return "No tienes solicitudes abiertas."
    lines = ["Tus solicitudes abiertas más recientes:"] + [_ticket_line(t) for t in open_tickets]
    return "\n".join(lines)


def ticket_created(ticket, level, provider_failed=False):
    code = ticket.ticket_code
    area = ticket.assigned_area.name if ticket.assigned_area_id else "Atención General"
    if provider_failed:
        return (
            f"No pudimos consultar la información en este momento. Registramos tu solicitud "
            f"{code} y el área {area} te responderá."
        )
    if level == "N2":
        return (
            f"Registramos tu solicitud {code}. El área {area} validará la información y te "
            f"responderá por este medio."
        )
    if level == "N3":
        return f"Registramos tu solicitud {code} y la derivamos al área {area}."
    return f"Registramos tu solicitud {code}. Un agente la revisará para orientarte."
