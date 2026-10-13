import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

code_validator = RegexValidator(
    regex=r"^[A-Z][A-Z0-9_]*$",
    message="Use mayúsculas, dígitos y guion bajo, empezando por letra (ej. ACADEMIC).",
)


class CatalogModel(models.Model):
    """Base de catálogos: código estable y desactivación lógica (sin borrado)."""

    code = models.CharField("código", max_length=32, validators=[code_validator])
    name = models.CharField("nombre", max_length=120)
    is_active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    # Campos que se guardan en AuditLog al crear/modificar.
    audit_fields = ("code", "name", "is_active")

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Area(CatalogModel):
    code = models.CharField("código", max_length=32, unique=True, validators=[code_validator])
    email = models.EmailField("correo", blank=True)

    audit_fields = ("code", "name", "email", "is_active")

    class Meta(CatalogModel.Meta):
        verbose_name = "área"
        verbose_name_plural = "áreas"


class Category(CatalogModel):
    code = models.CharField("código", max_length=32, unique=True, validators=[code_validator])
    default_area = models.ForeignKey(
        Area,
        verbose_name="área por defecto",
        on_delete=models.PROTECT,
        related_name="categories",
    )

    audit_fields = ("code", "name", "default_area_id", "is_active")

    class Meta(CatalogModel.Meta):
        verbose_name = "categoría"
        verbose_name_plural = "categorías"

    def clean(self):
        if self.is_active and self.default_area_id and not self.default_area.is_active:
            raise ValidationError({"default_area": "El área por defecto está inactiva."})


class Subcategory(CatalogModel):
    category = models.ForeignKey(
        Category,
        verbose_name="categoría",
        on_delete=models.PROTECT,
        related_name="subcategories",
    )

    audit_fields = ("category_id", "code", "name", "is_active")

    class Meta(CatalogModel.Meta):
        verbose_name = "subcategoría"
        verbose_name_plural = "subcategorías"
        ordering = ["category__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "code"], name="helpdesk_subcategory_category_code_unique"
            )
        ]

    def __str__(self):
        return f"{self.category.name} / {self.name}"


class AuditLog(models.Model):
    """Registro inmutable de acciones relevantes (SPEC §26, §32.2)."""

    class ActorType(models.TextChoices):
        USER = "USER", "Usuario"
        SYSTEM = "SYSTEM", "Sistema"
        AI = "AI", "IA"

    actor_type = models.CharField("tipo de actor", max_length=16, choices=ActorType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="actor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    action = models.CharField("acción", max_length=64)
    entity_type = models.CharField("tipo de entidad", max_length=64)
    entity_id = models.CharField("id de entidad", max_length=64)
    previous_value_json = models.JSONField(
        "valor anterior", null=True, blank=True, encoder=DjangoJSONEncoder
    )
    new_value_json = models.JSONField(
        "valor nuevo", null=True, blank=True, encoder=DjangoJSONEncoder
    )
    metadata_json = models.JSONField(
        "metadatos", default=dict, blank=True, encoder=DjangoJSONEncoder
    )
    created_at = models.DateTimeField("fecha", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registros de auditoría"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"], name="helpdesk_audit_entity_idx")
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Los registros de auditoría no se modifican.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los registros de auditoría no se eliminan.")


