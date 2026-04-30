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
    path("integrations/slack/", include("apps.connectors.slack.urls")),
    path("integrations/smartemailing/", include("apps.connectors.smartemailing.urls")),
    path("integrations/pipedrive/", include("apps.connectors.pipedrive.urls")),
    path("integrations/canva/", include("apps.connectors.canva.urls")),
    path("integrations/trello/", include("apps.connectors.trello.urls")),
    path("integrations/raynet/",        include("apps.connectors.raynet.urls")),
    path("integrations/caflou/",        include("apps.connectors.caflou.urls")),
    path("integrations/ecomail/",       include("apps.connectors.ecomail.urls")),
    path("integrations/fapi/",          include("apps.connectors.fapi.urls")),
    path("integrations/microsoft365/",  include("apps.connectors.microsoft365.urls")),
    path("integrations/salesforce/",    include("apps.connectors.salesforce.urls")),
    path("integrations/asana/",         include("apps.connectors.asana.urls")),
    path("integrations/basecamp/",      include("apps.connectors.basecamp.urls")),
    path("integrations/mailchimp/",     include("apps.connectors.mailchimp.urls")),
    path("integrations/calendly/",      include("apps.connectors.calendly.urls")),
    path("integrations/hubspot/",       include("apps.connectors.hubspot.urls")),
    path("integrations/jira/",          include("apps.connectors.jira.urls")),
    path("integrations/notion/",        include("apps.connectors.notion.urls")),
    path("integrations/dropbox/",       include("apps.connectors.dropbox.urls")),
    path("insights/", include(insights_urlpatterns)),
    path("chat/", include("apps.chat.urls")),
    path("knowledge/", include("apps.data_access.knowledge.urls")),
    path("addons/weekly-brief/", include("apps.addons.weekly_brief.urls")),
    path("", include("apps.core.urls")),
]
