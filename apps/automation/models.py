"""Automatización configurable (SPEC §28): intenciones, acciones y reglas de routing.

Todo es configuración en base de datos: cambiar una regla cambia el enrutamiento
del siguiente ticket sin redeploy (criterio de BE-T09). No hay tabla genérica de
«business_rules».
"""

from django.core.exceptions import ValidationError
from django.db import models

from apps.helpdesk.models import Area, CatalogModel, Category, Subcategory, Ticket, code_validator


class AutomationLevel(models.TextChoices):
    """Nivel de autonomía (SPEC §31)."""

    N0 = "N0", "N0 · Consulta estructurada"
    N1 = "N1", "N1 · Conocimiento autorizado"
    N2 = "N2", "N2 · Ticket + validación"
    N3 = "N3", "N3 · Ticket + routing"
    N4 = "N4", "N4 · Revisión humana"


class Intent(CatalogModel):
    code = models.CharField("código", max_length=32, unique=True, validators=[code_validator])
    automation_level = models.CharField(
        "nivel de autonomía", max_length=2, choices=AutomationLevel.choices
    )
    requires_authentication = models.BooleanField(
        "requiere autenticación",
        default=False,
        help_text="Datos personales: solo con sesión web o teléfono verificado (SPEC §31.2).",
    )
    requires_llm = models.BooleanField("requiere LLM", default=False)
    requires_human = models.BooleanField("requiere humano", default=False)
    # CR-006: coincidencias configuradas del Intent Engine (SPEC §30).
    keywords = models.TextField(
        "palabras clave",
        blank=True,
        default="",
        help_text=(
            "Una por línea. «a + b» exige que aparezcan todas las partes. Cada coincidencia "
            "suma tantos puntos como palabras tenga. No distingue mayúsculas ni tildes."
        ),
    )

    audit_fields = (
        "code",
        "name",
        "automation_level",
        "requires_authentication",
        "requires_llm",
        "requires_human",
        "keywords",
        "is_active",
    )

    class Meta(CatalogModel.Meta):
        verbose_name = "intención"
        verbose_name_plural = "intenciones"
        ordering = ["automation_level", "code"]


class IntentAction(models.Model):
    """Qué hace el sistema con una intención reconocida (SPEC §28, §31)."""

    class ActionType(models.TextChoices):
        PROVIDER_QUERY = "PROVIDER_QUERY", "Consultar proveedor institucional (N0)"
        TEMPLATE_RESPONSE = "TEMPLATE_RESPONSE", "Responder con plantilla (N1)"
        CREATE_TICKET = "CREATE_TICKET", "Crear ticket (N2/N3)"
        HUMAN_REVIEW = "HUMAN_REVIEW", "Derivar a revisión humana (N4)"

    # Contrato de InstitutionalDataProvider (SPEC §39); se valida aquí para no
    # aceptar métodos inexistentes en la configuración.
    PROVIDER_METHODS = (
        "get_schedule",
        "get_grades",
        "get_debt",
        "get_enrollment",
        "get_subjects",
        "get_ticket_status",
    )

    intent = models.ForeignKey(
        Intent, verbose_name="intención", on_delete=models.PROTECT, related_name="actions"
    )
    action_type = models.CharField("tipo de acción", max_length=32, choices=ActionType.choices)
    provider_method = models.CharField(
        "método del proveedor", max_length=64, blank=True, default=""
    )
    response_template = models.TextField(
        "plantilla de respuesta",
        blank=True,
        default="",
        help_text="Fuente única de N1 (SPEC §31.1): el LLM solo puede reformularla.",
    )
    fallback_action = models.CharField(
        "acción de respaldo",
        max_length=32,
        choices=ActionType.choices,
        default=ActionType.CREATE_TICKET,
    )
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    audit_fields = (
        "intent_id",
        "action_type",
        "provider_method",
        "response_template",
        "fallback_action",
        "is_active",
    )

    class Meta:
        verbose_name = "acción de intención"
        verbose_name_plural = "acciones de intención"
        ordering = ["intent__code", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["intent"],
                condition=models.Q(is_active=True),
                name="automation_one_active_action_per_intent",
            )
        ]

    def __str__(self):
        return f"{self.intent.code} → {self.get_action_type_display()}"

    def clean(self):
        T = self.ActionType
        if (
            self.action_type == T.PROVIDER_QUERY
            and self.provider_method not in self.PROVIDER_METHODS
        ):
            raise ValidationError(
                {"provider_method": f"Use uno de: {', '.join(self.PROVIDER_METHODS)}."}
            )
        if self.action_type == T.TEMPLATE_RESPONSE and not self.response_template.strip():
            raise ValidationError({"response_template": "La respuesta N1 necesita una plantilla."})


