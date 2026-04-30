"""MIME-type-aware text extractors for Workspace artifacts."""

from __future__ import annotations

from apps.data_access.knowledge.extractors.base import (
    ExtractionResult,
    extract,
    register,
    supported_mime_types,
)

__all__ = ["ExtractionResult", "extract", "register", "supported_mime_types"]

# Trigger registration of built-in extractors
from apps.data_access.knowledge.extractors import (  # noqa: E402, F401
    gmail,
    google_docs,
    google_sheets,
    google_slides,
    pdf,
    plain_text,
)
