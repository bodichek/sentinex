"""PDF export for a WeeklyBriefReport. Uses weasyprint when available."""

from __future__ import annotations

from apps.addons.weekly_brief.models import WeeklyBriefReport


class PDFGenerationError(RuntimeError):
    pass


def render_report_pdf(report: WeeklyBriefReport) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise PDFGenerationError("weasyprint not installed") from exc
    except OSError as exc:
        # Missing GTK on Windows — documented limitation.
        raise PDFGenerationError(f"weasyprint runtime unavailable: {exc}") from exc

    try:
        return bytes(HTML(string=report.html_body).write_pdf())
    except Exception as exc:
        raise PDFGenerationError(f"PDF generation failed: {exc}") from exc
