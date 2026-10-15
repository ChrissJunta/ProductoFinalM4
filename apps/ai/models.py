"""Configuración y trazabilidad de IA (SPEC §43, BE-T16/BE-T18).

El LLM nunca escribe en estos modelos ni en los de negocio: los registra
`AIService` / el runner del agente (SPEC §45).
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Operation(models.TextChoices):
    CLASSIFY = "CLASSIFY", "Clasificar"
    EXTRACT = "EXTRACT", "Extraer"
    SUMMARIZE = "SUMMARIZE", "Resumir"
    GENERATE_RESPONSE = "GENERATE_RESPONSE", "Generar respuesta"
    AGENT_RUN = "AGENT_RUN", "Ejecución del agente"


class AIModelConfig(models.Model):
    """Modelo primario y de respaldo por propósito (SPEC §46: LLM primario → fallback)."""

    provider = models.CharField("proveedor", max_length=32)
    model_name = models.CharField("modelo", max_length=100)
    purpose = models.CharField("propósito", max_length=32, choices=Operation.choices)
    is_primary = models.BooleanField("primario", default=False)
    is_fallback = models.BooleanField("respaldo", default=False)
    is_active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)

    audit_fields = ("provider", "model_name", "purpose", "is_primary", "is_fallback", "is_active")

    class Meta:
        verbose_name = "modelo de IA"
        verbose_name_plural = "modelos de IA"
        ordering = ["purpose", "-is_primary", "provider"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(is_primary=True, is_fallback=True),
                name="ai_modelconfig_primary_xor_fallback",
            ),
            models.UniqueConstraint(
                fields=["provider", "purpose"],
                condition=models.Q(is_primary=True, is_active=True),
                name="ai_modelconfig_one_primary",
            ),
            models.UniqueConstraint(
                fields=["provider", "purpose"],
                condition=models.Q(is_fallback=True, is_active=True),
                name="ai_modelconfig_one_fallback",
            ),
        ]

    def __str__(self):
        role = "primario" if self.is_primary else "respaldo" if self.is_fallback else "—"
        return f"{self.provider}/{self.model_name} ({self.get_purpose_display()}, {role})"


class AIPromptVersion(models.Model):
    name = models.CharField("nombre", max_length=64)
    version = models.PositiveIntegerField("versión")
    purpose = models.CharField("propósito", max_length=32, choices=Operation.choices)
    template = models.TextField("plantilla")
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)

    audit_fields = ("name", "version", "purpose", "template", "is_active")

    class Meta:
        verbose_name = "versión de prompt"
        verbose_name_plural = "versiones de prompt"
        ordering = ["purpose", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["name", "version"], name="ai_prompt_name_version"),
            models.UniqueConstraint(
                fields=["purpose"],
                condition=models.Q(is_active=True),
                name="ai_prompt_one_active_per_purpose",
            ),
        ]

    def __str__(self):
        return f"{self.name} v{self.version}"


class AIUsage(models.Model):
    """Una fila por llamada al proveedor, con éxito o error (SPEC §43)."""

    ticket = models.ForeignKey(
        "helpdesk.Ticket", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    message = models.ForeignKey(
        "helpdesk.TicketMessage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    provider = models.CharField("proveedor", max_length=32)
    model_name = models.CharField("modelo", max_length=100)
    operation = models.CharField("operación", max_length=32, choices=Operation.choices)
    input_tokens = models.PositiveIntegerField("tokens de entrada", default=0)
    output_tokens = models.PositiveIntegerField("tokens de salida", default=0)
    latency_ms = models.PositiveIntegerField("latencia (ms)", default=0)
    estimated_cost = models.DecimalField(
        "costo estimado", max_digits=10, decimal_places=6, default=0
    )
    success = models.BooleanField("éxito")
    error_code = models.CharField("código de error", max_length=64, blank=True, default="")
    created_at = models.DateTimeField("creado", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "uso de IA"
        verbose_name_plural = "usos de IA"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.provider}/{self.model_name} · {self.get_operation_display()} · #{self.pk}"


class AIDecision(models.Model):
    """Decisión de IA / del agente, revisable por un humano (SPEC §43, §46A.7)."""

    ticket = models.ForeignKey(
        "helpdesk.Ticket",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_decisions",
    )
    message = models.ForeignKey(
        "helpdesk.TicketMessage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="remitente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    prompt_version = models.ForeignKey(
        AIPromptVersion, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    operation = models.CharField("operación", max_length=32, choices=Operation.choices)
    channel = models.CharField("canal", max_length=16, blank=True, default="")
    intent_code = models.CharField("intención", max_length=32, blank=True, default="")
    autonomy_level = models.CharField("nivel", max_length=2, blank=True, default="")
    classification_source = models.CharField("origen", max_length=16, blank=True, default="")
    raw_output = models.TextField("salida cruda", blank=True, default="")
    parsed_output = models.JSONField("salida validada", null=True, blank=True)
    confidence = models.DecimalField(
        "confianza",
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    requires_human = models.BooleanField("requiere humano", default=False)
    accepted = models.BooleanField("aceptada", null=True, blank=True)
    corrected = models.BooleanField("corregida", default=False)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="corregida por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_at = models.DateTimeField("revisada", null=True, blank=True)
    graph_version = models.CharField("versión del grafo", max_length=16, blank=True, default="")
    node_path = models.JSONField("recorrido de nodos", default=list, blank=True)
    thread_id = models.CharField("hilo", max_length=64, blank=True, default="", db_index=True)
    errors = models.JSONField("errores", default=list, blank=True)
    trace = models.JSONField(
        "traza", default=list, blank=True, help_text="Pasos del agente por nodo (ADR-076)."
    )
    duration_ms = models.PositiveIntegerField("duración (ms)", null=True, blank=True)
    created_at = models.DateTimeField("creada", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "decisión de IA"
        verbose_name_plural = "decisiones de IA"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_operation_display()} · {self.intent_code or '—'} · #{self.pk}"

    @property
    def pending_review(self):
        return self.requires_human and self.accepted is None


class AgentPolicyDecision(models.Model):
    """Decisión propia del agente a partir de sus métricas (ADR-077).

    Modo mixto: las decisiones seguras se aplican solas (`auto=True`); las que le dan
    más autonomía quedan PROPUESTAS hasta que un Supervisor o Administrador las aprueba.
    """

    class Kind(models.TextChoices):
        TRUST_UP = "TRUST_UP", "D1 · Ganar confianza (sin revisión)"
        TRUST_DOWN = "TRUST_DOWN", "D2 · Perder confianza (revisión siempre)"
        KEYWORDS = "KEYWORDS", "D3 · Aprender palabras clave"
        LLM_PAUSE = "LLM_PAUSE", "D4 · Pausar el LLM"
        LLM_RESUME = "LLM_RESUME", "D4 · Reactivar el LLM"
        PRIORITY_UP = "PRIORITY_UP", "D5 · Subir prioridad por SLA"

    class Status(models.TextChoices):
        PROPOSED = "PROPOSED", "Propuesta"
        APPLIED = "APPLIED", "Aplicada"
        REJECTED = "REJECTED", "Rechazada"
        REVERTED = "REVERTED", "Revertida"

    kind = models.CharField("decisión", max_length=16, choices=Kind.choices)
    intent = models.ForeignKey(
        "automation.Intent",
        verbose_name="intención",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    status = models.CharField("estado", max_length=10, choices=Status.choices)
    auto = models.BooleanField("aplicada sola", default=False)
    summary = models.CharField("resumen", max_length=255)
    evidence = models.JSONField("evidencia", default=dict, blank=True)
    change = models.JSONField("cambio", default=dict, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="decidida por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField("decidida", null=True, blank=True)
    note = models.CharField("nota", max_length=255, blank=True, default="")
    created_at = models.DateTimeField("creada", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "decisión del agente"
        verbose_name_plural = "decisiones del agente"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.get_status_display()} · #{self.pk}"


class LLMCircuit(models.Model):
    """Interruptor del LLM (D4): fila única. OPEN = no se llama al LLM hasta `retry_at`;
    después se permite una llamada de prueba que lo cierra si responde."""

    class State(models.TextChoices):
        CLOSED = "CLOSED", "Activo"
        OPEN = "OPEN", "En pausa"

    state = models.CharField("estado", max_length=6, choices=State.choices, default=State.CLOSED)
    retry_at = models.DateTimeField("reintentar desde", null=True, blank=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        verbose_name = "interruptor del LLM"
        verbose_name_plural = "interruptor del LLM"

    def __str__(self):
        return self.get_state_display()
