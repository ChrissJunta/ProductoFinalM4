from django.contrib import admin

from apps.helpdesk.admin import CatalogAdmin, ReadOnlyAdmin

from .models import AIDecision, AIModelConfig, AIPromptVersion, AIUsage


@admin.register(AIModelConfig)
class AIModelConfigAdmin(CatalogAdmin):
    list_display = ("provider", "model_name", "purpose", "is_primary", "is_fallback", "is_active")
    list_filter = ("is_active", "provider", "purpose")
    search_fields = ("provider", "model_name")
    readonly_fields = ("created_at",)


@admin.register(AIPromptVersion)
class AIPromptVersionAdmin(CatalogAdmin):
    list_display = ("name", "version", "purpose", "is_active", "created_at")
    list_filter = ("is_active", "purpose")
    search_fields = ("name", "template")
    readonly_fields = ("created_at",)


@admin.register(AIUsage)
class AIUsageAdmin(ReadOnlyAdmin):
    list_display = (
        "created_at", "provider", "model_name", "operation", "success", "error_code",
        "input_tokens", "output_tokens", "latency_ms",
    )  # fmt: skip
    list_filter = ("success", "operation", "provider")


@admin.register(AIDecision)
class AIDecisionAdmin(ReadOnlyAdmin):
    list_display = (
        "created_at", "operation", "intent_code", "autonomy_level", "classification_source",
        "confidence", "requires_human", "accepted", "corrected", "ticket",
    )  # fmt: skip
    list_filter = ("operation", "autonomy_level", "classification_source", "requires_human")
    search_fields = ("intent_code", "thread_id", "ticket__ticket_code")
    list_select_related = ("ticket",)
