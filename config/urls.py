from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.helpdesk.urls")),
    path("", include("apps.automation.urls")),
    path("", include("apps.ai.urls")),
    path("manage/", include("apps.helpdesk.manage_urls")),
    path("", include("apps.integrations.urls")),
]
