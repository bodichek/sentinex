"""Weekly Brief views."""

from __future__ import annotations

from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.addons.weekly_brief.models import WeeklyBriefConfig, WeeklyBriefReport
from apps.addons.weekly_brief.pdf_generator import PDFGenerationError, render_report_pdf
from apps.core.addons.decorators import addon_required
from apps.core.middleware import require_membership


@login_required
@require_membership
@addon_required("weekly_brief")
def home(request: HttpRequest) -> HttpResponse:
    latest = WeeklyBriefReport.objects.filter(status=WeeklyBriefReport.STATUS_GENERATED).first()
    return render(request, "addons/weekly_brief/home.html", {"report": latest})


@login_required
@require_membership
@addon_required("weekly_brief")
def history(request: HttpRequest) -> HttpResponse:
    reports = WeeklyBriefReport.objects.all()[:50]
    return render(request, "addons/weekly_brief/history.html", {"reports": reports})


@login_required
@require_membership
@addon_required("weekly_brief")
def detail(request: HttpRequest, uuid: UUID) -> HttpResponse:
    report = get_object_or_404(WeeklyBriefReport, uuid=uuid)
    return render(request, "addons/weekly_brief/brief_detail.html", {"report": report})


@login_required
@require_membership
@addon_required("weekly_brief")
def pdf_export(request: HttpRequest, uuid: UUID) -> HttpResponse:
    report = get_object_or_404(WeeklyBriefReport, uuid=uuid)
    try:
        pdf_bytes = render_report_pdf(report)
    except PDFGenerationError as exc:
        return HttpResponse(f"PDF export selhal: {exc}", status=503, content_type="text/plain")
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="brief-{report.period_end}.pdf"'
    return response


@login_required
@require_membership
@addon_required("weekly_brief")
def configure(request: HttpRequest) -> HttpResponse:
    config, _ = WeeklyBriefConfig.objects.get_or_create(pk=1)
    if request.method == "POST":
        config.recipients = request.POST.get("recipients", "").strip()
        config.schedule_day = int(request.POST.get("schedule_day", config.schedule_day))
        config.schedule_hour = int(request.POST.get("schedule_hour", config.schedule_hour))
        config.timezone = request.POST.get("timezone", config.timezone)
        config.save()
    return render(request, "addons/weekly_brief/configure.html", {"config": config})
