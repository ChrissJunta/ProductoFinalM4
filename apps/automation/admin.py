from django.contrib import admin

from apps.helpdesk.admin import CatalogAdmin

from .models import Intent, IntentAction, RoutingRule

# Toda escritura pasa por helpdesk.catalogs (auditada, sin borrado físico).


@admin.register(Intent)
class IntentAdmin(CatalogAdmin):
    list_display = (
        "code",
        "name",
        "automation_level",
        "requires_authentication",
        "requires_human",
        "is_active",
    )
    list_filter = ("is_active", "automation_level", "requires_authentication")


@admin.register(IntentAction)
class IntentActionAdmin(CatalogAdmin):
    list_display = ("intent", "action_type", "provider_method", "fallback_action", "is_active")
    list_filter = ("is_active", "action_type")
    search_fields = ("intent__code", "intent__name", "response_template")
    list_select_related = ("intent",)


@admin.register(RoutingRule)
class RoutingRuleAdmin(CatalogAdmin):
    list_display = (
        "order",
        "intent",
        "category",
        "subcategory",
        "area",
        "priority",
        "requires_validation",
        "is_active",
    )
    list_display_links = ("order", "intent")
    list_filter = ("is_active", "area", "priority", "requires_validation")
    search_fields = ("intent__code", "category__code", "subcategory__code", "area__code")
    list_select_related = ("intent", "category", "subcategory", "area")
    ordering = ("order", "id")
