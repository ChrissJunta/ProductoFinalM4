from django.urls import path

from . import views

app_name = "helpdesk"

urlpatterns = [
    path("tickets/new/", views.ticket_create, name="ticket_create"),
    path(
        "tickets/<str:code>/attachments/<int:pk>/",
        views.attachment_download,
        name="attachment_download",
    ),
]