class RoutingRule(models.Model):
    """Regla de enrutamiento (SPEC §28). Gana la de menor `order` que coincida.

    Intención, categoría y subcategoría vacías actúan como comodín.
    """

    intent = models.ForeignKey(
        Intent, verbose_name="intención", null=True, blank=True, on_delete=models.PROTECT
    )
    category = models.ForeignKey(
        Category, verbose_name="categoría", null=True, blank=True, on_delete=models.PROTECT
    )
    subcategory = models.ForeignKey(
        Subcategory, verbose_name="subcategoría", null=True, blank=True, on_delete=models.PROTECT
    )
    area = models.ForeignKey(Area, verbose_name="área destino", on_delete=models.PROTECT)
    priority = models.CharField(
        "prioridad",
        max_length=16,
        choices=Ticket.Priority.choices,
        blank=True,
        default="",
        help_text="Vacío = mantener la prioridad del ticket.",
    )
    requires_validation = models.BooleanField("requiere validación", default=False)
    order = models.PositiveIntegerField("orden", default=100)
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    audit_fields = (
        "intent_id",
        "category_id",
        "subcategory_id",
        "area_id",
        "priority",
        "requires_validation",
        "order",
        "is_active",
    )

    class Meta:
        verbose_name = "regla de routing"
        verbose_name_plural = "reglas de routing"
        ordering = ["order", "id"]

    def __str__(self):
        parts = [
            self.intent.code if self.intent_id else None,
            self.category.code if self.category_id else None,
            self.subcategory.code if self.subcategory_id else None,
        ]
        criteria = " + ".join(p for p in parts if p) or "cualquier ticket"
        return f"#{self.order} {criteria} → {self.area.code}"

    def clean(self):
        if not (self.intent_id or self.category_id or self.subcategory_id):
            raise ValidationError("Indique al menos intención, categoría o subcategoría.")
        if (
            self.subcategory_id
            and self.category_id
            and self.subcategory.category_id != self.category_id
        ):
            raise ValidationError({"subcategory": "La subcategoría no pertenece a la categoría."})


class IntentPolicy(models.Model):
    """Política vigente que el agente ajusta por intención con sus decisiones (ADR-077).

    Solo la modifican las decisiones aplicadas (`apps.ai.policies`): cada cambio queda
    en `AgentPolicyDecision` con su evidencia y se puede revertir.
    """

    class ReviewMode(models.TextChoices):
        DEFAULT = "DEFAULT", "Según confianza"
        SKIP = "SKIP", "Sin revisión (muestreo de control)"
        ALWAYS = "ALWAYS", "Revisión siempre"

    intent = models.OneToOneField(
        Intent, on_delete=models.CASCADE, related_name="policy", verbose_name="intención"
    )
    review_mode = models.CharField(
        "revisión humana", max_length=8, choices=ReviewMode.choices, default=ReviewMode.DEFAULT
    )
    priority_override = models.CharField(
        "prioridad mínima",
        max_length=10,
        blank=True,
        default="",
        help_text="Prioridad mínima de sus tickets nuevos (vacío = la del routing).",
    )
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        verbose_name = "política de intención"
        verbose_name_plural = "políticas de intención"

    def __str__(self):
        return f"{self.intent.code}: {self.get_review_mode_display()}"
