import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from apps.accounts.roles import get_role
from apps.helpdesk.models import Ticket

pytestmark = pytest.mark.django_db


def test_refuses_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_demo")


def test_creates_one_user_per_role_and_tickets_once(settings):
    settings.DEBUG = True
    call_command("seed_demo")
    call_command("seed_demo")  # idempotente
    users = {u.username: get_role(u) for u in get_user_model().objects.all()}
    assert users == {
        "usuario": "Usuario",
        "agente_ti": "Agente",
        "agente_fin": "Agente",
        "supervisor": "Supervisor",
        "admin": "Administrador",
    }
    assert sorted(Ticket.objects.values_list("status", flat=True)) == sorted(
        ["NEW", "IN_PROGRESS", "WAITING_USER", "RESOLVED"]
    )
