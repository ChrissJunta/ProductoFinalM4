from django.contrib import admin

from apps.helpdesk.admin import ReadOnlyAdmin

from .models import IntegrationInbox, IntegrationOutbox


@admin.register(IntegrationInbox)
class IntegrationInboxAdmin(ReadOnlyAdmin):
    list_display = ("received_at", "provider", "external_event_id", "status", "attempts")
    list_filter = ("provider", "status")
    search_fields = ("external_event_id",)


@admin.register(IntegrationOutbox)
class IntegrationOutboxAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "provider", "destination", "status", "attempts", "sent_at")
    list_filter = ("provider", "status")
    search_fields = ("destination", "external_message_id")
