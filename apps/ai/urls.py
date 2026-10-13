from django.urls import path

from . import views

app_name = "ai"

urlpatterns = [
    path("tickets/<str:code>/review/", views.ticket_review, name="ticket_review"),
]
