"""Extractor registry: maps MIME type → handler returning ExtractionResult."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractionResult:
    text: str
    truncated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


Extractor = Callable[[dict[str, Any]], ExtractionResult]
_REGISTRY: dict[str, Extractor] = {}


def register(*mime_types: str) -> Callable[[Extractor], Extractor]:
    def deco(fn: Extractor) -> Extractor:
        for mt in mime_types:
            _REGISTRY[mt] = fn
        return fn

    return deco


def supported_mime_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def extract(mime_type: str, file_meta: dict[str, Any]) -> ExtractionResult | None:
    """Run the extractor matching ``mime_type``; return None if unsupported."""
    handler = _REGISTRY.get(mime_type)
    if handler is None:
        return None
    return handler(file_meta)
