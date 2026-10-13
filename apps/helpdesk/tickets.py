"""TicketService (SPEC §33). BE-T03 implementa la creación y los adjuntos."""

import os

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from . import audit
from .attachments import validate_upload
from .audit import Action
from .models import Attachment, Ticket

TICKET_CODE_SEQUENCE = "helpdesk_ticket_code_seq"


def next_ticket_code():
    """Código `HD-AAAA-NNNNNN` a partir de una secuencia PostgreSQL.

    `nextval` es atómico entre transacciones concurrentes, por lo que dos
    tickets nunca reciben el mismo número (SPEC §26, criterio de BE-T03).
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(%s)", [TICKET_CODE_SEQUENCE])
        (number,) = cursor.fetchone()
    return f"HD-{timezone.localdate():%Y}-{number:06d}"


class TicketService:
    @staticmethod
    @transaction.atomic
    def create(
        *,
        user,
        subject,
        description,
        channel=Ticket.Channel.WEB,
        category=None,
        subcategory=None,
        attachment=None,
    ):
        """Crea un ticket en estado NEW y registra la auditoría inicial.

        El código, el estado, la prioridad y el área los decide el backend;
        el área inicial es la de la categoría (BE-T09 añadirá routing).
        """
        if attachment is not None:
            validate_upload(attachment)
        if subcategory is not None and category is None:
            category = subcategory.category
        if category is not None and not category.is_active:
            raise ValidationError({"category": "La categoría no está disponible."})
        if subcategory is not None and not subcategory.is_active:
            raise ValidationError({"subcategory": "La subcategoría no está disponible."})

        ticket = Ticket(
            ticket_code=next_ticket_code(),
            user=user,
            channel=channel,
            category=category,
            subcategory=subcategory,
            subject=subject.strip(),
            description=description.strip(),
            assigned_area=category.default_area if category else None,
            classification_source=Ticket.ClassificationSource.USER if category else "",
        )
        ticket.full_clean()
        ticket.save()
        audit.record(
            Action.CREATE,
            ticket,
            actor=user,
            new=audit.snapshot(ticket, Ticket.audit_fields),
        )

        if attachment is not None:
            TicketService.add_attachment(ticket, attachment, uploaded_by=user)
        return ticket

    @staticmethod
    @transaction.atomic
    def add_attachment(ticket, uploaded_file, *, uploaded_by):
        content_type = validate_upload(uploaded_file)
        item = Attachment(
            ticket=ticket,
            uploaded_by=uploaded_by,
            original_name=os.path.basename(uploaded_file.name)[:255],
            content_type=content_type,
            size_bytes=uploaded_file.size,
        )
        item.file.save(uploaded_file.name, uploaded_file, save=False)
        # Si el registro no se guarda, borrar el archivo para no dejarlo huérfano.
        # (Un rollback posterior de la transacción externa puede dejar huérfanos;
        # su limpieza periódica queda como pendiente en progress.md.)
        try:
            item.save()
        except Exception:
            item.file.delete(save=False)
            raise
        audit.record(
            Action.CREATE,
            item,
            actor=uploaded_by,
            new=audit.snapshot(item, Attachment.audit_fields),
            metadata={"ticket_code": ticket.ticket_code},
        )
        return item
