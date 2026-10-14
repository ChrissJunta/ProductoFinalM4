from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import admin_login

urlpatterns = [
    path(f"{settings.ADMIN_URL}login/", admin_login, name="admin_login"),
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.helpdesk.urls")),
    path("", include("apps.automation.urls")),
    path("", include("apps.ai.urls")),
    path("manage/", include("apps.helpdesk.manage_urls")),
    path("", include("apps.integrations.urls")),
]
