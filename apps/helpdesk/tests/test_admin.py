"""Catálogos administrables desde Django admin, con escritura auditada."""

import pytest
from django.urls import reverse

from apps.helpdesk.audit import Action
from apps.helpdesk.models import Area, AuditLog, Category

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client, make_user):
    # Django admin exige is_staff además de los permisos del grupo.
    client.force_login(make_user("admin", role="Administrador", is_staff=True))
    return client


def test_admin_can_create_area_and_it_is_audited(admin_client):
    response = admin_client.post(
        reverse("admin:helpdesk_area_add"),
        {"code": "LIBRARY", "name": "Biblioteca", "email": "", "is_active": "on"},
    )
    assert response.status_code == 302
    area = Area.objects.get(code="LIBRARY")
    log = AuditLog.objects.get(entity_type="helpdesk.area", entity_id=str(area.pk))
    assert log.action == Action.CREATE
    assert log.actor.username == "admin"


def test_admin_can_edit_category_and_it_is_audited(admin_client):
    category = Category.objects.get(code="GENERAL")
    response = admin_client.post(
        reverse("admin:helpdesk_category_change", args=[category.pk]),
        {
            "code": "GENERAL",
            "name": "General y otros",
            "default_area": category.default_area_id,
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    log = AuditLog.objects.filter(entity_type="helpdesk.category", action=Action.UPDATE).get()
    assert log.new_value_json == {"name": "General y otros"}


def test_admin_deactivate_action_is_audited(admin_client):
    areas = Area.objects.filter(code__in=["IT", "SERVICE"])
    response = admin_client.post(
        reverse("admin:helpdesk_area_changelist"),
        {"action": "deactivate", "_selected_action": [a.pk for a in areas]},
    )
    assert response.status_code == 302
    assert not Area.objects.filter(code__in=["IT", "SERVICE"], is_active=True).exists()
    assert AuditLog.objects.filter(action=Action.DEACTIVATE).count() == 2


def test_admin_cannot_delete_catalogs(admin_client):
    area = Area.objects.get(code="IT")
    response = admin_client.get(reverse("admin:helpdesk_area_delete", args=[area.pk]))
    assert response.status_code == 403


@pytest.mark.parametrize("view", ["admin:helpdesk_auditlog_add"])
def test_audit_log_cannot_be_added_from_admin(admin_client, view):
    assert admin_client.get(reverse(view)).status_code == 403


def test_audit_log_is_read_only_in_admin(admin_client):
    log = AuditLog.objects.first()
    url = reverse("admin:helpdesk_auditlog_change", args=[log.pk])
    response = admin_client.post(url, {"action": "HACKED"})
    log.refresh_from_db()
    assert log.action != "HACKED"
    assert response.status_code in (302, 403)
    assert admin_client.get(reverse("admin:helpdesk_auditlog_changelist")).status_code == 200
