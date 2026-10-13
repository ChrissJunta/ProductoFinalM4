from django.contrib import admin, messages

from . import catalogs
from .models import (
    Alert,
    Area,
    Attachment,
    AuditLog,
    Category,
    SLAPolicy,
    Subcategory,
    Ticket,
)


class CatalogAdmin(admin.ModelAdmin):
    """Admin de catálogos: escritura auditada y sin borrado físico."""

    list_display = ("code", "name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    readonly_fields = ("created_at", "updated_at")
    actions = ("activate", "deactivate")

    def save_model(self, request, obj, form, change):
        catalogs.save_catalog_item(obj, actor=request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    def _set_active(self, request, queryset, active):
        for obj in queryset:
            catalogs.set_active(obj, active, actor=request.user)
        estado = "activados" if active else "desactivados"
        self.message_user(request, f"{queryset.count()} elementos {estado}.", messages.SUCCESS)

    @admin.action(description="Activar seleccionados", permissions=["change"])
    def activate(self, request, queryset):
        self._set_active(request, queryset, True)

    @admin.action(description="Desactivar seleccionados", permissions=["change"])
    def deactivate(self, request, queryset):
        self._set_active(request, queryset, False)


@admin.register(Area)
class AreaAdmin(CatalogAdmin):
    list_display = ("code", "name", "email", "is_active", "updated_at")
    filter_horizontal = ("agents",)

    def save_related(self, request, form, formsets, change):
        # Los agentes del área se guardan con el servicio auditado, no con form.save_m2m().
        catalogs.set_area_agents(form.instance, form.cleaned_data["agents"], actor=request.user)


@admin.register(Category)
class CategoryAdmin(CatalogAdmin):
    list_display = ("code", "name", "default_area", "is_active", "updated_at")
    list_filter = ("is_active", "default_area")
    list_select_related = ("default_area",)


@admin.register(Subcategory)
class SubcategoryAdmin(CatalogAdmin):
    list_display = ("code", "name", "category", "is_active", "updated_at")
    list_filter = ("is_active", "category")
    list_select_related = ("category",)


@admin.register(SLAPolicy)
class SLAPolicyAdmin(CatalogAdmin):
    list_display = (
        "__str__",
        "first_response_minutes",
        "resolution_minutes",
        "business_hours_only",
        "is_active",
    )
    list_filter = ("is_active", "priority", "business_hours_only", "category")
    search_fields = ("category__name",)
    list_select_related = ("category",)


class ReadOnlyAdmin(admin.ModelAdmin):
    """Solo consulta: la escritura pasa por los servicios, que auditan cada cambio."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "actor_type", "actor", "action", "entity_type", "entity_id")
    list_filter = ("actor_type", "action", "entity_type")
    search_fields = ("entity_id", "actor__username")
    list_select_related = ("actor",)


@admin.register(Ticket)
class TicketAdmin(ReadOnlyAdmin):
    list_display = ("ticket_code", "subject", "user", "status", "priority", "channel", "created_at")
    list_filter = ("status", "priority", "channel", "assigned_area")
    search_fields = ("ticket_code", "subject", "user__username")
    list_select_related = ("user",)


@admin.register(Attachment)
class AttachmentAdmin(ReadOnlyAdmin):
    list_display = ("original_name", "ticket", "content_type", "size_bytes", "created_at")
    list_select_related = ("ticket",)


@admin.register(Alert)
class AlertAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "alert_type", "severity", "ticket", "status", "resolved_at")
    list_filter = ("status", "alert_type", "severity")
    search_fields = ("ticket__ticket_code",)
    list_select_related = ("ticket",)
