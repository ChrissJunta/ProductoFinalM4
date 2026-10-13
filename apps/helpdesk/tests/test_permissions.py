"""Matriz de permisos de modelo por rol (migraciones helpdesk.0003 y 0007)."""

import pytest
from django.core.management import call_command

from apps.helpdesk.models import Area

pytestmark = pytest.mark.django_db

CATALOGS = ["area", "category", "subcategory"]

EXPECTED = {
    "Administrador": {
        f"{a}_{m}" for m in [*CATALOGS, "slapolicy"] for a in ("add", "change", "view")
    }
    | {"view_auditlog", "view_alert"},
    "Supervisor": {f"view_{m}" for m in [*CATALOGS, "slapolicy"]} | {"view_auditlog", "view_alert"},
    "Agente": {f"view_{m}" for m in [*CATALOGS, "slapolicy"]},
    "Usuario": set(),
}


@pytest.mark.parametrize("role", EXPECTED)
def test_role_permissions(make_user, role):
    user = make_user(role=role)
    granted = {p.split(".", 1)[1] for p in user.get_all_permissions() if p.startswith("helpdesk.")}
    assert granted == EXPECTED[role]


@pytest.mark.parametrize("role", EXPECTED)
def test_nobody_can_delete_catalogs_or_change_audit(make_user, role):
    user = make_user(role=role)
    forbidden = [f"delete_{m}" for m in [*CATALOGS, "slapolicy"]]
    forbidden += ["change_auditlog", "delete_auditlog", "add_alert", "change_alert", "delete_alert"]
    for codename in forbidden:
        assert not user.has_perm(f"helpdesk.{codename}")


# serialized_rollback: restaura los datos de las migraciones (grupos, catálogos)
# que el vaciado de la prueba transaccional anterior haya borrado.
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_helpdesk_migrations_are_reversible():
    call_command("migrate", "helpdesk", "0001", verbosity=0)
    assert not Area.objects.exists()
    call_command("migrate", "helpdesk", "zero", verbosity=0)
    call_command("migrate", verbosity=0)
    assert Area.objects.count() == 4
