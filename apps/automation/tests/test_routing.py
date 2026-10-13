"""BE-T09: catálogo de intenciones, acciones y routing configurable."""

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from apps.automation.models import AutomationLevel, Intent, IntentAction, RoutingRule
from apps.automation.services import AutomationService
from apps.helpdesk import catalogs
from apps.helpdesk.models import Area, AuditLog, Category, Subcategory, Ticket
from apps.helpdesk.tickets import TicketService

pytestmark = pytest.mark.django_db

SPEC_INTENTS = {
    "CHECK_SCHEDULE", "CHECK_GRADE", "CHECK_DEBT", "CHECK_ENROLLMENT", "CHECK_SUBJECTS",
    "CHECK_TICKET", "CHECK_ACADEMIC_DATES", "CHECK_CONTACT", "CHECK_REQUIREMENTS",
    "GRADE_DISCREPANCY", "PAYMENT_NOT_REFLECTED", "DEBT_DISPUTE", "ENROLLMENT_PROBLEM",
    "SUBJECT_NOT_VISIBLE", "ACCESS_PROBLEM", "PASSWORD_PROBLEM", "CERTIFICATE_REQUEST",
    "PROFILE_UPDATE", "GENERAL_COMPLAINT", "UNKNOWN_REQUEST",
}  # fmt: skip


def intent(code):
    return Intent.objects.get(code=code)


def area(code):
    return Area.objects.get(code=code)


# --- Catálogo inicial (SPEC §29) ------------------------------------------------------


def test_initial_catalog_matches_spec():
    assert set(Intent.objects.values_list("code", flat=True)) == SPEC_INTENTS


@pytest.mark.parametrize(
    "code,level,action,auth",
    [
        ("CHECK_GRADE", "N0", "PROVIDER_QUERY", True),
        ("CHECK_CONTACT", "N1", "TEMPLATE_RESPONSE", False),
        ("PAYMENT_NOT_REFLECTED", "N2", "CREATE_TICKET", True),
        ("PASSWORD_PROBLEM", "N3", "CREATE_TICKET", False),
        ("UNKNOWN_REQUEST", "N4", "HUMAN_REVIEW", False),
    ],
)
def test_levels_and_actions(code, level, action, auth):
    i = intent(code)
    assert (i.automation_level, i.requires_authentication) == (level, auth)
    assert i.actions.get(is_active=True).action_type == action


def test_n0_actions_use_provider_contract_and_n1_have_templates():
    for a in IntentAction.objects.select_related("intent"):
        if a.intent.automation_level == AutomationLevel.N0:
            assert a.provider_method in IntentAction.PROVIDER_METHODS
        if a.intent.automation_level == AutomationLevel.N1:
            assert a.response_template.strip()


# --- Validaciones de configuración -------------------------------------------------------


def test_action_validation():
    with pytest.raises(ValidationError):
        IntentAction(intent=intent("CHECK_GRADE"), action_type="PROVIDER_QUERY",
                     provider_method="borrar_notas").full_clean()  # fmt: skip
    with pytest.raises(ValidationError):
        IntentAction(intent=intent("CHECK_CONTACT"), action_type="TEMPLATE_RESPONSE").full_clean()


def test_rule_needs_some_criteria_and_coherent_subcategory():
    with pytest.raises(ValidationError):
        RoutingRule(area=area("IT")).full_clean()
    with pytest.raises(ValidationError):
        RoutingRule(
            area=area("IT"),
            category=Category.objects.get(code="FINANCIAL"),
            subcategory=Subcategory.objects.get(category__code="ACADEMIC", code="GRADES"),
        ).full_clean()


# --- Motor de routing --------------------------------------------------------------------


def test_rule_by_intent():
    rule = AutomationService.matching_rule(intent_id=intent("PAYMENT_NOT_REFLECTED").pk)
    assert (rule.area.code, rule.priority, rule.requires_validation) == ("FINANCE", "HIGH", True)


def test_no_rule_for_plain_web_ticket():
    assert (
        AutomationService.matching_rule(category_id=Category.objects.get(code="GENERAL").pk) is None
    )


def test_lowest_order_wins_and_wildcards():
    tech = Category.objects.get(code="TECHNICAL")
    pwd = Subcategory.objects.get(category=tech, code="PASSWORD")
    broad = RoutingRule.objects.create(category=tech, area=area("SERVICE"), order=50)
    narrow = RoutingRule.objects.create(subcategory=pwd, area=area("IT"), priority="HIGH", order=5)
    assert AutomationService.matching_rule(category_id=tech.pk, subcategory_id=pwd.pk) == narrow
    assert AutomationService.matching_rule(category_id=tech.pk) == broad


