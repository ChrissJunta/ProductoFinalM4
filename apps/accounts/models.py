from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

# Formato E.164: "+" seguido de 8 a 15 dígitos, sin espacios.
phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="Ingrese el teléfono en formato internacional, por ejemplo +593991234567.",
)


class User(AbstractUser):
    """Usuario del sistema (SPEC §25). Los roles se gestionan con Groups."""

    class Source(models.TextChoices):
        LOCAL = "LOCAL", "Local"
        SGA = "SGA", "SGA"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    phone = models.CharField(
        "teléfono", max_length=16, blank=True, default="", validators=[phone_validator]
    )
    phone_verified_at = models.DateTimeField(
        "teléfono verificado el",
        null=True,
        blank=True,
        help_text="Vacío si el teléfono no está verificado para WhatsApp (SPEC §35.1).",
    )
    external_id = models.CharField(
        "identificador institucional", max_length=64, blank=True, default=""
    )
    source = models.CharField("origen", max_length=16, choices=Source.choices, default=Source.LOCAL)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.UniqueConstraint(
                fields=["phone"],
                condition=~Q(phone=""),
                name="accounts_user_phone_unique",
            ),
            models.UniqueConstraint(
                fields=["external_id"],
                condition=~Q(external_id=""),
                name="accounts_user_external_id_unique",
            ),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loaded_phone = (self.phone, self.phone_verified_at)

    def save(self, *args, **kwargs):
        """Cambiar el teléfono anula la verificación (SPEC §35.1), salvo que la vinculación
        fije a la vez un nuevo `phone_verified_at`."""
        phone, verified_at = self._loaded_phone
        if self.phone != phone and self.phone_verified_at == verified_at and verified_at:
            self.phone_verified_at = None
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "phone_verified_at"}
        super().save(*args, **kwargs)
        self._loaded_phone = (self.phone, self.phone_verified_at)

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self._loaded_phone = (self.phone, self.phone_verified_at)

    @property
    def is_phone_verified(self):
        return bool(self.phone) and self.phone_verified_at is not None
