"""BE-T20 (seguridad): límite de intentos y configuración de despliegue (SPEC §48)."""

import os
import subprocess
import sys

import pytest
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts import ratelimit
from conftest import PASSWORD

pytestmark = pytest.mark.django_db
LOGIN = "accounts:login"


def login(client, username, password, **extra):
    return client.post(reverse(LOGIN), {"username": username, "password": password}, **extra)


def test_user_locked_after_failed_attempts(client, make_user, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "login_user": (3, 60)}
    make_user("ana")
    for _ in range(3):
        assert login(client, "ana", "mala").status_code == 200
    blocked = login(client, "ana", PASSWORD)  # incluso con la clave correcta
    assert blocked.status_code == 429
    assert "Demasiados intentos" in str(blocked.context["form"].non_field_errors())
    assert "_auth_user_id" not in client.session
    assert login(client, "ANA", PASSWORD).status_code == 429  # sin distinguir mayúsculas


def test_success_resets_user_counter(client, make_user, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "login_user": (3, 60)}
    make_user("ana")
    login(client, "ana", "mala")
    login(client, "ana", "mala")
    assert login(client, "ana", PASSWORD).status_code == 302
    client.logout()
    login(client, "ana", "mala")
    login(client, "ana", "mala")
    assert login(client, "ana", PASSWORD).status_code == 302


def test_ip_limit_across_usernames(client, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "login_ip": (2, 60)}
    login(client, "a", "x")
    login(client, "b", "x")
    assert login(client, "c", "x").status_code == 429


def test_forwarded_for_only_with_trusted_proxy(settings):
    rf = RequestFactory()
    req = rf.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 1.2.3.4")
    settings.TRUSTED_PROXY_COUNT = 0
    assert ratelimit.client_ip(req) == "10.0.0.1"  # cabecera falsificable ignorada
    settings.TRUSTED_PROXY_COUNT = 1
    assert ratelimit.client_ip(req) == "1.2.3.4"
    settings.TRUSTED_PROXY_COUNT = 3
    assert ratelimit.client_ip(req) == "10.0.0.1"


def test_hit_survives_expired_key(settings, monkeypatch):
    from django.core.cache import cache

    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "assistant": (1, 60)}
    monkeypatch.setattr(cache, "add", lambda *a, **k: False)
    monkeypatch.setattr(cache, "incr", lambda *a, **k: (_ for _ in ()).throw(ValueError()))
    assert ratelimit.hit("assistant", 1) is False


def test_assistant_rate_limited(client, make_user, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "assistant": (2, 60)}
    client.force_login(make_user("ana", role="Usuario"))
    url = reverse("automation:assistant")
    assert client.post(url, {"message": "hola"}).status_code == 302
    assert client.post(url, {"message": "hola"}).status_code == 302
    r = client.post(url, {"message": "hola"})
    assert r.status_code == 429 and r.context["form"].non_field_errors()
    assert client.get(url).status_code == 200  # leer no consume el límite


def test_deploy_check_is_clean_with_production_settings():
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.base",
        "DJANGO_SECRET_KEY": "x" * 60 + "-produccion-ficticia-solo-para-check",
        "DJANGO_DEBUG": "False",
        "DJANGO_ALLOWED_HOSTS": "mesa.example.edu",
        "DJANGO_SECURE_SSL_REDIRECT": "True",
        "DJANGO_HSTS_SECONDS": "31536000",
        "DJANGO_SECURE_COOKIES": "True",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr
