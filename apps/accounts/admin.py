from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Datos institucionales",
            {"fields": ("phone", "phone_verified_at", "external_id", "source")},
        ),
        ("Telegram", {"fields": ("telegram_chat_id", "telegram_verified_at")}),
        ("Seguridad", {"fields": ("must_change_password",)}),
    )
    list_display = ("username", "email", "first_name", "last_name", "source", "is_active")
    list_filter = BaseUserAdmin.list_filter + ("source", "must_change_password")
    search_fields = BaseUserAdmin.search_fields + ("phone", "external_id")

    def save_model(self, request, obj, form, change):
        # Quien recibe una contraseña creada por otra persona debe cambiarla (ADR-072).
        if not change:
            obj.must_change_password = True
        super().save_model(request, obj, form, change)

    def user_change_password(self, request, id, form_url=""):
        response = super().user_change_password(request, id, form_url)
        if (
            request.method == "POST"
            and response.status_code == 302
            and str(request.user.pk) != str(id)
        ):
            User.objects.filter(pk=id).update(must_change_password=True)
        return response
