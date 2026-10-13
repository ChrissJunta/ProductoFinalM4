"""Colas de integración y vinculación de WhatsApp (SPEC §35-§37, BE-T11/T11A/T12)."""

from django.conf import settings
from django.db import models


class Provider(models.TextChoices):
    WHATSAPP = "WHATSAPP", "WhatsApp"


class IntegrationInbox(models.Model):
    """Evento recibido. `external_event_id` único por proveedor = idempotencia."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        DONE = "DONE", "Procesado"
        IGNORED = "IGNORED", "Ignorado"
        FAILED = "FAILED", "Fallido"

    provider = models.CharField("proveedor", max_length=16, choices=Provider.choices)
    external_event_id = models.CharField("id externo", max_length=128)
    payload_json = models.JSONField("carga")
    status = models.CharField(
        "estado", max_length=16, choices=Status.choices, default=Status.PENDING
    )
    attempts = models.PositiveSmallIntegerField("intentos", default=0)
    next_attempt_at = models.DateTimeField("próximo intento", null=True, blank=True)
    received_at = models.DateTimeField("recibido", auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField("procesado", null=True, blank=True)
    last_error = models.TextField("último error", blank=True, default="")

    class Meta:
        verbose_name = "evento recibido"
        verbose_name_plural = "eventos recibidos"
        ordering = ["received_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_event_id"], name="integrations_inbox_idempotent"
            )
        ]
        indexes = [models.Index(fields=["status", "next_attempt_at"], name="integ_inbox_queue_idx")]

    def __str__(self):
        return f"{self.provider} {self.external_event_id} ({self.status})"


class IntegrationOutbox(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        SENT = "SENT", "Enviado"
        FAILED = "FAILED", "Fallido"

    provider = models.CharField("proveedor", max_length=16, choices=Provider.choices)
    destination = models.CharField("destino", max_length=32)
    payload_json = models.JSONField("carga")
    status = models.CharField(
        "estado", max_length=16, choices=Status.choices, default=Status.PENDING
    )
    attempts = models.PositiveSmallIntegerField("intentos", default=0)
    next_attempt_at = models.DateTimeField("próximo intento", null=True, blank=True)
    created_at = models.DateTimeField("creado", auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField("enviado", null=True, blank=True)
    external_message_id = models.CharField("id externo", max_length=128, blank=True, default="")
    last_error = models.TextField("último error", blank=True, default="")

    class Meta:
        verbose_name = "mensaje saliente"
        verbose_name_plural = "mensajes salientes"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="integ_outbox_queue_idx")
        ]

    def __str__(self):
        return f"→ {self.destination} ({self.status})"


class WhatsAppLinkCode(models.Model):
    """Código de vinculación (SPEC §35.1): hash, un solo uso, 10 minutos."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="whatsapp_codes"
    )
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "código de vinculación"
        verbose_name_plural = "códigos de vinculación"
        indexes = [models.Index(fields=["code_hash"], name="integ_linkcode_hash_idx")]

    def __str__(self):
        return f"Código de {self.user} ({'usado' if self.used_at else 'vigente'})"
