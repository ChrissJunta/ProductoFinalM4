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
    # CR-003: agentes que atienden el área (define qué tickets ve cada agente, BE-T04).
    agents = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="agentes",
        blank=True,
        related_name="agent_areas",
        limit_choices_to={"groups__name": "Agente"},
    )

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

    Los plazos SLA los calcula `helpdesk.sla` al crear el ticket.
    """

    class Channel(models.TextChoices):
        WEB = "WEB", "Web"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        TELEGRAM = "TELEGRAM", "Telegram"

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
    # CR-002: intención que originó el ticket (la fija automatización/IA; web la deja vacía).
    intent = models.ForeignKey(
        "automation.Intent",
        verbose_name="intención",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
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
        "intent_id",
        "category_id",
        "subcategory_id",
        "priority",
        "status",
        "assigned_area_id",
        "subject",
        "first_response_due_at",
        "sla_due_at",
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
    message = models.ForeignKey(
        "TicketMessage",
        verbose_name="mensaje",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attachments",
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


class SLAPolicy(models.Model):
    """Plazos por prioridad y, opcionalmente, por categoría (SPEC §26, §34).

    Sin categoría = política general. Se administra como un catálogo
    (escritura auditada vía `helpdesk.catalogs`, sin borrado físico).
    """

    category = models.ForeignKey(
        Category,
        verbose_name="categoría",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text="Vacío = política general para todas las categorías.",
    )
    priority = models.CharField("prioridad", max_length=16, choices=Ticket.Priority.choices)
    first_response_minutes = models.PositiveIntegerField("primera respuesta (min)")
    resolution_minutes = models.PositiveIntegerField("resolución (min)")
    business_hours_only = models.BooleanField("solo horario laboral", default=True)
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    audit_fields = (
        "category_id",
        "priority",
        "first_response_minutes",
        "resolution_minutes",
        "business_hours_only",
        "is_active",
    )

    class Meta:
        verbose_name = "política SLA"
        verbose_name_plural = "políticas SLA"
        ordering = ["category__name", "priority"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "priority"],
                condition=models.Q(is_active=True),
                nulls_distinct=False,
                name="helpdesk_slapolicy_active_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(resolution_minutes__gte=models.F("first_response_minutes")),
                name="helpdesk_slapolicy_resolution_gte_first_response",
            ),
        ]

    def __str__(self):
        scope = self.category.name if self.category_id else "General"
        return f"{scope} · {self.get_priority_display()}"

    def clean(self):
        if (
            self.first_response_minutes is not None
            and self.resolution_minutes is not None
            and self.resolution_minutes < self.first_response_minutes
        ):
            raise ValidationError(
                {"resolution_minutes": "La resolución no puede ser menor que la primera respuesta."}
            )


class Alert(models.Model):
    """Alerta operativa (SPEC §26, FE-007). Una sola abierta por tipo y ticket."""

    class Type(models.TextChoices):
        SLA_WARNING = "SLA_WARNING", "SLA por vencer"
        SLA_BREACHED = "SLA_BREACHED", "SLA vencido"
        ESCALATED = "ESCALATED", "Escalado"
        HUMAN_REVIEW = "HUMAN_REVIEW", "Revisión humana"  # N4 / baja confianza (BE-T14)

    class Severity(models.TextChoices):
        INFO = "INFO", "Informativa"
        WARNING = "WARNING", "Advertencia"
        CRITICAL = "CRITICAL", "Crítica"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Abierta"
        RESOLVED = "RESOLVED", "Resuelta"

    ticket = models.ForeignKey(
        Ticket, verbose_name="ticket", on_delete=models.PROTECT, related_name="alerts"
    )
    alert_type = models.CharField("tipo", max_length=32, choices=Type.choices)
    severity = models.CharField("severidad", max_length=16, choices=Severity.choices)
    message = models.CharField("mensaje", max_length=255)
    status = models.CharField("estado", max_length=16, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField("creada", auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField("resuelta", null=True, blank=True)

    class Meta:
        verbose_name = "alerta"
        verbose_name_plural = "alertas"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["ticket", "alert_type"],
                condition=models.Q(status="OPEN"),
                name="helpdesk_alert_one_open_per_type",
            )
        ]
        indexes = [models.Index(fields=["status", "alert_type"], name="helpdesk_alert_queue_idx")]

    def __str__(self):
        return f"{self.get_alert_type_display()} · {self.ticket_id}"


class Conversation(models.Model):
    """Hilo de un usuario en un canal (SPEC §26). Une Web y WhatsApp en el mismo ticket."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        on_delete=models.PROTECT,
        related_name="conversations",
    )
    channel = models.CharField("canal", max_length=16, choices=Ticket.Channel.choices)
    external_conversation_id = models.CharField(
        "id de conversación externa", max_length=128, blank=True, default=""
    )
    active_ticket = models.ForeignKey(
        Ticket,
        verbose_name="ticket activo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    active_intent = models.CharField("intención activa", max_length=64, blank=True, default="")
    context_summary = models.TextField("resumen de contexto", blank=True, default="")
    last_message_at = models.DateTimeField("último mensaje", null=True, blank=True)
    is_active = models.BooleanField("activa", default=True)

    class Meta:
        verbose_name = "conversación"
        verbose_name_plural = "conversaciones"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "channel"],
                condition=models.Q(is_active=True),
                name="helpdesk_conversation_one_active_per_channel",
            )
        ]

    def __str__(self):
        return f"{self.user} · {self.get_channel_display()}"


class TicketMessage(models.Model):
    """Mensaje del histórico de un ticket (SPEC §26, §14)."""

    class SenderType(models.TextChoices):
        USER = "USER", "Usuario"
        AGENT = "AGENT", "Agente"
        SYSTEM = "SYSTEM", "Sistema"
        AI = "AI", "IA"

    class MessageType(models.TextChoices):
        TEXT = "TEXT", "Mensaje"
        INFO_REQUEST = "INFO_REQUEST", "Solicitud de información"
        RESOLUTION = "RESOLUTION", "Resolución"

    ticket = models.ForeignKey(
        Ticket, verbose_name="ticket", on_delete=models.PROTECT, related_name="messages"
    )
    conversation = models.ForeignKey(
        Conversation,
        verbose_name="conversación",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="messages",
        help_text="Vacío en mensajes del personal escritos desde el portal web.",
    )
    sender_type = models.CharField("remitente", max_length=16, choices=SenderType.choices)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="autor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    message_type = models.CharField(
        "tipo", max_length=16, choices=MessageType.choices, default=MessageType.TEXT
    )
    content = models.TextField("contenido", max_length=5000)
    external_message_id = models.CharField(
        "id de mensaje externo", max_length=128, blank=True, default=""
    )
    llm_generated = models.BooleanField("generado por IA", default=False)
    created_at = models.DateTimeField("fecha", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "mensaje"
        verbose_name_plural = "mensajes"
        ordering = ["created_at", "id"]
        constraints = [
            # Idempotencia de WhatsApp (BE-T11): un mensaje externo se registra una sola vez.
            models.UniqueConstraint(
                fields=["external_message_id"],
                condition=~models.Q(external_message_id=""),
                name="helpdesk_message_external_id_unique",
            )
        ]

    def __str__(self):
        return f"{self.ticket_id} · {self.get_sender_type_display()}"

    @property
    def channel(self):
        """Canal por el que llegó: el de su conversación, o Web para el personal."""
        return self.conversation.channel if self.conversation_id else Ticket.Channel.WEB
