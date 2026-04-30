"""Tests for the extractor registry and registration of built-in handlers."""

from __future__ import annotations

from apps.data_access.knowledge.extractors import (  # noqa: F401  (triggers registration)
    base,
    supported_mime_types,
)


def test_registry_contains_core_mime_types() -> None:
    mts = supported_mime_types()
    assert "application/vnd.google-apps.document" in mts
    assert "application/vnd.google-apps.spreadsheet" in mts
    assert "application/vnd.google-apps.presentation" in mts
    assert "application/pdf" in mts
    assert "text/plain" in mts
    assert "text/markdown" in mts


def test_unknown_mime_returns_none() -> None:
    assert base.extract("application/x-unknown", {"id": "abc"}) is None


def test_register_decorator_adds_new_mime() -> None:
    @base.register("test/special")
    def _h(meta: dict) -> base.ExtractionResult:
        return base.ExtractionResult(text="hi", metadata={"x": 1})

    res = base.extract("test/special", {})
    assert res is not None
    assert res.text == "hi"
    assert res.metadata["x"] == 1