class Ticket(models.Model):
    """Solicitud con seguimiento (SPEC §26 `Ticket`).

    `intent` se añade con BE-T09 (CR-002). Los plazos SLA los calcula BE-T08.
    """

    class Channel(models.TextChoices):
        WEB = "WEB", "Web"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    class Status(models.TextChoices):
        NEW = "NEW", "Nuevo"
        CLASSIFIED = "CLASSIFIED", "Clasificado"
        ASSIGNED = "ASSIGNED", "Asignado"
        IN_PROGRESS = "IN_PROGRESS", "En proceso"
        WAITING_USER = "WAITING_USER", "Esperando usuario"
        RESOLVED = "RESOLVED", "Resuelto"
        CLOSED = "CLOSED", "Cerrado"
        ESCALATED = "ESCALATED", "Escalado"
        REOPENED = "REOPENED", "Reabierto"
        CANCELLED = "CANCELLED", "Cancelado"

    class Priority(models.TextChoices):
        LOW = "LOW", "Baja"
        MEDIUM = "MEDIUM", "Media"
        HIGH = "HIGH", "Alta"
        CRITICAL = "CRITICAL", "Crítica"

    class ClassificationSource(models.TextChoices):
        USER = "USER", "Usuario"
        RULES = "RULES", "Reglas"
        LLM = "LLM", "LLM"
        HUMAN = "HUMAN", "Humano"

    ticket_code = models.CharField("código", max_length=20, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="solicitante",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    channel = models.CharField("canal", max_length=16, choices=Channel.choices)
    category = models.ForeignKey(
        Category, verbose_name="categoría", null=True, blank=True, on_delete=models.PROTECT
    )
    subcategory = models.ForeignKey(
        Subcategory, verbose_name="subcategoría", null=True, blank=True, on_delete=models.PROTECT
    )
    priority = models.CharField(
        "prioridad", max_length=16, choices=Priority.choices, default=Priority.MEDIUM
    )
    status = models.CharField("estado", max_length=16, choices=Status.choices, default=Status.NEW)
    assigned_area = models.ForeignKey(
        Area, verbose_name="área asignada", null=True, blank=True, on_delete=models.PROTECT
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsable",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_tickets",
    )
    subject = models.CharField("asunto", max_length=200)
    description = models.TextField("descripción", max_length=5000)
    classification_source = models.CharField(
        "origen de clasificación",
        max_length=16,
        choices=ClassificationSource.choices,
        blank=True,
        default="",
    )
    classification_score = models.DecimalField(
        "confianza de clasificación", max_digits=4, decimal_places=3, null=True, blank=True
    )
    version = models.PositiveIntegerField("versión", default=1)
    created_at = models.DateTimeField("creado", auto_now_add=True, db_index=True)
    assigned_at = models.DateTimeField("asignado", null=True, blank=True)
    first_response_at = models.DateTimeField("primera respuesta", null=True, blank=True)
    resolved_at = models.DateTimeField("resuelto", null=True, blank=True)
    closed_at = models.DateTimeField("cerrado", null=True, blank=True)
    first_response_due_at = models.DateTimeField("vence primera respuesta", null=True, blank=True)
    sla_due_at = models.DateTimeField("vence resolución", null=True, blank=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    audit_fields = (
        "ticket_code",
        "user_id",
        "channel",
        "category_id",
        "subcategory_id",
        "priority",
        "status",
        "assigned_area_id",
        "subject",
    )

    class Meta:
        verbose_name = "ticket"
        verbose_name_plural = "tickets"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="helpdesk_ticket_user_idx"),
            models.Index(fields=["status", "assigned_area"], name="helpdesk_ticket_queue_idx"),
        ]

    def __str__(self):
        return self.ticket_code

    def clean(self):
        if self.subcategory_id and self.subcategory.category_id != self.category_id:
            raise ValidationError(
                {"subcategory": "La subcategoría no pertenece a la categoría elegida."}
            )


def attachment_upload_to(instance, filename):
    # Nombre aleatorio: el nombre original solo se guarda como dato, nunca como ruta.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return f"attachments/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{ext}"


class Attachment(models.Model):
    """Adjunto de un ticket (SPEC §26 `Attachment`). Validación en `helpdesk.attachments`."""

    ticket = models.ForeignKey(
        Ticket, verbose_name="ticket", on_delete=models.PROTECT, related_name="attachments"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="subido por",
        on_delete=models.PROTECT,
        related_name="+",
    )
    file = models.FileField("archivo", upload_to=attachment_upload_to, max_length=255)
    original_name = models.CharField("nombre original", max_length=255)
    content_type = models.CharField("tipo MIME", max_length=100)
    size_bytes = models.PositiveIntegerField("tamaño (bytes)")
    created_at = models.DateTimeField("subido", auto_now_add=True)

    audit_fields = ("ticket_id", "original_name", "content_type", "size_bytes")

    class Meta:
        verbose_name = "adjunto"
        verbose_name_plural = "adjuntos"
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.original_name


class TicketStatusHistory(models.Model):
    """Historial de cambios de estado (SPEC §26, §32.2). Lo escribe `helpdesk.workflow`."""

    ticket = models.ForeignKey(
        Ticket, verbose_name="ticket", on_delete=models.PROTECT, related_name="status_history"
    )
    previous_status = models.CharField(
        "estado anterior", max_length=16, choices=Ticket.Status.choices, blank=True, default=""
    )
    new_status = models.CharField("estado nuevo", max_length=16, choices=Ticket.Status.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="actor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Vacío cuando la transición la ejecuta el sistema.",
    )
    reason = models.TextField("motivo", blank=True, default="")
    created_at = models.DateTimeField("fecha", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "cambio de estado"
        verbose_name_plural = "historial de estados"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["ticket", "new_status", "-created_at"], name="helpdesk_hist_entry_idx"
            )
        ]

    def __str__(self):
        return f"{self.ticket_id}: {self.previous_status or '—'} → {self.new_status}"
