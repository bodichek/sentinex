"""Weekly Brief Celery tasks."""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.core.mail import send_mail
from django_tenants.utils import schema_context

from apps.addons.weekly_brief.models import WeeklyBriefConfig, WeeklyBriefReport
from apps.addons.weekly_brief.services import WeeklyBriefGenerator

logger = logging.getLogger(__name__)


@shared_task(name="weekly_brief.generate_weekly_brief_for_tenant")  # type: ignore[untyped-decorator]
def generate_weekly_brief_for_tenant(tenant_schema: str) -> dict[str, Any]:
    with schema_context(tenant_schema):
        report = WeeklyBriefGenerator().generate()
    return {"tenant_schema": tenant_schema, "report_uuid": str(report.uuid), "status": report.status}


@shared_task(name="weekly_brief.send_weekly_brief_email")  # type: ignore[untyped-decorator]
def send_weekly_brief_email(tenant_schema: str, report_uuid: str) -> dict[str, Any]:
    from django.utils import timezone

    with schema_context(tenant_schema):
        report = WeeklyBriefReport.objects.filter(uuid=report_uuid).first()
        if report is None:
            return {"ok": False, "error": "report not found"}
        config = WeeklyBriefConfig.objects.filter(pk=1).first()
        recipients = [e.strip() for e in (config.recipients if config else "").split(",") if e.strip()]
        if not recipients:
            return {"ok": False, "error": "no recipients configured"}
        send_mail(
            subject=f"Weekly Brief · {report.period_start} — {report.period_end}",
            message=report.plain_body,
            from_email=None,
            recipient_list=recipients,
            html_message=report.html_body,
            fail_silently=False,
        )
        report.status = WeeklyBriefReport.STATUS_DELIVERED
        report.delivered_at = timezone.now()  # type: ignore[assignment]
        report.save(update_fields=["status", "delivered_at"])
    return {"ok": True, "recipients": recipients}
