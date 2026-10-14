"""Protección de contraseñas y accesos (ADR-071..075)."""

import time

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.db import DatabaseError
from django.urls import reverse

from apps.accounts import checks, passwords
from apps.accounts.middleware import LAST_ACTIVITY_KEY
from apps.accounts.roles import Role
from apps.helpdesk.models import AuditLog
from conftest import PASSWORD

pytestmark = pytest.mark.django_db
LOGIN = reverse("accounts:login")
CHANGE = reverse("accounts:password_change")


def login(client, username, password=PASSWORD):
    return client.post(LOGIN, {"username": username, "password": password})


def access_log(action):
    return AuditLog.objects.filter(entity_type="accounts.user", action=action)


# --- Política de contraseñas y hash ---------------------------------------------------------


@pytest.mark.parametrize("weak", ["Ab1", "solo-letras-largas", "1234567890123", "password123"])
def test_weak_passwords_rejected(weak):
    with pytest.raises(ValidationError):
        validate_password(weak)


def test_strong_password_accepted():
    validate_password("Cielo-Rojo-2026")


def test_argon2_is_primary_hasher_with_pbkdf2_fallback():
    from config.settings import base

    assert base.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")
    assert any(h.endswith("PBKDF2PasswordHasher") for h in base.PASSWORD_HASHERS)


def test_generated_passwords_are_random_and_valid():
    values = {passwords.generate() for _ in range(20)}
    assert len(values) == 20
    for value in values:
        validate_password(value)


def test_generate_retries_until_letters_and_digits(monkeypatch):
    picks = iter("a" * 14 + "a1" * 7)
    monkeypatch.setattr(passwords.secrets, "choice", lambda _alphabet: next(picks))
    assert passwords.generate() == "a1" * 7


# --- Sesión -------------------------------------------------------------------------------


def test_idle_session_is_closed(client, make_user, settings):
    settings.SESSION_IDLE_TIMEOUT = 60
    make_user("ana")
    login(client, "ana")
    assert client.get(reverse("accounts:home")).status_code == 200
    session = client.session
    session[LAST_ACTIVITY_KEY] = int(time.time()) - 120
    session.save()
    response = client.get(reverse("accounts:home"))
    assert response.status_code == 302
    assert response.url.startswith(LOGIN)
    assert "_auth_user_id" not in client.session
    assert access_log("LOGOUT").exists()


def test_activity_keeps_session_alive(client, make_user, settings):
    settings.SESSION_IDLE_TIMEOUT = 600
    make_user("ana")
    login(client, "ana")
    client.get(reverse("accounts:home"))
    session = client.session
    session[LAST_ACTIVITY_KEY] = int(time.time()) - 300
    session.save()
    assert client.get(reverse("accounts:home")).status_code == 200
    assert client.session[LAST_ACTIVITY_KEY] >= int(time.time()) - 5


def test_idle_timeout_can_be_disabled(client, make_user, settings):
    settings.SESSION_IDLE_TIMEOUT = 0
    make_user("ana")
    login(client, "ana")
    assert client.get(reverse("accounts:home")).status_code == 200
    assert LAST_ACTIVITY_KEY not in client.session


def test_session_settings_hardened(settings):
    assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is True
    assert settings.SESSION_COOKIE_HTTPONLY and settings.CSRF_COOKIE_HTTPONLY
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"


# --- Cambio de contraseña -------------------------------------------------------------------


def test_forced_password_change(client, make_user):
    make_user("ana", must_change_password=True)
    login(client, "ana")
    response = client.get(reverse("accounts:home"))
    assert response.status_code == 302 and response.url == CHANGE
    page = client.get(CHANGE)
    assert page.status_code == 200 and page.context["forced"] is True
    assert client.get("/static/css/app.css").status_code in (200, 404)  # sin redirección
    response = client.post(
        CHANGE,
        {
            "old_password": PASSWORD,
            "new_password1": "Nueva-Clave-77",
            "new_password2": "Nueva-Clave-77",
        },
    )
    assert response.status_code == 302 and response.url == reverse("accounts:role_redirect")
    user = get_user_model().objects.get(username="ana")
    assert user.must_change_password is False and user.check_password("Nueva-Clave-77")
    assert client.get(reverse("accounts:home")).status_code == 200  # sesión conservada
    assert access_log("PASSWORD_CHANGE").filter(actor=user).exists()


def test_forced_user_can_logout(client, make_user):
    make_user("ana", must_change_password=True)
    login(client, "ana")
    assert client.post(reverse("accounts:logout")).url == reverse("accounts:login")
    assert "_auth_user_id" not in client.session


def test_password_change_rejects_weak_and_wrong_old(client, make_user):
    make_user("ana")
    login(client, "ana")
    assert client.get(CHANGE).context["forced"] is False
    weak = client.post(
        CHANGE, {"old_password": PASSWORD, "new_password1": "abc", "new_password2": "abc"}
    )
    wrong = client.post(
        CHANGE,
        {
            "old_password": "mala",
            "new_password1": "Nueva-Clave-77",
            "new_password2": "Nueva-Clave-77",
        },
    )
    assert weak.status_code == wrong.status_code == 200
    assert get_user_model().objects.get(username="ana").check_password(PASSWORD)


def test_password_change_requires_login(client):
    assert client.get(CHANGE).url.startswith(LOGIN)


# --- Auditoría de accesos -------------------------------------------------------------------


