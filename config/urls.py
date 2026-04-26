"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.addons.weekly_brief import api as weekly_brief_api
from apps.core.health import healthcheck
from apps.data_access.urls import insights_urlpatterns

urlpatterns = [
    path("", RedirectView.as_view(url="/dashboard/", permanent=False)),
    path("health/", healthcheck, name="healthcheck"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/v1/", include("apps.agents.urls")),
    path(
        "api/addons/weekly_brief/trigger/",
        weekly_brief_api.GenerateView.as_view(),
        name="weekly_brief_trigger",
    ),
    path("integrations/", include("apps.data_access.urls")),
    path("insights/", include(insights_urlpatterns)),
    path("chat/", include("apps.chat.urls")),
    path("addons/weekly-brief/", include("apps.addons.weekly_brief.urls")),
    path("", include("apps.core.urls")),
]
