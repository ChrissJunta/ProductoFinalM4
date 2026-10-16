"""CONTRACT-016 (responde CONTRACT-FRONT-005): administración propia de catálogos."""

import pytest
from django.urls import reverse

from apps.automation.models import Intent, IntentAction, RoutingRule
from apps.helpdesk.catalog_admin import ENTITIES
from apps.helpdesk.models import Area, AuditLog, Category, SLAPolicy, Subcategory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client, make_user):
    client.force_login(make_user("admin", role="Administrador"))
    return client


def url(name, *args):
    return reverse(f"manage:{name}", args=args)


def audit_count(model):
    return AuditLog.objects.filter(entity_type=model._meta.label_lower).count()


# --- Permisos -------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["Usuario", "Agente", "Supervisor"])
def test_only_administrator(client, make_user, role):
    client.force_login(make_user("x", role=role))
    assert client.get(url("index")).status_code == 403
    assert client.get(url("list", "areas")).status_code == 403
    assert (
        client.post(url("toggle", "areas", Area.objects.first().pk), {"active": "0"}).status_code
        == 403
    )


def test_anonymous_redirects_to_login(client):
    assert client.get(url("list", "areas")).status_code == 302


def test_unknown_entity_or_object_is_404(admin_client):
    assert admin_client.get(url("list", "usuarios")).status_code == 404
    assert admin_client.get(url("edit", "areas", 999999)).status_code == 404
    assert admin_client.get(url("edit", "usuarios", 1)).status_code == 404


# --- Índice y listados ----------------------------------------------------------------------


def test_index_lists_all_entities(admin_client):
    ctx = admin_client.get(url("index")).context
    assert [e["slug"] for e in ctx["entities"]] == list(ENTITIES)
    areas = ctx["entities"][0]
    assert (areas["active"], areas["total"]) == (4, 4)


@pytest.mark.parametrize("slug", list(ENTITIES))
def test_every_list_and_forms_render(admin_client, slug):
    r = admin_client.get(url("list", slug))
    assert r.status_code == 200 and r.context["rows"]
    row = r.context["rows"][0]
    assert len(row["values"]) == len(r.context["columns"])
    assert admin_client.get(row["edit_url"]).status_code == 200
    assert admin_client.get(r.context["create_url"]).status_code == 200


def test_list_filters_and_pagination(admin_client):
    r = admin_client.get(url("list", "intents"), {"q": "incorrecta", "status": "active"})
    codes = {row["object"].code for row in r.context["rows"]}
    assert codes == {"GRADE_DISCREPANCY"}  # nombre «Nota incorrecta»
    assert r.context["filters"] == {"q": "incorrecta", "status": "active"}
    Intent.objects.filter(code="GRADE_DISCREPANCY").update(is_active=False)
    r = admin_client.get(url("list", "intents"), {"status": "inactive"})
    assert [row["object"].code for row in r.context["rows"]] == ["GRADE_DISCREPANCY"]
    r = admin_client.get(url("list", "intents"), {"status": "raro", "page": "x"})
    assert r.context["filters"]["status"] == "all" and r.context["page_obj"].number == 1
    assert r.context["page_obj"].paginator.count == 21


def test_area_list_shows_agents(admin_client, make_user):
    Area.objects.get(code="IT").agents.add(make_user("tomas", role="Agente"))
    rows = admin_client.get(url("list", "areas"), {"q": "IT"}).context["rows"]
    assert rows[0]["values"][-1] == "tomas"


# --- Alta y edición -------------------------------------------------------------------------


def test_create_category_audited(admin_client):
    before = audit_count(Category)
    r = admin_client.post(
        url("create", "categories"),
        {
            "code": "LIBRARY",
            "name": "Biblioteca",
            "default_area": Area.objects.get(code="SERVICE").pk,
        },
    )
    assert r.status_code == 302 and r.url == url("list", "categories")
    assert Category.objects.get(code="LIBRARY").default_area.code == "SERVICE"
    assert audit_count(Category) == before + 1


def test_code_cannot_change_on_edit(admin_client):
    area = Area.objects.get(code="IT")
    r = admin_client.post(
        url("edit", "areas", area.pk), {"code": "HACK", "name": "TI", "email": ""}
    )
    assert r.status_code == 302
    area.refresh_from_db()
    assert (area.code, area.name) == ("IT", "TI")


def test_form_errors_are_returned(admin_client):
    r = admin_client.post(url("create", "categories"), {"code": "minúsculas", "name": ""})
    assert r.status_code == 200
    assert {"code", "name", "default_area"} <= set(r.context["form"].errors)


def test_model_validation_errors_reach_form(admin_client):
    r = admin_client.post(
        url("create", "routing"), {"area": Area.objects.get(code="IT").pk, "order": 1}
    )  # regla sin criterios: RoutingRule.clean
    assert r.status_code == 200 and r.context["form"].non_field_errors()
    r = admin_client.post(
        url("create", "actions"),
        {"intent": Intent.objects.get(code="CHECK_CONTACT").pk, "action_type": "TEMPLATE_RESPONSE",
         "fallback_action": "CREATE_TICKET"},
    )  # fmt: skip
    assert "response_template" in r.context["form"].errors


