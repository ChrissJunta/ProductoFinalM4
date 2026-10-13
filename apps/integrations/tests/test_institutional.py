"""BE-T15: contrato InstitutionalDataProvider, LocalProvider y servicio de consulta."""

from datetime import date, time
from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.integrations.institutional import get_provider
from apps.integrations.institutional.base import (
    InstitutionalDataProvider,
    ProviderError,
    StudentNotFound,
)
from apps.integrations.institutional.local import LocalProvider
from apps.integrations.institutional.service import InstitutionalQueryService

pytestmark = pytest.mark.django_db

WEDNESDAY = date(2026, 10, 14)
SUNDAY = date(2026, 10, 18)


@pytest.fixture
def student(make_user):
    return make_user("ana", external_id="EST-0001")


@pytest.fixture
def provider():
    return LocalProvider()


def test_get_provider_by_setting(settings):
    assert isinstance(get_provider(), LocalProvider)
    settings.INSTITUTIONAL_PROVIDER = "sga"
    with pytest.raises(ImproperlyConfigured):
        get_provider()
    settings.INSTITUTIONAL_PROVIDER = "otro"
    with pytest.raises(ImproperlyConfigured):
        get_provider()


def test_contract_is_abstract():
    with pytest.raises(TypeError):
        InstitutionalDataProvider()


def test_schedule_for_a_given_day(student, provider):
    entries = provider.get_schedule(student, date=WEDNESDAY)
    assert [(e.start, e.subject) for e in entries] == [
        (time(7), "Cálculo I"),
        (time(11), "Comunicación Oral y Escrita"),
    ]
    assert all(e.day == WEDNESDAY for e in entries)
    assert provider.get_schedule(student, date=SUNDAY) == []


def test_schedule_defaults_to_today(student, provider, monkeypatch):
    monkeypatch.setattr(
        "apps.integrations.institutional.local.timezone.localdate", lambda: WEDNESDAY
    )
    assert len(provider.get_schedule(student)) == 2


def test_grades_current_and_previous_period(student, provider):
    grades = provider.get_grades(student)
    assert {g.subject: g.value for g in grades}["Programación I"] == Decimal("8.50")
    assert {g.period for g in grades} == {"2026-2"}
    assert [g.status for g in provider.get_grades(student, period="2026-1")] == ["Aprobado"] * 2
    assert provider.get_grades(student, period="1999-1") == []


def test_debt_summary(student, provider, make_user):
    debt = provider.get_debt(student)
    assert (debt.total, debt.currency, len(debt.items)) == (Decimal("390.00"), "USD", 2)
    assert debt.items[0].due_date > date.today()
    clean = provider.get_debt(make_user("eva", external_id="EST-0002"))
    assert (clean.total, clean.items) == (Decimal("0"), ())


def test_enrollment_and_subjects(student, provider):
    assert provider.get_enrollment(student).status == "Matriculado"
    assert provider.get_enrollment(student, period="2020-1").status == "Sin matrícula"
    subjects = provider.get_subjects(student)
    assert [s.code for s in subjects][:2] == ["MAT-101", "PRG-101"]
    assert sum(s.credits for s in subjects) == 13


def test_unknown_student(make_user, provider):
    for user in (make_user("sin"), make_user("otro", external_id="EST-9999")):
        with pytest.raises(StudentNotFound):
            provider.get_grades(user)


def test_query_service_only_allows_contract_reads(student):
    service = InstitutionalQueryService()
    assert service.query(student, "get_debt").total == Decimal("390.00")
    with pytest.raises(ValueError):
        service.query(student, "get_ticket_status")
    with pytest.raises(ValueError):
        service.query(student, "__init__")


def test_query_service_requires_authenticated_user(student):
    from django.contrib.auth.models import AnonymousUser

    for user in (None, AnonymousUser()):
        with pytest.raises(PermissionError):
            InstitutionalQueryService().query(user, "get_grades")


def test_query_service_wraps_unexpected_failures(student):
    class Broken(LocalProvider):
        def get_grades(self, user, period=None):
            raise TimeoutError("SGA no responde")

    with pytest.raises(ProviderError, match="SGA no responde"):
        InstitutionalQueryService(Broken()).query(student, "get_grades")
    with pytest.raises(StudentNotFound):  # los errores del contrato pasan tal cual
        InstitutionalQueryService().query(type(student).objects.create(username="x"), "get_debt")