def test_login_logout_and_failures_are_audited(client, make_user):
    ana = make_user("ana")
    login(client, "ana", "mala")
    failed = access_log("LOGIN_FAILED").get()
    assert failed.actor is None and failed.metadata_json["username"] == "ana"
    assert failed.metadata_json["ip"] == "127.0.0.1"
    assert "mala" not in str(failed.metadata_json)  # nunca la contraseña
    login(client, "ana")
    assert access_log("LOGIN").get().actor == ana
    client.post(reverse("accounts:logout"))
    assert access_log("LOGOUT").get().entity_id == str(ana.pk)


def test_lockout_is_audited(client, make_user, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "login_user": (1, 60)}
    make_user("ana")
    login(client, "ana", "mala")
    assert login(client, "ana").status_code == 429
    assert access_log("LOGIN_LOCKED").get().metadata_json["username"] == "ana"


def test_anonymous_logout_is_not_audited(client):
    client.post(reverse("accounts:logout"))
    assert not access_log("LOGOUT").exists()


# --- Admin de Django -----------------------------------------------------------------------


def test_admin_login_uses_protected_portal_login(client):
    response = client.get(reverse("admin:login") + "?next=/admin/helpdesk/")
    assert response.status_code == 302
    assert response.url.startswith(LOGIN) and "next=/admin/helpdesk/" in response.url
    assert client.get(reverse("admin:login")).url.endswith("next=" + reverse("admin:index"))


def test_admin_login_forbidden_for_non_staff(client, make_user):
    make_user("ana")
    login(client, "ana")
    assert client.get(reverse("admin:login")).status_code == 403


def _staff_admin(make_user):
    return make_user("jefe", role=Role.ADMINISTRADOR, is_staff=True, is_superuser=True)


def test_admin_created_user_must_change_password(client, make_user):
    _staff_admin(make_user)
    login(client, "jefe")
    response = client.post(
        reverse("admin:accounts_user_add"),
        {
            "username": "nuevo",
            "password1": "Temporal-2026x",
            "password2": "Temporal-2026x",
            "usable_password": "true",
        },
    )
    assert response.status_code == 302
    assert get_user_model().objects.get(username="nuevo").must_change_password is True


def test_admin_password_reset_of_other_user_forces_change(client, make_user):
    jefe = _staff_admin(make_user)
    ana = make_user("ana")
    login(client, "jefe")
    url = reverse("admin:auth_user_password_change", args=[ana.pk])
    data = {"password1": "Temporal-2026x", "password2": "Temporal-2026x"}
    assert client.post(url, data).status_code == 302
    ana.refresh_from_db()
    assert ana.must_change_password is True
    own = reverse("admin:auth_user_password_change", args=[jefe.pk])
    client.post(own, data)
    jefe.refresh_from_db()
    assert jefe.must_change_password is False


# --- Comandos -----------------------------------------------------------------------------


def test_reset_password_command(make_user, capsys):
    make_user("ana")
    call_command("reset_password", "ana")
    temporary = capsys.readouterr().out.split("Contraseña temporal de ana: ")[1].split()[0]
    ana = get_user_model().objects.get(username="ana")
    assert ana.check_password(temporary) and ana.must_change_password
    entry = access_log("PASSWORD_RESET").get()
    assert entry.actor is None and entry.actor_type == "SYSTEM"
    with pytest.raises(CommandError):
        call_command("reset_password", "nadie")


def _credentials(out):
    lines = [line.split() for line in out.splitlines() if "→" in line]
    return {parts[0]: parts[1] for parts in lines}


def test_seed_demo_random_passwords_and_rotate(settings, capsys):
    settings.DEBUG = True
    call_command("seed_demo")
    first = _credentials(capsys.readouterr().out)
    assert set(first) == {"usuario", "agente_ti", "agente_fin", "supervisor", "admin"}
    assert len(set(first.values())) == 5
    User = get_user_model()
    assert all(User.objects.get(username=u).check_password(p) for u, p in first.items())
    call_command("seed_demo", rotate=True)
    second = _credentials(capsys.readouterr().out)
    assert set(second) == set(first) and all(second[u] != first[u] for u in first)
    assert User.objects.get(username="admin").check_password(second["admin"])


def test_seed_demo_fixed_password_is_validated(settings, capsys):
    settings.DEBUG = True
    with pytest.raises(CommandError):
        call_command("seed_demo", password="corta")
    call_command("seed_demo", password="Prueba-E2E-2026")
    assert get_user_model().objects.get(username="supervisor").check_password("Prueba-E2E-2026")
    call_command("seed_demo")  # ya existe y sin --rotate: no cambia nada
    assert "--rotate" in capsys.readouterr().out


# --- Checks de despliegue -------------------------------------------------------------------


def test_check_flags_public_demo_password(make_user):
    assert checks.check_public_demo_password(None) == []
    make_user("admin", password=passwords.LEGACY_DEMO_PASSWORD)
    make_user("ana", password=passwords.LEGACY_DEMO_PASSWORD)  # no es usuario demo
    [warning] = checks.check_public_demo_password(None)
    assert warning.id == "accounts.W001" and "admin" in warning.msg and "ana" not in warning.msg


def test_check_tolerates_missing_tables(monkeypatch):
    def broken(*args, **kwargs):
        raise DatabaseError

    monkeypatch.setattr(get_user_model().objects, "filter", broken)
    assert checks.check_public_demo_password(None) == []


def test_check_admin_url(settings):
    settings.ADMIN_URL = "admin/"
    assert checks.check_admin_url(None)[0].id == "accounts.W002"
    settings.ADMIN_URL = "gestion-x7/"
    assert checks.check_admin_url(None) == []
