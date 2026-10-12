from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import RegexValidator
from django.db import models

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
