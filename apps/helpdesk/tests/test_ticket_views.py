"""Vistas web de BE-T03: CONTRACT-004 (crear) y CONTRACT-005 (descargar adjunto)."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.helpdesk.models import Category, Subcategory, Ticket
from apps.helpdesk.tickets import TicketService

from .factories import PDF, upload

pytestmark = pytest.mark.django_db

CREATE_URL = reverse("helpdesk:ticket_create")


def _post(client, **extra):
    data = {"subject": "Pago no reflejado", "description": "Pagué ayer y sigue la deuda."}
    data.update(extra)
    return client.post(CREATE_URL, data)


# --- Crear ticket (CONTRACT-004) --------------------------------------------


def test_create_requires_login(client):
    response = client.get(CREATE_URL)
    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


def test_create_form_context(client, make_user):
    client.force_login(make_user())
    response = client.get(CREATE_URL)
    assert response.status_code == 200
    form = response.context["form"]
    assert list(form.fields) == ["subject", "description", "category", "subcategory", "attachment"]
    tree = response.context["category_tree"]
    academic = next(c for c in tree if c["name"] == "Académico")
    assert {"id", "name", "subcategories"} == set(academic)
    assert "Calificaciones" in [s["name"] for s in academic["subcategories"]]


def test_create_ticket(client, make_user):
    user = make_user()
    client.force_login(user)
    category = Category.objects.get(code="FINANCIAL")
    sub = Subcategory.objects.get(category=category, code="PAYMENTS")
    response = _post(client, category=category.pk, subcategory=sub.pk)

    ticket = Ticket.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("helpdesk:ticket_detail", args=[ticket.ticket_code])  # CR-005
    assert ticket.user == user
    assert ticket.subcategory == sub
    messages = [str(m) for m in response.wsgi_request._messages]
    assert messages == [f"Solicitud {ticket.ticket_code} creada."]


def test_create_ticket_with_attachment(client, make_user):
    client.force_login(make_user())
    response = client.post(
        CREATE_URL,
        {"subject": "Adjunto", "description": "Va el comprobante", "attachment": upload()},
    )
    assert response.status_code == 302
    assert Ticket.objects.get().attachments.count() == 1


def test_client_cannot_set_backend_fields(client, make_user):
    client.force_login(make_user())
    _post(client, status="CLOSED", priority="CRITICAL", ticket_code="HD-0000-000001", user=999)
    ticket = Ticket.objects.get()
    assert ticket.status == Ticket.Status.NEW
    assert ticket.priority == Ticket.Priority.MEDIUM
    assert ticket.ticket_code != "HD-0000-000001"


@pytest.mark.parametrize(
    "extra,field",
    [
        ({"subject": ""}, "subject"),
        ({"description": ""}, "description"),
        ({"category": 999999}, "category"),
    ],
)
def test_invalid_form_shows_errors(client, make_user, extra, field):
    client.force_login(make_user())
    response = _post(client, **extra)
    assert response.status_code == 200
    assert field in response.context["form"].errors
    assert not Ticket.objects.exists()


def test_mismatched_subcategory_rejected(client, make_user):
    client.force_login(make_user())
    response = _post(
        client,
        category=Category.objects.get(code="FINANCIAL").pk,
        subcategory=Subcategory.objects.get(category__code="ACADEMIC", code="GRADES").pk,
    )
    assert "subcategory" in response.context["form"].errors
    assert not Ticket.objects.exists()


def test_inactive_category_not_offered(client, make_user):
    category = Category.objects.get(code="GENERAL")
    category.is_active = False
    category.save()
    client.force_login(make_user())
    response = _post(client, category=category.pk)
    assert "category" in response.context["form"].errors
    assert all(c["name"] != "General" for c in response.context["category_tree"])


def test_invalid_attachment_rejected(client, make_user):
    client.force_login(make_user())
    response = client.post(
        CREATE_URL,
        {"subject": "x", "description": "y", "attachment": upload("x.exe", b"MZ")},
    )
    assert "attachment" in response.context["form"].errors
    assert not Ticket.objects.exists()


def test_create_requires_csrf(make_user):
    client = Client(enforce_csrf_checks=True)
    client.force_login(make_user())
    assert _post(client).status_code == 403


# --- Descargar adjunto (CONTRACT-005) -----------------------------------------


@pytest.fixture
def ticket_with_file(make_user):
    owner = make_user("duenio", role="Usuario")
    ticket = TicketService.create(
        user=owner, subject="Adjunto", description="d", attachment=upload("Recibo.pdf")
    )
    return ticket, ticket.attachments.get()


def _download_url(ticket, item):
    return reverse("helpdesk:attachment_download", args=[ticket.ticket_code, item.pk])


def test_owner_downloads_attachment(client, ticket_with_file):
    ticket, item = ticket_with_file
    client.force_login(ticket.user)
    response = client.get(_download_url(ticket, item))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert 'attachment; filename="Recibo.pdf"' in response["Content-Disposition"]
    assert b"".join(response.streaming_content) == PDF


def test_other_user_cannot_download(client, make_user, ticket_with_file):
    # 404 y no 403: no se revela que el ticket existe (BE-T04).
    ticket, item = ticket_with_file
    client.force_login(make_user("otro", role="Usuario"))
    assert client.get(_download_url(ticket, item)).status_code == 404


@pytest.mark.parametrize("role", ["Agente", "Supervisor", "Administrador"])
def test_staff_can_download(client, make_user, ticket_with_file, role):
    ticket, item = ticket_with_file
    client.force_login(make_user("staff", role=role))
    assert client.get(_download_url(ticket, item)).status_code == 200


def test_attachment_must_belong_to_ticket(client, make_user, ticket_with_file):
    ticket, item = ticket_with_file
    other = TicketService.create(user=ticket.user, subject="Otro", description="d")
    client.force_login(ticket.user)
    url = reverse("helpdesk:attachment_download", args=[other.ticket_code, item.pk])
    assert client.get(url).status_code == 404


def test_missing_file_returns_404(client, ticket_with_file):
    ticket, item = ticket_with_file
    item.file.delete(save=False)
    client.force_login(ticket.user)
    assert client.get(_download_url(ticket, item)).status_code == 404


def test_download_requires_login(client, ticket_with_file):
    ticket, item = ticket_with_file
    assert client.get(_download_url(ticket, item)).status_code == 302


def test_service_validation_error_is_shown_in_form(client, make_user, monkeypatch):
    # Caso límite: la categoría se desactiva entre la validación del formulario y el guardado.
    from django.core.exceptions import ValidationError

    def reject(**kwargs):
        raise ValidationError({"category": "La categoría no está disponible."})

    monkeypatch.setattr(TicketService, "create", staticmethod(reject))
    client.force_login(make_user())
    response = _post(client, category=Category.objects.get(code="GENERAL").pk)
    assert response.status_code == 200
    assert response.context["form"].errors["category"] == ["La categoría no está disponible."]
