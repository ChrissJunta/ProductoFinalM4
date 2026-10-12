from django.contrib import admin, messages

from . import catalogs
from .models import Area, AuditLog, Category, Subcategory


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


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Solo lectura: la auditoría no se crea, edita ni borra desde el admin."""

    list_display = ("created_at", "actor_type", "actor", "action", "entity_type", "entity_id")
    list_filter = ("actor_type", "action", "entity_type")
    search_fields = ("entity_id", "actor__username")
    list_select_related = ("actor",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
