from django.urls import path

from . import views

app_name = "helpdesk"

urlpatterns = [
    path("tickets/", views.ticket_list, name="ticket_list"),
    path("tickets/new/", views.ticket_create, name="ticket_create"),
    path("agent/inbox/", views.agent_inbox, name="agent_inbox"),
    path("alerts/", views.alert_list, name="alert_list"),
    path("tickets/<str:code>/", views.ticket_detail, name="ticket_detail"),
    path("tickets/<str:code>/messages/", views.ticket_message, name="ticket_message"),
    path("tickets/<str:code>/assign/", views.ticket_assign, name="ticket_assign"),
    path("tickets/<str:code>/status/", views.ticket_transition, name="ticket_status"),
    path(
        "tickets/<str:code>/resolve/",
        views.ticket_transition,
        {"action": "resolve"},
        name="ticket_resolve",
    ),
    path(
        "tickets/<str:code>/escalate/",
        views.ticket_transition,
        {"action": "escalate"},
        name="ticket_escalate",
    ),
    path(
        "tickets/<str:code>/confirm/",
        views.ticket_transition,
        {"action": "confirm"},
        name="ticket_confirm",
    ),
    path(
        "tickets/<str:code>/reject-resolution/",
        views.ticket_transition,
        {"action": "reject_resolution"},
        name="ticket_reject_resolution",
    ),
    path(
        "tickets/<str:code>/reopen/",
        views.ticket_transition,
        {"action": "reopen"},
        name="ticket_reopen",
    ),
    path(
        "tickets/<str:code>/cancel/",
        views.ticket_transition,
        {"action": "cancel"},
        name="ticket_cancel",
    ),
    path(
        "tickets/<str:code>/attachments/<int:pk>/",
        views.attachment_download,
        name="attachment_download",
    ),
]
