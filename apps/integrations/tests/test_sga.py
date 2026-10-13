"""BE-T19: SGAProvider contra el SGA simulado (mock HTTP real en un hilo local)."""

from datetime import date
from io import StringIO

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command

from apps.integrations.institutional import get_provider, sga_mock
from apps.integrations.institutional.base import ProviderError, StudentNotFound
from apps.integrations.institutional.local import LocalProvider
from apps.integrations.institutional.sga import SGAProvider

pytestmark = pytest.mark.django_db
DAY = date(2026, 10, 14)


@pytest.fixture
def server():
    srv = sga_mock.start(token="secreto")
    yield srv
    srv.shutdown()


@pytest.fixture
def sga(server):
    return SGAProvider(server.url, token="secreto", timeout=1.0, retry_wait=0)


def student(make_user, code, name="ana"):
    return make_user(name, external_id=code)


# --- Mismo contrato que LocalProvider (criterio de aceptación) ----------------------------------


@pytest.mark.parametrize(
    "method,kwargs",
    [
        ("get_schedule", {"date": DAY}),
        ("get_schedule", {"date": date(2026, 10, 18)}),  # domingo: lista vacía
        ("get_grades", {}),
        ("get_grades", {"period": "2026-1"}),
        ("get_debt", {}),
        ("get_enrollment", {}),
        ("get_enrollment", {"period": "2020-1"}),
        ("get_subjects", {}),
    ],
)
def test_same_contract_as_local(make_user, sga, method, kwargs):
    user = student(make_user, "EST-0001")
    assert getattr(sga, method)(user, **kwargs) == getattr(LocalProvider(), method)(user, **kwargs)


def test_schedule_defaults_to_today(make_user, sga, monkeypatch):
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: DAY)
    assert sga.get_schedule(student(make_user, "EST-0001"))[0].day == DAY


def test_student_without_debt(make_user, sga):
    assert sga.get_debt(student(make_user, "EST-0002")).items == ()


# --- Errores 4xx / 5xx / red / formato -------------------------------------------------------


def test_404_and_missing_external_id_are_student_not_found(make_user, sga):
    with pytest.raises(StudentNotFound):
        sga.get_grades(student(make_user, "EST-9999"))
    with pytest.raises(StudentNotFound):
        sga.get_grades(make_user("sin-codigo"))


def test_401_is_not_retried(make_user, server):
    bad = SGAProvider(server.url, token="otro", retry_wait=0)
    with pytest.raises(ProviderError, match="401"):
        bad.get_debt(student(make_user, "EST-0001"))
    assert server.hits == 1


def test_5xx_retried_once_then_error(make_user, sga, server):
    with pytest.raises(ProviderError, match="500"):
        sga.get_debt(student(make_user, "EST-500"))
    assert server.hits == 2


def test_transient_5xx_recovers_on_retry(make_user, sga, server):
    debt = sga.get_debt(student(make_user, "EST-FLAKY"))
    assert debt.total > 0 and server.hits == 2


def test_timeout(make_user, server, monkeypatch):
    monkeypatch.setattr(sga_mock, "SLOW_SECONDS", 0.5)
    slow = SGAProvider(server.url, token="secreto", timeout=0.1, retries=0)
    with pytest.raises(ProviderError, match="no disponible"):
        slow.get_debt(student(make_user, "EST-SLOW"))


def test_unreachable_server(make_user):
    down = SGAProvider("http://127.0.0.1:9", timeout=0.2, retries=0)
    with pytest.raises(ProviderError):
        down.get_grades(student(make_user, "EST-0001"))


@pytest.mark.parametrize("code", ["EST-BADJSON", "EST-BADFORMAT"])
def test_invalid_responses(make_user, sga, code):
    user = student(make_user, code)
    for method in ("get_schedule", "get_grades", "get_debt", "get_enrollment", "get_subjects"):
        with pytest.raises(ProviderError):
            getattr(sga, method)(user)


def test_requires_base_url():
    with pytest.raises(ValueError):
        SGAProvider("")


# --- Selección por configuración y uso desde el agente ---------------------------------------


def test_get_provider_sga(settings, server):
    settings.INSTITUTIONAL_PROVIDER = "sga"
    settings.SGA_BASE_URL = ""
    with pytest.raises(ImproperlyConfigured):
        get_provider()
    settings.SGA_BASE_URL, settings.SGA_TOKEN = server.url, "secreto"
    provider = get_provider()
    assert isinstance(provider, SGAProvider) and provider.token == "secreto"


def test_agent_answers_through_sga(settings, server, make_user):
    from apps.ai.agent import runner

    settings.INSTITUTIONAL_PROVIDER = "sga"
    settings.SGA_BASE_URL, settings.SGA_TOKEN = server.url, "secreto"
    runner.reset()
    user = make_user("ana", role="Usuario", external_id="EST-0001")
    r = runner.run_agent(text="¿Cuánto debo?", user=user)
    assert r.level == "N0" and "USD 390.00" in r.response
    down = make_user("caido", role="Usuario", external_id="EST-500")
    r = runner.run_agent(text="¿Cuánto debo?", user=down)  # SGA caído → ticket (ADR-045)
    assert r.ticket is not None and "No pudimos consultar" in r.response
    runner.reset()


def test_run_sga_mock_command():
    out = StringIO()
    call_command("run_sga_mock", "--port", "0", "--seconds", "0.01", stdout=out)
    assert "SGA simulado en http://127.0.0.1:" in out.getvalue() and "detenido" in out.getvalue()
