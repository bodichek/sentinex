"""Weekly Brief addon manifest."""

from __future__ import annotations

from apps.core.addons import AddonManifest

manifest = AddonManifest(
    name="weekly_brief",
    display_name="CEO Weekly Brief",
    version="0.1.0",
    description="Pondělní ranní brief: klíčové metriky, anomálie a priority na další týden.",
    author="Sentinex",
    category="reporting",
    tags=("brief", "ceo", "email"),
    pricing={"monthly_czk": 4900.0, "setup_czk": 0.0},
    dependencies=(),
    permissions=("weekly_brief.view", "weekly_brief.configure"),
    ui_entry_points=(
        {"label": "Weekly Brief", "url_name": "weekly_brief:home"},
    ),
)
