"""BE-T06: asignación y reasignación autorizadas y trazables."""

import pytest

from apps.helpdesk import assignment, workflow
from apps.helpdesk.models import Area, AuditLog, Ticket
from apps.helpdesk.tickets import TicketService

pytestmark = pytest.mark.django_db

S = Ticket.Status


@pytest.fixture
def setup(make_user):
    it, fin = Area.objects.get(code="IT"), Area.objects.get(code="FINANCE")
    p = {
        "owner": make_user("owner", role="Usuario"),
        "it1": make_user("it1", role="Agente"),
        "it2": make_user("it2", role="Agente"),
        "fin1": make_user("fin1", role="Agente"),
        "sup": make_user("sup", role="Supervisor"),
        "admin": make_user("admin", role="Administrador"),
    }
    it.agents.add(p["it1"], p["it2"])
    fin.agents.add(p["fin1"])
    ticket = TicketService.create(user=p["owner"], subject="s", description="d")  # NEW, sin área
    return p, it, fin, ticket


def test_supervisor_assigns_new_ticket_and_status_advances(setup):
    p, it, fin, ticket = setup
    t = assignment.assign(ticket, actor=p["sup"], area=it, assignee=p["it1"], expected_version=1)
    assert (t.assigned_area, t.assigned_user, t.status) == (it, p["it1"], S.ASSIGNED)
    assert t.assigned_at is not None
    path = list(t.status_history.values_list("new_status", flat=True))
    assert path == [S.NEW, S.CLASSIFIED, S.ASSIGNED]
    log = AuditLog.objects.get(entity_type="helpdesk.ticket", action="ASSIGN")
    assert log.actor == p["sup"]
    assert log.previous_value_json == {"assigned_area_id": None, "assigned_user_id": None}
    assert log.new_value_json == {"assigned_area_id": it.pk, "assigned_user_id": p["it1"].pk}


def test_agent_takes_triage_ticket_in_own_area(setup):
    p, it, fin, ticket = setup
    t = assignment.assign(ticket, actor=p["it1"], area=it, assignee=p["it1"])
    assert t.assigned_user == p["it1"] and t.status == S.ASSIGNED


def test_agent_reassigns_to_colleague_and_it_is_audited_as_reassign(setup):
    p, it, fin, ticket = setup
    t = assignment.assign(ticket, actor=p["it1"], area=it, assignee=p["it1"])
    Ticket.objects.filter(pk=t.pk).update(status=S.IN_PROGRESS)
    t.refresh_from_db()
    t = assignment.assign(t, actor=p["it1"], area=it, assignee=p["it2"])
    assert t.assigned_user == p["it2"] and t.status == S.IN_PROGRESS  # sigue en proceso
    assert AuditLog.objects.filter(action="REASSIGN").count() == 1


def test_agent_cannot_move_ticket_to_other_area(setup):
    p, it, fin, ticket = setup
    with pytest.raises(workflow.TransitionForbidden):
        assignment.assign(ticket, actor=p["it1"], area=fin, assignee=p["fin1"])


def test_assignee_must_belong_to_area(setup):
    p, it, fin, ticket = setup
    with pytest.raises(workflow.InvalidTransition):
        assignment.assign(ticket, actor=p["sup"], area=it, assignee=p["fin1"])


def test_inactive_assignee_rejected(setup):
    p, it, fin, ticket = setup
    p["it2"].is_active = False
    p["it2"].save()
    with pytest.raises(workflow.InvalidTransition):
        assignment.assign(ticket, actor=p["sup"], area=it, assignee=p["it2"])


@pytest.mark.parametrize("who", ["owner", "admin"])
def test_user_and_admin_cannot_assign(setup, who):
    p, it, fin, ticket = setup
    with pytest.raises(workflow.TransitionForbidden):
        assignment.assign(ticket, actor=p[who], area=it)
    assert not assignment.assign_options(ticket, p[who])["can_assign"]


def test_only_supervisor_reassigns_escalated(setup):
    p, it, fin, ticket = setup
    t = assignment.assign(ticket, actor=p["sup"], area=it, assignee=p["it1"])
    Ticket.objects.filter(pk=t.pk).update(status=S.ESCALATED)
    t.refresh_from_db()
    with pytest.raises(workflow.TransitionForbidden):
        assignment.assign(t, actor=p["it1"], area=it, assignee=p["it2"])
    t = assignment.assign(t, actor=p["sup"], area=fin, assignee=p["fin1"])
    assert (t.assigned_area, t.status) == (fin, S.ASSIGNED)  # §32.1 fila 12


def test_reopened_ticket_returns_to_assigned_via_system_step(setup):
    p, it, fin, ticket = setup
    t = assignment.assign(ticket, actor=p["sup"], area=it, assignee=p["it1"])
    Ticket.objects.filter(pk=t.pk).update(status=S.REOPENED)
    t.refresh_from_db()
    t = assignment.assign(t, actor=p["it1"], area=it, assignee=p["it2"])
    assert t.status == S.ASSIGNED
    assert t.status_history.last().actor is None  # fila 17 no permite Agente: paso de sistema


@pytest.mark.parametrize("status", [S.RESOLVED, S.CLOSED, S.CANCELLED])
def test_finished_tickets_cannot_be_assigned(setup, status):
    p, it, fin, ticket = setup
    Ticket.objects.filter(pk=ticket.pk).update(status=status)
    ticket.refresh_from_db()
    with pytest.raises(workflow.InvalidTransition):
        assignment.assign(ticket, actor=p["sup"], area=it)
    assert not assignment.assign_options(ticket, p["sup"])["can_assign"]


def test_stale_version_rejected(setup):
    p, it, fin, ticket = setup
    with pytest.raises(workflow.StaleTicket):
        assignment.assign(ticket, actor=p["sup"], area=it, expected_version=99)


def test_same_assignment_is_noop(setup):
    p, it, fin, ticket = setup
    t = assignment.assign(ticket, actor=p["sup"], area=it, assignee=p["it1"])
    version = t.version
    t = assignment.assign(t, actor=p["sup"], area=it, assignee=p["it1"])
    assert t.version == version
    assert AuditLog.objects.filter(action__in=["ASSIGN", "REASSIGN"]).count() == 1


def test_assign_options(setup):
    p, it, fin, ticket = setup
    sup = assignment.assign_options(ticket, p["sup"])
    assert sup["can_assign"] and {a["name"] for a in sup["areas"]} == set(
        Area.objects.filter(is_active=True).values_list("name", flat=True)
    )
    agent = assignment.assign_options(ticket, p["it1"])
    assert [a["id"] for a in agent["areas"]] == [it.pk]
    assert [x["id"] for x in agent["areas"][0]["agents"]] == [p["it1"].pk, p["it2"].pk]


def test_confirming_category_area_advances_status(setup):
    """El área ya venía de la categoría: asignar a esa misma área sí avanza a ASSIGNED."""
    from apps.helpdesk.models import Category

    p, it, fin, _ = setup
    t = TicketService.create(
        user=p["owner"],
        subject="s",
        description="d",
        category=Category.objects.get(code="TECHNICAL"),
    )
    assert (t.assigned_area, t.status) == (it, S.NEW)
    t = assignment.assign(t, actor=p["sup"], area=it)
    assert t.status == S.ASSIGNED
    assert not AuditLog.objects.filter(action__in=["ASSIGN", "REASSIGN"]).exists()
