from django.urls import path

from . import views

app_name = "automation"

urlpatterns = [
    path("assistant/", views.assistant, name="assistant"),
]
