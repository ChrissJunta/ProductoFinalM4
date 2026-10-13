import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.helpdesk import audit, workflow
from apps.helpdesk.models import Area, AuditLog, Ticket, TicketStatusHistory
from apps.helpdesk.tickets import TicketService
from apps.helpdesk.workflow import TRANSITIONS, Actor

pytestmark = pytest.mark.django_db

S = Ticket.Status


@pytest.fixture
def people(make_user):
    return {
        "owner": make_user("owner", role="Usuario"),
        "other_user": make_user("other", role="Usuario"),
        "agent": make_user("agent", role="Agente"),
        "assigned_agent": make_user("assigned", role="Agente"),
        "supervisor": make_user("supervisor", role="Supervisor"),
        "admin": make_user("admin", role="Administrador"),
    }


@pytest.fixture
def ticket(people):
    t = TicketService.create(user=people["owner"], subject="Asunto", description="Detalle")
    Ticket.objects.filter(pk=t.pk).update(
        assigned_area=Area.objects.get(code="IT"), assigned_user=people["assigned_agent"]
    )
    t.refresh_from_db()
    return t


def put_in(ticket, status, **fields):
    """Coloca el ticket en un estado sin pasar por el workflow (solo para preparar pruebas)."""
    if status == S.CLOSED:
        fields.setdefault("closed_at", timezone.now())
    Ticket.objects.filter(pk=ticket.pk).update(status=status, **fields)
    ticket.refresh_from_db()
    return ticket


# Qué categoría de §32.1 representa cada persona de prueba.
PERSONA_KINDS = {
    "owner": {Actor.OWNER},
    "other_user": set(),
    "agent": {Actor.AGENT},
    "assigned_agent": {Actor.AGENT, Actor.ASSIGNED_AGENT},
    "supervisor": {Actor.SUPERVISOR},
    "admin": set(),  # Administrador configura; no opera tickets (§9.4, §32.1)
    "system": {Actor.SYSTEM},
}


# --- Matriz completa: 17 transiciones × 7 actores --------------------------------


@pytest.mark.parametrize("persona", PERSONA_KINDS)
@pytest.mark.parametrize("edge", TRANSITIONS, ids=lambda e: f"{e[0]}->{e[1]}")
def test_transition_matrix(ticket, people, edge, persona):
    source, target = edge
    put_in(ticket, source)
    actor = None if persona == "system" else people[persona]
    allowed = bool(TRANSITIONS[edge].actors & PERSONA_KINDS[persona])

    if allowed:
        updated = workflow.transition(ticket, target, actor=actor, reason="motivo")
        assert updated.status == target
    else:
        with pytest.raises(workflow.TransitionForbidden):
            workflow.transition(ticket, target, actor=actor, reason="motivo")
        ticket.refresh_from_db()
        assert ticket.status == source


def test_table_has_the_17_transitions_of_the_spec():
    assert len(TRANSITIONS) == 17


@pytest.mark.parametrize(
    "edge",
    [(a, b) for a in S.values for b in S.values if a != b and (a, b) not in TRANSITIONS],
    ids=lambda e: f"{e[0]}->{e[1]}",
)
def test_transitions_outside_the_table_are_rejected(ticket, people, edge):
    source, target = edge
    put_in(ticket, source)
    with pytest.raises(workflow.InvalidTransition):
        workflow.transition(ticket, target, actor=people["supervisor"], reason="motivo")


@pytest.mark.parametrize("status", [S.CANCELLED])
def test_terminal_states(ticket, people, status):
    put_in(ticket, status)
    assert workflow.allowed_targets(ticket, people["supervisor"]) == []
    assert workflow.allowed_targets(ticket, None) == []


# --- Motivo obligatorio ----------------------------------------------------------


@pytest.mark.parametrize(
    "edge",
    [e for e, rule in TRANSITIONS.items() if rule.reason_required],
    ids=lambda e: f"{e[0]}->{e[1]}",
)
def test_reason_required(ticket, people, edge):
    source, target = edge
    put_in(ticket, source)
    actors = TRANSITIONS[edge].actors
    actor = people["owner"] if Actor.OWNER in actors else people["supervisor"]
    with pytest.raises(workflow.ReasonRequired):
        workflow.transition(ticket, target, actor=actor, reason="   ")


# --- Bloqueo optimista, historial y auditoría --------------------------------------


def test_stale_version_rejected(ticket, people):
    put_in(ticket, S.ASSIGNED)
    with pytest.raises(workflow.StaleTicket):
        workflow.transition(
            ticket, S.IN_PROGRESS, actor=people["supervisor"], expected_version=ticket.version + 1
        )
    ticket.refresh_from_db()
    assert ticket.status == S.ASSIGNED


def test_transition_updates_version_history_and_audit(ticket, people):
    put_in(ticket, S.ASSIGNED)
    version = ticket.version
    updated = workflow.transition(
        ticket,
        S.ESCALATED,
        actor=people["assigned_agent"],
        reason="Requiere a Finanzas",
        expected_version=version,
    )
    assert updated.version == version + 1

    entry = TicketStatusHistory.objects.filter(ticket=ticket).last()
    assert (entry.previous_status, entry.new_status) == (S.ASSIGNED, S.ESCALATED)
    assert entry.actor == people["assigned_agent"]
    assert entry.reason == "Requiere a Finanzas"

    log = AuditLog.objects.filter(entity_type="helpdesk.ticket", action="STATUS_CHANGE").get()
    assert log.previous_value_json == {"status": "ASSIGNED"}
    assert log.new_value_json == {"status": "ESCALATED"}
    assert log.metadata_json == {"reason": "Requiere a Finanzas"}


