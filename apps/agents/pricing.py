"""Per-model LLM pricing (USD per million tokens).

Update when Anthropic pricing changes. Cost calculation is the single
source of truth for LLM billing — Insight Functions / gateway read from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings


@dataclass(frozen=True)
class ModelPricing:
    input_per_million_usd: Decimal
    output_per_million_usd: Decimal


# Per Anthropic pricing as of 2026-04. Verify at https://www.anthropic.com/pricing.
PRICING: dict[str, ModelPricing] = {
    "claude-sonnet-4-20250514": ModelPricing(Decimal("3.00"), Decimal("15.00")),
    "claude-sonnet-4-6": ModelPricing(Decimal("3.00"), Decimal("15.00")),
    "claude-opus-4-7": ModelPricing(Decimal("15.00"), Decimal("75.00")),
    "claude-haiku-4-5-20251001": ModelPricing(Decimal("1.00"), Decimal("5.00")),
}

# Aliases accepted by the gateway's model router.
ALIASES: dict[str, str] = {
    "sonnet": "claude-sonnet-4-20250514",
    "haiku": "claude-haiku-4-5-20251001",
    "opus": "claude-opus-4-7",
}


def resolve_model(name: str) -> str:
    return ALIASES.get(name, name)


def compute_cost_czk(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Return total cost in CZK using ``settings.USD_TO_CZK``."""
    pricing = PRICING.get(model)
    if pricing is None:
        return Decimal("0")
    usd = (
        pricing.input_per_million_usd * Decimal(input_tokens)
        + pricing.output_per_million_usd * Decimal(output_tokens)
    ) / Decimal("1000000")
    return (usd * Decimal(str(settings.USD_TO_CZK))).quantize(Decimal("0.0001"))
