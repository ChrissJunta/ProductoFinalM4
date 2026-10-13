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
    )
    list_display = ("username", "email", "first_name", "last_name", "source", "is_active")
    list_filter = BaseUserAdmin.list_filter + ("source",)
    search_fields = BaseUserAdmin.search_fields + ("phone", "external_id")
