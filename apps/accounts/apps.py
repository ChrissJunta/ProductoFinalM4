from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Cuentas"

    def ready(self):
        from . import checks, signals  # noqa: F401  (registra receptores y checks)
