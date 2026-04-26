"""Addon manifest schema."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AddonManifest:
    name: str
    display_name: str
    version: str
    description: str = ""
    author: str = ""
    category: str = "general"
    tags: tuple[str, ...] = field(default_factory=tuple)
    pricing: dict[str, float] = field(default_factory=dict)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    permissions: tuple[str, ...] = field(default_factory=tuple)
    ui_entry_points: tuple[dict[str, str], ...] = field(default_factory=tuple)
