from django.urls import path

from .whatsapp import views

app_name = "integrations"

urlpatterns = [
    path("api/webhooks/whatsapp/", views.whatsapp_webhook, name="whatsapp_webhook"),
]
