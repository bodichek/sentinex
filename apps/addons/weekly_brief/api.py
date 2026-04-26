"""Weekly Brief API endpoints."""

from __future__ import annotations

from typing import ClassVar

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.addons.weekly_brief.models import WeeklyBriefReport
from apps.addons.weekly_brief.services import WeeklyBriefGenerator


class GenerateView(APIView):
    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        report = WeeklyBriefGenerator().generate()
        return Response(
            {"uuid": str(report.uuid), "status": report.status},
            status=status.HTTP_201_CREATED,
        )


class ReportsView(APIView):
    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        reports = WeeklyBriefReport.objects.all()[:50]
        return Response(
            [
                {
                    "uuid": str(r.uuid),
                    "period_start": r.period_start.isoformat(),
                    "period_end": r.period_end.isoformat(),
                    "status": r.status,
                }
                for r in reports
            ]
        )
