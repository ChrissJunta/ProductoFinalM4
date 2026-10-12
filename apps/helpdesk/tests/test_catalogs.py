import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError

from apps.helpdesk import catalogs
from apps.helpdesk.audit import Action
from apps.helpdesk.models import Area, AuditLog, Category, Subcategory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user(make_user):
    return make_user("admin", role="Administrador")


def _logs(instance):
    return AuditLog.objects.filter(
        entity_type=instance._meta.label_lower, entity_id=str(instance.pk)
    ).order_by("id")


# --- Datos iniciales ---------------------------------------------------------


def test_initial_catalogs_seeded():
    assert set(Area.objects.values_list("code", flat=True)) == {
        "ACADEMIC",
        "FINANCE",
        "IT",
        "SERVICE",
    }
    grades = Subcategory.objects.get(category__code="ACADEMIC", code="GRADES")
    assert grades.category.default_area.code == "ACADEMIC"
    assert Subcategory.objects.count() == 12


def test_initial_catalogs_are_audited_as_system():
    area = Area.objects.get(code="IT")
    log = _logs(area).get()
    assert log.actor_type == AuditLog.ActorType.SYSTEM
    assert log.action == Action.CREATE
    assert log.new_value_json["code"] == "IT"


# --- Validaciones de modelo ----------------------------------------------------


@pytest.mark.parametrize("code", ["academic", "1AREA", "MI AREA", "ÁREA", ""])
def test_invalid_code_rejected(code):
    with pytest.raises(ValidationError):
        Area(code=code, name="X").full_clean()


def test_area_code_unique():
    with pytest.raises(IntegrityError):
        Area.objects.create(code="IT", name="Duplicada")


def test_subcategory_code_unique_per_category():
    academic = Category.objects.get(code="ACADEMIC")
    financial = Category.objects.get(code="FINANCIAL")
    Subcategory.objects.create(
        category=financial, code="GRADES", name="Mismo código, otra categoría"
    )
    with pytest.raises(IntegrityError):
        Subcategory.objects.create(category=academic, code="GRADES", name="Duplicada")


def test_area_in_use_cannot_be_deleted():
    with pytest.raises(ProtectedError):
        Area.objects.get(code="ACADEMIC").delete()


def test_active_category_requires_active_default_area(admin_user):
    area = Area.objects.get(code="IT")
    catalogs.set_active(area, False, actor=admin_user)
    category = Category(code="NEW", name="Nueva", default_area=Area.objects.get(code="IT"))
    with pytest.raises(ValidationError) as exc:
        category.full_clean()
    assert "default_area" in exc.value.message_dict


def test_str():
    sub = Subcategory.objects.get(category__code="ACADEMIC", code="GRADES")
    assert str(sub) == "Académico / Calificaciones"
    assert str(Area.objects.get(code="IT")) == "Soporte Tecnológico (IT)"


# --- Escritura auditada ---------------------------------------------------------


def test_create_is_audited(admin_user):
    area = catalogs.save_catalog_item(
        Area(code="LIBRARY", name="Biblioteca", email="biblio@example.com"), actor=admin_user
    )
    log = _logs(area).get()
    assert log.action == Action.CREATE
    assert log.actor == admin_user
    assert log.actor_type == AuditLog.ActorType.USER
    assert log.previous_value_json is None
    assert log.new_value_json == {
        "code": "LIBRARY",
        "name": "Biblioteca",
        "email": "biblio@example.com",
        "is_active": True,
    }


def test_create_invalid_is_not_saved_nor_audited(admin_user):
    before = AuditLog.objects.count()
    with pytest.raises(ValidationError):
        catalogs.save_catalog_item(Area(code="bad code", name="X"), actor=admin_user)
    assert not Area.objects.filter(name="X").exists()
    assert AuditLog.objects.count() == before


def test_update_audits_only_changed_fields(admin_user):
    category = Category.objects.get(code="GENERAL")
    category.name = "General y otros"
    category.default_area = Area.objects.get(code="ACADEMIC")
    catalogs.save_catalog_item(category, actor=admin_user)

    log = _logs(category).last()
    assert log.action == Action.UPDATE
    assert log.previous_value_json == {
        "name": "General",
        "default_area_id": Area.objects.get(code="SERVICE").pk,
    }
    assert log.new_value_json == {
        "name": "General y otros",
        "default_area_id": Area.objects.get(code="ACADEMIC").pk,
    }


def test_update_without_changes_is_not_audited(admin_user):
    area = Area.objects.get(code="IT")
    before = _logs(area).count()
    catalogs.save_catalog_item(area, actor=admin_user)
    assert _logs(area).count() == before


def test_deactivate_and_activate_are_audited(admin_user):
    sub = Subcategory.objects.get(category__code="GENERAL", code="OTHER")
    catalogs.set_active(sub, False, actor=admin_user)
    sub.refresh_from_db()
    assert sub.is_active is False

    catalogs.set_active(sub, True, actor=admin_user)
    actions = list(_logs(sub).values_list("action", flat=True))
    assert actions[-2:] == [Action.DEACTIVATE, Action.ACTIVATE]


def test_set_active_noop_is_not_audited(admin_user):
    area = Area.objects.get(code="IT")
    before = _logs(area).count()
    catalogs.set_active(area, True, actor=admin_user)
    assert _logs(area).count() == before
