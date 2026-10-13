import re
import threading

import pytest
from django.core.exceptions import ValidationError
from django.db import connection

from apps.helpdesk import catalogs
from apps.helpdesk.audit import Action
from apps.helpdesk.models import Area, Attachment, AuditLog, Category, Subcategory, Ticket
from apps.helpdesk.tickets import TicketService, next_ticket_code

from .factories import upload

pytestmark = pytest.mark.django_db

CODE_RE = re.compile(r"^HD-\d{4}-\d{6}$")


def _create(user, **kwargs):
    data = {"subject": "No veo mi nota", "description": "La nota de Cálculo no aparece."}
    data.update(kwargs)
    return TicketService.create(user=user, **data)


def test_create_minimal_ticket(make_user):
    user = make_user()
    ticket = _create(user)
    assert CODE_RE.match(ticket.ticket_code)
    assert ticket.status == Ticket.Status.NEW
    assert ticket.priority == Ticket.Priority.MEDIUM
    assert ticket.channel == Ticket.Channel.WEB
    assert ticket.version == 1
    assert ticket.category is None
    assert ticket.assigned_area is None
    assert ticket.classification_source == ""
    assert ticket.sla_due_at is not None  # política general MEDIUM (BE-T08)
    assert ticket.first_response_due_at < ticket.sla_due_at


def test_codes_are_sequential_and_unique(make_user):
    user = make_user()
    codes = [_create(user).ticket_code for _ in range(3)]
    numbers = [int(c.rsplit("-", 1)[1]) for c in codes]
    assert numbers == sorted(numbers)
    assert len(set(codes)) == 3


def test_text_is_trimmed(make_user):
    ticket = _create(make_user(), subject="  Asunto  ", description="  Detalle  ")
    assert (ticket.subject, ticket.description) == ("Asunto", "Detalle")


def test_category_sets_initial_area_and_source(make_user):
    category = Category.objects.get(code="FINANCIAL")
    ticket = _create(make_user(), category=category)
    assert ticket.assigned_area == Area.objects.get(code="FINANCE")
    assert ticket.classification_source == Ticket.ClassificationSource.USER


def test_subcategory_alone_infers_category(make_user):
    sub = Subcategory.objects.get(category__code="ACADEMIC", code="GRADES")
    ticket = _create(make_user(), subcategory=sub)
    assert ticket.category == sub.category
    assert ticket.assigned_area.code == "ACADEMIC"


def test_subcategory_must_match_category(make_user):
    with pytest.raises(ValidationError) as exc:
        _create(
            make_user(),
            category=Category.objects.get(code="FINANCIAL"),
            subcategory=Subcategory.objects.get(category__code="ACADEMIC", code="GRADES"),
        )
    assert "subcategory" in exc.value.message_dict
    assert not Ticket.objects.exists()


def test_inactive_category_rejected(make_user):
    admin = make_user("admin", role="Administrador")
    category = catalogs.set_active(Category.objects.get(code="GENERAL"), False, actor=admin)
    with pytest.raises(ValidationError):
        _create(make_user(), category=category)


def test_inactive_subcategory_rejected(make_user):
    admin = make_user("admin", role="Administrador")
    sub = catalogs.set_active(
        Subcategory.objects.get(category__code="GENERAL", code="OTHER"), False, actor=admin
    )
    with pytest.raises(ValidationError):
        _create(make_user(), subcategory=sub)


@pytest.mark.parametrize(
    "field,value", [("subject", ""), ("subject", "x" * 201), ("description", "")]
)
def test_invalid_text_rejected(make_user, field, value):
    with pytest.raises(ValidationError) as exc:
        _create(make_user(), **{field: value})
    assert field in exc.value.message_dict


def test_creation_is_audited(make_user):
    user = make_user()
    ticket = _create(user, category=Category.objects.get(code="TECHNICAL"))
    log = AuditLog.objects.get(entity_type="helpdesk.ticket", entity_id=str(ticket.pk))
    assert log.action == Action.CREATE
    assert log.actor == user
    assert log.new_value_json["ticket_code"] == ticket.ticket_code
    assert log.new_value_json["status"] == "NEW"
    assert log.new_value_json["assigned_area_id"] == Area.objects.get(code="IT").pk


def test_create_with_attachment(make_user):
    user = make_user()
    ticket = _create(user, attachment=upload("Comprobante de pago.pdf"))
    item = ticket.attachments.get()
    assert item.original_name == "Comprobante de pago.pdf"
    assert item.content_type == "application/pdf"
    assert item.uploaded_by == user
    assert item.file.name.startswith("attachments/")
    assert "Comprobante" not in item.file.name  # nombre aleatorio en disco
    assert AuditLog.objects.filter(
        entity_type="helpdesk.attachment", entity_id=str(item.pk), action=Action.CREATE
    ).exists()


def test_invalid_attachment_creates_nothing(make_user):
    before = next_ticket_code()
    with pytest.raises(ValidationError):
        _create(make_user(), attachment=upload("virus.exe", b"MZ\x90\x00"))
    assert not Ticket.objects.exists()
    assert not Attachment.objects.exists()
    # El adjunto se valida antes de consumir un número de ticket.
    after = next_ticket_code()
    assert int(after.rsplit("-", 1)[1]) == int(before.rsplit("-", 1)[1]) + 1


# Prueba transaccional: los hilos usan conexiones propias y deben ver datos confirmados.
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_no_duplicate_codes_under_concurrency(django_user_model):
    user = django_user_model.objects.create_user("concurrente", password="x")
    workers = 12
    barrier = threading.Barrier(workers)
    codes, errors = [], []

    def worker():
        try:
            barrier.wait(timeout=10)
            ticket = TicketService.create(user=user, subject="Concurrente", description="Prueba")
            codes.append(ticket.ticket_code)
        except Exception as exc:  # pragma: no cover - se informa en la aserción
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(codes) == workers
    assert len(set(codes)) == workers
    assert Ticket.objects.count() == workers
