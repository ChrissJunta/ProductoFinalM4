from django.urls import path

from . import views

app_name = "ai"

urlpatterns = [
    path("tickets/<str:code>/review/", views.ticket_review, name="ticket_review"),
    path("ai/traces/", views.trace_list, name="trace_list"),
    path("ai/traces/<int:pk>/", views.trace_detail, name="trace_detail"),
    path("ai/traces/<int:pk>/json/", views.trace_json, name="trace_json"),
]
