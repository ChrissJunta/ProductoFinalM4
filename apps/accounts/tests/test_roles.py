import pytest
from django.contrib.auth.models import AnonymousUser, Group

from apps.accounts.roles import ROLE_PRIORITY, Role, get_role, has_role

pytestmark = pytest.mark.django_db


def test_role_groups_created_by_migration():
    names = set(Group.objects.values_list("name", flat=True))
    assert set(ROLE_PRIORITY) <= names


@pytest.mark.parametrize("role", [Role.USUARIO, Role.AGENTE, Role.SUPERVISOR, Role.ADMINISTRADOR])
def test_get_role_for_each_group(make_user, role):
    assert get_role(make_user(role=role)) == role


def test_highest_role_wins(make_user):
    user = make_user(role=Role.AGENTE)
    user.groups.add(Group.objects.get(name=Role.SUPERVISOR))
    assert get_role(user) == Role.SUPERVISOR


def test_user_without_group_gets_least_privilege(make_user):
    assert get_role(make_user()) == Role.USUARIO


def test_superuser_is_administrator(django_user_model):
    admin = django_user_model.objects.create_superuser("root", "root@example.com", "x")
    assert get_role(admin) == Role.ADMINISTRADOR


def test_anonymous_has_no_role():
    assert get_role(AnonymousUser()) is None
    assert has_role(AnonymousUser(), Role.USUARIO) is False


def test_has_role(make_user):
    agent = make_user(role=Role.AGENTE)
    assert has_role(agent, Role.AGENTE, Role.SUPERVISOR)
    assert not has_role(agent, Role.ADMINISTRADOR)