def test_inactive_rule_area_or_intent_are_ignored(make_user):
    admin = make_user("admin", role="Administrador")
    pid = intent("PASSWORD_PROBLEM")
    catalogs.set_active(pid, False, actor=admin)
    assert AutomationService.matching_rule(intent_id=pid.pk) is None


# --- Integración con la creación de tickets ------------------------------------------------


def test_ticket_creation_applies_routing_before_sla(make_user):
    t = TicketService.create(
        user=make_user(), subject="s", description="d", intent=intent("PAYMENT_NOT_REFLECTED")
    )
    assert (t.assigned_area.code, t.priority, t.intent.code) == (
        "FINANCE",
        "HIGH",
        "PAYMENT_NOT_REFLECTED",
    )
    log = AuditLog.objects.get(entity_type="helpdesk.ticket", entity_id=str(t.pk))
    assert log.metadata_json["requires_validation"] is True
    assert log.new_value_json["intent_id"] == t.intent_id
    # SLA calculado con la prioridad ya enrutada (HIGH: 60 / 1440 min laborables).
    from apps.helpdesk import sla

    assert sla.policy_for(t.category, t.priority).priority == "HIGH"


def test_without_rule_category_default_area_is_kept(make_user):
    t = TicketService.create(
        user=make_user(),
        subject="s",
        description="d",
        category=Category.objects.get(code="FINANCIAL"),
    )
    assert (t.assigned_area.code, t.priority) == ("FINANCE", "MEDIUM")


def test_routing_changes_without_redeploy(make_user):
    """Criterio de aceptación BE-T09: cambiar la configuración cambia el próximo ticket."""
    admin, user = make_user("admin", role="Administrador"), make_user("u")
    pwd = intent("PASSWORD_PROBLEM")
    first = TicketService.create(user=user, subject="a", description="d", intent=pwd)
    assert first.assigned_area.code == "IT"

    rule = RoutingRule.objects.get(intent=pwd)
    rule.area, rule.priority = area("SERVICE"), "CRITICAL"
    catalogs.save_catalog_item(rule, actor=admin)  # misma vía que el admin, auditada

    second = TicketService.create(user=user, subject="b", description="d", intent=pwd)
    assert (second.assigned_area.code, second.priority) == ("SERVICE", "CRITICAL")
    first.refresh_from_db()
    assert first.assigned_area.code == "IT"  # los tickets existentes no se tocan
    assert AuditLog.objects.filter(entity_type="automation.routingrule", action="UPDATE").exists()


# --- Admin y permisos ---------------------------------------------------------------------


@pytest.fixture
def admin_client(client, make_user):
    client.force_login(make_user("admin", role="Administrador", is_staff=True))
    return client


def test_admin_edits_rule_with_audit(admin_client):
    rule = RoutingRule.objects.get(intent__code="ACCESS_PROBLEM")
    r = admin_client.post(
        reverse("admin:automation_routingrule_change", args=[rule.pk]),
        {
            "intent": rule.intent_id,
            "area": area("SERVICE").pk,
            "priority": "LOW",
            "order": 7,
            "is_active": "on",
        },  # fmt: skip
    )
    assert r.status_code == 302
    rule.refresh_from_db()
    assert (rule.area.code, rule.order) == ("SERVICE", 7)
    assert (
        AuditLog.objects.filter(entity_type="automation.routingrule", action="UPDATE").count() == 1
    )


def test_admin_cannot_delete_intents(admin_client):
    i = intent("CHECK_GRADE")
    assert (
        admin_client.get(reverse("admin:automation_intent_delete", args=[i.pk])).status_code == 403
    )


@pytest.mark.parametrize(
    "role,expected",
    [
        ("Administrador", {f"{a}_{m}" for m in ("intent", "intentaction", "routingrule")
                           for a in ("add", "change", "view")}),
        ("Supervisor", {"view_intent", "view_intentaction", "view_routingrule"}),
        ("Agente", {"view_intent"}),
        ("Usuario", set()),
    ],
)  # fmt: skip
def test_role_permissions(make_user, role, expected):
    user = make_user("x", role=role)
    granted = {
        p.split(".", 1)[1] for p in user.get_all_permissions() if p.startswith("automation.")
    }
    assert granted == expected


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_automation_migrations_are_reversible():
    call_command("migrate", "helpdesk", "0009", verbosity=0)  # quita Ticket.intent primero
    call_command("migrate", "automation", "zero", verbosity=0)
    call_command("migrate", verbosity=0)
    assert Intent.objects.count() == 20
    assert Ticket._meta.get_field("intent")
