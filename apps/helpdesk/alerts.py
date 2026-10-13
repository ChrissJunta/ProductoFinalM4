"""Alertas operativas (SPEC §26 `Alert`, FE-007).

Invariante: como máximo una alerta abierta por tipo y ticket (restricción en BD).
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Alert


def open_alert(ticket, alert_type, *, severity, message):
    """Abre la alerta si no hay una abierta del mismo tipo. Devuelve (alerta, creada)."""
    existing = Alert.objects.filter(
        ticket=ticket, alert_type=alert_type, status=Alert.Status.OPEN
    ).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            return (
                Alert.objects.create(
                    ticket=ticket, alert_type=alert_type, severity=severity, message=message
                ),
                True,
            )
    except IntegrityError:
        # Otro proceso la abrió entre la consulta y la inserción.
        return Alert.objects.get(
            ticket=ticket, alert_type=alert_type, status=Alert.Status.OPEN
        ), False


def resolve_alerts(ticket, alert_types=None):
    """Marca como resueltas las alertas abiertas del ticket (todas o de los tipos dados)."""
    qs = Alert.objects.filter(ticket=ticket, status=Alert.Status.OPEN)
    if alert_types is not None:
        qs = qs.filter(alert_type__in=alert_types)
    return qs.update(status=Alert.Status.RESOLVED, resolved_at=timezone.now())
