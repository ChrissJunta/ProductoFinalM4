from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.role_redirect, name="role_redirect"),
    path("inicio/", views.home, name="home"),
    path("accounts/login/", views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/whatsapp/", views.whatsapp_link, name="whatsapp"),
]
