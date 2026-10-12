"""Matriz de permisos vertical (rol) y horizontal (propietario)."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.views import View

from apps.accounts.permissions import RoleRequiredMixin, check_owner_or_staff, role_required
from apps.accounts.roles import Role

pytestmark = pytest.mark.django_db

ALL_ROLES = [Role.USUARIO, Role.AGENTE, Role.SUPERVISOR, Role.ADMINISTRADOR]

# Vista protegida → roles que deben tener acceso.
MATRIX = {
    "solo_admin": {Role.ADMINISTRADOR},
    "supervision": {Role.SUPERVISOR, Role.ADMINISTRADOR},
    "atencion": {Role.AGENTE, Role.SUPERVISOR, Role.ADMINISTRADOR},
    "autenticado": set(ALL_ROLES),
}


def _ok(request):
    return HttpResponse("ok")


def _request(user):
    request = RequestFactory().get("/protegida/")
    request.user = user
    return request


@pytest.mark.parametrize("view_name", MATRIX)
@pytest.mark.parametrize("role", ALL_ROLES)
def test_role_required_matrix(make_user, view_name, role):
    view = role_required(*MATRIX[view_name])(_ok)
    request = _request(make_user(role=role))
    if role in MATRIX[view_name]:
        assert view(request).status_code == 200
    else:
        with pytest.raises(PermissionDenied):
            view(request)


def test_role_required_redirects_anonymous_to_login():
    view = role_required(Role.USUARIO)(_ok)
    response = view(_request(AnonymousUser()))
    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/?next=/protegida/")


class SupervisorView(RoleRequiredMixin, View):
    allowed_roles = (Role.SUPERVISOR, Role.ADMINISTRADOR)

    def get(self, request):
        return HttpResponse("ok")


@pytest.mark.parametrize("role", ALL_ROLES)
def test_role_required_mixin(make_user, role):
    request = _request(make_user(role=role))
    if role in SupervisorView.allowed_roles:
        assert SupervisorView.as_view()(request).status_code == 200
    else:
        with pytest.raises(PermissionDenied):
            SupervisorView.as_view()(request)


def test_role_required_mixin_redirects_anonymous():
    response = SupervisorView.as_view()(_request(AnonymousUser()))
    assert response.status_code == 302


def test_owner_can_access_own_resource(make_user):
    owner = make_user("duenio", role=Role.USUARIO)
    check_owner_or_staff(owner, owner.pk)


def test_user_cannot_access_other_users_resource(make_user):
    owner = make_user("duenio", role=Role.USUARIO)
    other = make_user("otro", role=Role.USUARIO)
    with pytest.raises(PermissionDenied):
        check_owner_or_staff(other, owner.pk)


@pytest.mark.parametrize("role", [Role.AGENTE, Role.SUPERVISOR, Role.ADMINISTRADOR])
def test_staff_roles_pass_horizontal_check(make_user, role):
    owner = make_user("duenio", role=Role.USUARIO)
    check_owner_or_staff(make_user("staff", role=role), owner.pk)


def test_anonymous_fails_horizontal_check(make_user):
    owner = make_user("duenio")
    with pytest.raises(PermissionDenied):
        check_owner_or_staff(AnonymousUser(), owner.pk)
