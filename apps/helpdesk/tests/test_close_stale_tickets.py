from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.helpdesk import workflow
from apps.helpdesk.models import Ticket, TicketStatusHistory
from apps.helpdesk.tickets import TicketService

pytestmark = pytest.mark.django_db

S = Ticket.Status


@pytest.fixture
def make_ticket(make_user):
    owner = make_user("owner", role="Usuario")

    def _make(status, days_in_status):
        """Ticket que entró a `status` hace `days_in_status` días (según el historial)."""
        t = TicketService.create(user=owner, subject="s", description="d")
        Ticket.objects.filter(pk=t.pk).update(status=status)
        entry = TicketStatusHistory.objects.create(ticket=t, previous_status="X", new_status=status)
        TicketStatusHistory.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=days_in_status)
        )
        t.refresh_from_db()
        return t

    return _make


def _run(*args):
    out = StringIO()
    call_command("close_stale_tickets", *args, stdout=out)
    return out.getvalue()


def test_closes_old_resolved_and_cancels_old_waiting(make_ticket, settings):
    resolved_old = make_ticket(S.RESOLVED, settings.AUTO_CLOSE_DAYS + 1)
    resolved_new = make_ticket(S.RESOLVED, settings.AUTO_CLOSE_DAYS - 1)
    waiting_old = make_ticket(S.WAITING_USER, settings.WAITING_USER_TIMEOUT_DAYS + 1)
    waiting_new = make_ticket(S.WAITING_USER, 1)

    output = _run()

    for t in (resolved_old, resolved_new, waiting_old, waiting_new):
        t.refresh_from_db()
    assert resolved_old.status == S.CLOSED
    assert resolved_old.closed_at is not None
    assert waiting_old.status == S.CANCELLED
    assert resolved_new.status == S.RESOLVED
    assert waiting_new.status == S.WAITING_USER
    assert "Tickets procesados: 2" in output

    entry = waiting_old.status_history.last()
    assert entry.actor is None
    assert entry.reason.startswith("Cancelación automática")


def test_uses_last_entry_into_state(make_ticket, settings):
    t = make_ticket(S.RESOLVED, settings.AUTO_CLOSE_DAYS + 5)
    # Volvió a RESOLVED hace poco: el plazo cuenta desde la última entrada.
    TicketStatusHistory.objects.create(
        ticket=t, previous_status=S.IN_PROGRESS, new_status=S.RESOLVED
    )
    _run()
    t.refresh_from_db()
    assert t.status == S.RESOLVED


def test_dry_run_changes_nothing(make_ticket, settings):
    t = make_ticket(S.RESOLVED, settings.AUTO_CLOSE_DAYS + 1)
    output = _run("--dry-run")
    t.refresh_from_db()
    assert t.status == S.RESOLVED
    assert f"[dry-run] {t.ticket_code}" in output


def test_is_idempotent(make_ticket, settings):
    make_ticket(S.RESOLVED, settings.AUTO_CLOSE_DAYS + 1)
    _run()
    assert "Tickets procesados: 0" in _run()


def test_skips_ticket_changed_concurrently(make_ticket, settings, monkeypatch):
    t = make_ticket(S.RESOLVED, settings.AUTO_CLOSE_DAYS + 1)

    def changed(*args, **kwargs):
        raise workflow.InvalidTransition()

    monkeypatch.setattr(workflow, "transition", changed)
    output = _run()
    assert f"Omitido {t.ticket_code}" in output
    assert "Tickets procesados: 0" in output
