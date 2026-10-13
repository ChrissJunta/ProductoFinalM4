from django.urls import path

from . import manage_views as views

app_name = "manage"

urlpatterns = [
    path("", views.manage_index, name="index"),
    path("<slug:entity>/", views.manage_list, name="list"),
    path("<slug:entity>/new/", views.manage_create, name="create"),
    path("<slug:entity>/<int:pk>/", views.manage_edit, name="edit"),
    path("<slug:entity>/<int:pk>/toggle/", views.manage_toggle, name="toggle"),
]
