"""Weekly Brief service tests with mocked LLM."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from django_tenants.utils import schema_context

from apps.addons.weekly_brief.models import WeeklyBriefReport
from apps.addons.weekly_brief.services import WeeklyBriefGenerator
from apps.data_access.models import ManualKPI


def _llm_stub(prompt, **kwargs):  # type: ignore[no-untyped-def]
    return SimpleNamespace(content="EXEC SUMMARY")


@pytest.mark.django_db(transaction=True)
class TestWeeklyBriefGenerator:
    def test_generates_report_with_mocked_llm(self) -> None:
        with schema_context("test_tenant"):
            WeeklyBriefReport.objects.all().delete()
            ManualKPI.objects.all().delete()
            from datetime import date
            ManualKPI.objects.create(name="cash_on_hand", value=Decimal("500000"), period_end=date.today())
            ManualKPI.objects.create(name="monthly_expenses", value=Decimal("100000"), period_end=date.today())

            report = WeeklyBriefGenerator(llm=_llm_stub).generate()

            assert report.status == WeeklyBriefReport.STATUS_GENERATED
            assert report.content["summary"] == "EXEC SUMMARY"
            assert "cashflow" in report.content["sections"]
            assert report.html_body
            assert report.plain_body

    def test_idempotent_same_week(self) -> None:
        with schema_context("test_tenant"):
            WeeklyBriefReport.objects.all().delete()
            ManualKPI.objects.all().delete()
            from datetime import date
            ManualKPI.objects.create(name="cash_on_hand", value=Decimal("1"), period_end=date.today())
            ManualKPI.objects.create(name="monthly_expenses", value=Decimal("1"), period_end=date.today())

            r1 = WeeklyBriefGenerator(llm=_llm_stub).generate()
            r2 = WeeklyBriefGenerator(llm=_llm_stub).generate()
            assert r1.pk == r2.pk
            assert WeeklyBriefReport.objects.filter(
                period_start=r1.period_start, period_end=r1.period_end
            ).count() == 1


@pytest.mark.django_db
class TestManifestDiscovery:
    def test_addon_discovered(self) -> None:
        from apps.core.addons import registry
        registry.discover(force=True)
        manifest = registry.get("weekly_brief")
        assert manifest is not None
        assert manifest.display_name == "CEO Weekly Brief"
