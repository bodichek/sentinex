from __future__ import annotations

from django.urls import path

from apps.addons.weekly_brief import api, views

app_name = "weekly_brief"

urlpatterns = [
    path("", views.home, name="home"),
    path("history/", views.history, name="history"),
    path("configure/", views.configure, name="configure"),
    path("<uuid:uuid>/", views.detail, name="detail"),
    path("<uuid:uuid>/pdf/", views.pdf_export, name="pdf"),
    path("api/generate/", api.GenerateView.as_view(), name="api_generate"),
    path("api/reports/", api.ReportsView.as_view(), name="api_reports"),
]
