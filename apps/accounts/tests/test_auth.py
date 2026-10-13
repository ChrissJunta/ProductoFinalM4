import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.roles import Role
from apps.accounts.views import ROLE_HOME_URLS
from conftest import PASSWORD

pytestmark = pytest.mark.django_db

LOGIN_URL = reverse("accounts:login")


def _login(client, username, password=PASSWORD, **extra):
    return client.post(LOGIN_URL, {"username": username, "password": password, **extra})


def test_login_page_renders(client):
    response = client.get(LOGIN_URL)
    assert response.status_code == 200
    assert "form" in response.context


def test_login_with_username(client, make_user):
    make_user("ana")
    response = _login(client, "ana")
    assert response.status_code == 302
    assert response.url == reverse("accounts:role_redirect")


def test_login_with_email_case_insensitive(client, make_user):
    make_user("ana", email="ana@example.com")
    response = _login(client, "ANA@example.com")
    assert response.status_code == 302


def test_login_with_ambiguous_email_is_rejected(client, make_user):
    make_user("a", email="compartido@example.com")
    make_user("b", email="compartido@example.com")
    response = _login(client, "compartido@example.com")
    assert response.status_code == 200
    assert response.context["form"].non_field_errors()


@pytest.mark.parametrize("username,password", [("ana", "incorrecta"), ("noexiste", PASSWORD)])
def test_invalid_credentials_return_same_generic_error(client, make_user, username, password):
    make_user("ana")
    response = _login(client, username, password)
    assert response.status_code == 200
    errors = response.context["form"].non_field_errors()
    assert len(errors) == 1
    assert "_auth_user_id" not in client.session


def test_inactive_user_cannot_login(client, make_user):
    make_user("ana", is_active=False)
    response = _login(client, "ana")
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_login_requires_csrf(make_user):
    make_user("ana")
    client = Client(enforce_csrf_checks=True)
    response = _login(client, "ana")
    assert response.status_code == 403


def test_login_respects_safe_next(client, make_user):
    make_user("ana")
    response = _login(client, "ana", next="/inicio/")
    assert response.url == "/inicio/"


def test_login_ignores_external_next(client, make_user):
    make_user("ana")
    response = _login(client, "ana", next="https://malicioso.example.com/")
    assert response.url == reverse("accounts:role_redirect")


def test_authenticated_user_skips_login_page(client, make_user):
    client.force_login(make_user("ana"))
    response = client.get(LOGIN_URL)
    assert response.status_code == 302


@pytest.mark.parametrize("role", [Role.USUARIO, Role.AGENTE, Role.SUPERVISOR, Role.ADMINISTRADOR])
def test_role_redirect(client, make_user, role):
    client.force_login(make_user(role=role))
    response = client.get(reverse("accounts:role_redirect"))
    assert response.status_code == 302
    assert response.url == reverse(ROLE_HOME_URLS[role])


def test_role_redirect_requires_login(client):
    response = client.get(reverse("accounts:role_redirect"))
    assert response.status_code == 302
    assert response.url.startswith(LOGIN_URL)


def test_home_exposes_user_role(client, make_user):
    client.force_login(make_user(role=Role.AGENTE))
    response = client.get(reverse("accounts:home"))
    assert response.status_code == 200
    assert response.context["user_role"] == Role.AGENTE


def test_logout_requires_post(client, make_user):
    client.force_login(make_user())
    assert client.get(reverse("accounts:logout")).status_code == 405


def test_logout(client, make_user):
    client.force_login(make_user())
    response = client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    assert response.url == LOGIN_URL
    assert "_auth_user_id" not in client.session