def test_unique_active_constraint_is_reported(admin_client):
    r = admin_client.post(
        url("create", "actions"),
        {"intent": Intent.objects.get(code="CHECK_CONTACT").pk, "action_type": "TEMPLATE_RESPONSE",
         "response_template": "otra", "fallback_action": "CREATE_TICKET"},
    )  # fmt: skip
    assert r.status_code == 200 and r.context["form"].non_field_errors()


def test_area_agents_saved_with_audit(admin_client, make_user):
    agent = make_user("tomas", role="Agente")
    make_user("user", role="Usuario")
    area = Area.objects.get(code="IT")
    form = admin_client.get(url("edit", "areas", area.pk)).context["form"]
    assert list(form.fields["agents"].queryset) == [agent]  # solo agentes activos
    r = admin_client.post(
        url("edit", "areas", area.pk), {"name": area.name, "email": "", "agents": [agent.pk]}
    )
    assert r.status_code == 302 and list(area.agents.all()) == [agent]
    assert AuditLog.objects.filter(
        entity_type="helpdesk.area", entity_id=str(area.pk), new_value_json__agent_ids=[agent.pk]
    ).exists()
    assert admin_client.get(url("edit", "areas", area.pk)).context["form"].initial["agents"] == [
        agent.pk
    ]


def test_relations_offer_only_active_options_plus_current(admin_client):
    sub = Subcategory.objects.get(category__code="ACADEMIC", code="GRADES")
    Category.objects.filter(code="ACADEMIC").update(is_active=False)
    create = admin_client.get(url("create", "subcategories")).context["form"]
    assert not create.fields["category"].queryset.filter(code="ACADEMIC").exists()
    edit = admin_client.get(url("edit", "subcategories", sub.pk)).context["form"]
    assert edit.fields["category"].queryset.filter(code="ACADEMIC").exists()


def test_intent_keywords_and_routing_editable(admin_client):
    intent = Intent.objects.get(code="CHECK_REQUIREMENTS")
    data = {
        "name": intent.name, "automation_level": "N1", "requires_authentication": "",
        "keywords": "requisitos\nsilabo",
    }  # fmt: skip
    assert admin_client.post(url("edit", "intents", intent.pk), data).status_code == 302
    intent.refresh_from_db()
    assert intent.keywords == "requisitos\nsilabo"
    rule = RoutingRule.objects.get(intent__code="PASSWORD_PROBLEM")
    r = admin_client.post(
        url("edit", "routing", rule.pk),
        {"intent": rule.intent_id, "area": Area.objects.get(code="SERVICE").pk,
         "priority": "HIGH", "order": 3},
    )  # fmt: skip
    assert r.status_code == 302
    rule.refresh_from_db()
    assert (rule.area.code, rule.priority, rule.order) == ("SERVICE", "HIGH", 3)


def test_sla_and_provider_method_choices(admin_client):
    policy = SLAPolicy.objects.filter(category__isnull=True, priority="LOW").get()
    r = admin_client.post(
        url("edit", "sla", policy.pk),
        {"priority": "LOW", "first_response_minutes": 100, "resolution_minutes": 2000,
         "business_hours_only": "on"},
    )  # fmt: skip
    assert r.status_code == 302
    policy.refresh_from_db()
    assert (policy.first_response_minutes, policy.resolution_minutes) == (100, 2000)
    form = admin_client.get(url("create", "actions")).context["form"]
    assert [c for c, _ in form.fields["provider_method"].choices][1:] == list(
        IntentAction.PROVIDER_METHODS
    )


# --- Activar / desactivar --------------------------------------------------------------------


def test_toggle_audited_and_idempotent(admin_client):
    area = Area.objects.get(code="SERVICE")
    r = admin_client.post(url("toggle", "areas", area.pk), {"active": "0"})
    assert r.status_code == 302 and r.url == url("list", "areas")
    area.refresh_from_db()
    assert not area.is_active
    assert AuditLog.objects.filter(entity_id=str(area.pk), action="DEACTIVATE").count() == 1
    admin_client.post(url("toggle", "areas", area.pk), {"active": "0"})
    assert AuditLog.objects.filter(entity_id=str(area.pk), action="DEACTIVATE").count() == 1
    admin_client.post(url("toggle", "areas", area.pk), {"active": "1"})
    area.refresh_from_db()
    assert area.is_active


def test_toggle_requires_value_and_post(admin_client):
    area = Area.objects.get(code="SERVICE")
    admin_client.post(url("toggle", "areas", area.pk), {})
    area.refresh_from_db()
    assert area.is_active
    assert admin_client.get(url("toggle", "areas", area.pk)).status_code == 405


def test_toggle_reports_unique_conflict(admin_client):
    first = IntentAction.objects.get(intent__code="CHECK_CONTACT")
    first.is_active = False
    first.save()
    IntentAction.objects.create(
        intent=first.intent, action_type="TEMPLATE_RESPONSE", response_template="nueva"
    )
    r = admin_client.post(url("toggle", "actions", first.pk), {"active": "1"}, follow=True)
    first.refresh_from_db()
    assert not first.is_active
    assert any("ya existe" in str(m) for m in r.context["messages"])
