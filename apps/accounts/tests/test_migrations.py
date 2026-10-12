import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command


# serialized_rollback: restaura los datos de las migraciones (grupos, catálogos)
# que el vaciado de la prueba transaccional anterior haya borrado.
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_accounts_migrations_are_reversible():
    call_command("migrate", "accounts", "0001", verbosity=0)
    assert not Group.objects.filter(name__in=["Usuario", "Administrador"]).exists()

    call_command("migrate", "accounts", "zero", verbosity=0)
    call_command("migrate", verbosity=0)

    assert (
        Group.objects.filter(name__in=["Usuario", "Agente", "Supervisor", "Administrador"]).count()
        == 4
    )