def test_system_transition_is_audited_as_system(ticket):
    workflow.transition(ticket, S.CLASSIFIED)
    log = AuditLog.objects.filter(action="STATUS_CHANGE").get()
    assert log.actor is None
    assert log.actor_type == AuditLog.ActorType.SYSTEM
    assert TicketStatusHistory.objects.filter(ticket=ticket).last().actor is None


def test_creation_writes_initial_history(ticket):
    first = TicketStatusHistory.objects.filter(ticket=ticket).first()
    assert (first.previous_status, first.new_status) == ("", S.NEW)
    assert first.actor == ticket.user


def test_transition_is_atomic(ticket, people, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("fallo de auditoría")

    put_in(ticket, S.ASSIGNED)
    monkeypatch.setattr(audit, "record", boom)
    with pytest.raises(RuntimeError):
        workflow.transition(ticket, S.IN_PROGRESS, actor=people["supervisor"])
    ticket.refresh_from_db()
    assert ticket.status == S.ASSIGNED
    assert not TicketStatusHistory.objects.filter(new_status=S.IN_PROGRESS).exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_update_detected(make_user):
    """Dos usuarios leen la misma versión y actúan a la vez: solo uno gana."""
    owner = make_user("owner2", role="Usuario")
    ticket = TicketService.create(user=owner, subject="s", description="d")
    ticket = put_in(ticket, S.RESOLVED)
    version = ticket.version
    barrier = threading.Barrier(2)
    results = []

    def act(user, target, reason):
        try:
            barrier.wait(timeout=10)
            workflow.transition(ticket, target, actor=user, reason=reason, expected_version=version)
            results.append("ok")
        except workflow.TransitionError as exc:
            results.append(type(exc).__name__)
        finally:
            connection.close()

    threads = [
        threading.Thread(target=act, args=(owner, S.CLOSED, "")),
        threading.Thread(target=act, args=(owner, S.IN_PROGRESS, "No se resolvió")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["StaleTicket", "ok"]
    ticket.refresh_from_db()
    assert ticket.version == version + 1


# --- Condiciones y efectos ---------------------------------------------------------


def test_assigned_requires_area_or_user(people):
    t = TicketService.create(user=people["owner"], subject="s", description="d")
    put_in(t, S.CLASSIFIED)
    with pytest.raises(workflow.InvalidTransition):
        workflow.transition(t, S.ASSIGNED, actor=people["supervisor"])
    assert S.ASSIGNED not in workflow.allowed_targets(t, people["supervisor"])


def test_assigned_sets_assigned_at(ticket, people):
    put_in(ticket, S.CLASSIFIED)
    updated = workflow.transition(ticket, S.ASSIGNED, actor=people["agent"])
    assert updated.assigned_at is not None


def test_resolve_close_and_reopen_timestamps(ticket, people):
    put_in(ticket, S.IN_PROGRESS)
    t = workflow.transition(ticket, S.RESOLVED, actor=people["assigned_agent"], reason="Listo")
    assert t.resolved_at is not None
    t = workflow.transition(t, S.CLOSED, actor=people["owner"])
    assert t.closed_at is not None
    t = workflow.transition(t, S.REOPENED, actor=people["owner"])
    assert (t.resolved_at, t.closed_at) == (None, None)


def test_reject_resolution_clears_resolved_at_and_keeps_sla(ticket, people):
    due = timezone.now() + timedelta(hours=5)
    put_in(ticket, S.RESOLVED, resolved_at=timezone.now(), sla_due_at=due)
    t = workflow.transition(ticket, S.IN_PROGRESS, actor=people["owner"], reason="Sigue igual")
    assert t.resolved_at is None
    assert t.sla_due_at == due


def test_reopen_window(ticket, people, settings):
    old = timezone.now() - timedelta(days=settings.REOPEN_WINDOW_DAYS, minutes=1)
    put_in(ticket, S.CLOSED, closed_at=old)
    with pytest.raises(workflow.InvalidTransition) as exc:
        workflow.transition(ticket, S.REOPENED, actor=people["owner"])
    assert "7 días" in exc.value.message
    assert workflow.allowed_targets(ticket, people["owner"]) == []


def test_reopened_returns_to_last_active_agent(ticket, people):
    put_in(ticket, S.REOPENED)
    t = workflow.transition(ticket, S.ASSIGNED)
    assert t.assigned_user == people["assigned_agent"]


def test_reopened_with_inactive_agent_keeps_only_area(ticket, people):
    people["assigned_agent"].is_active = False
    people["assigned_agent"].save()
    put_in(ticket, S.REOPENED)
    t = workflow.transition(ticket, S.ASSIGNED)
    assert t.assigned_user is None
    assert t.assigned_area.code == "IT"


# --- allowed_targets (para mostrar solo acciones válidas) ---------------------------


def test_allowed_targets(ticket, people):
    put_in(ticket, S.IN_PROGRESS)
    assert set(workflow.allowed_targets(ticket, people["assigned_agent"])) == {
        S.WAITING_USER,
        S.ESCALATED,
        S.RESOLVED,
    }
    assert workflow.allowed_targets(ticket, people["agent"]) == []
    assert workflow.allowed_targets(ticket, people["owner"]) == []

    put_in(ticket, S.RESOLVED)
    assert set(workflow.allowed_targets(ticket, people["owner"])) == {S.CLOSED, S.IN_PROGRESS}
