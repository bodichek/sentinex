# Skill: Add Insight Function

Use this skill when adding a new Insight Function to the Data Access Layer.

## When to Use

- Need a new business-level query that aggregates data for agents or addons
- Agents or addons need structured access to synced data
- Encoding a methodology (Scaling Up, EOS, OKR, custom) as executable logic

## Insight Function Rules

Recall from `docs/DATA_ACCESS.md`:
- Pure Python functions
- Typed inputs and outputs
- Framework-agnostic (no methodology branding in function names)
- Unit tested with mock data
- Cached where appropriate

## Steps

### 1. Identify the output type

Decide what the function returns. Define a dataclass or Pydantic model.

Location: `apps/data_access/insight_functions/types/<category>.py`

Example:
```python
from dataclasses import dataclass
from datetime import date

@dataclass
class MarginTrends:
    period_start: date
    period_end: date
    gross_margin_pct: float
    trend_direction: str  # "improving", "stable", "declining"
    trend_confidence: str  # "high", "medium", "low"
    data_points_count: int
```

### 2. Categorize the function

Place it in the appropriate category file:
- `strategic.py` — high-level business analysis
- `finance.py` — financial metrics
- `people.py` — team and organizational signals
- `customer.py` — pipeline, deal, customer health
- `operations.py` — projects, commitments, bottlenecks

If the category doesn't fit, create a new file.

### 3. Implement the function

```python
from apps.core.models import Organization
from .types.finance import MarginTrends

def get_margin_trends(
    org: Organization,
    period_months: int = 6,
) -> MarginTrends:
    """Analyze gross margin trends over a period.

    Args:
        org: The organization.
        period_months: Lookback period.

    Returns:
        MarginTrends with trend analysis.

    Raises:
        InsufficientData: If fewer than 3 months of data exist.
    """
    # Fetch data from synced metrics
    # Apply methodology
    # Return typed result
    ...
```

Guidelines:
- Function name: `get_<noun>_<qualifier>`
- No side effects (pure function)
- Explicit about data requirements
- Raise `InsufficientData` if not enough data
- Never return None — use typed result or raise

### 4. Add caching (if expensive)

For functions that aggregate lots of data:

```python
from apps.core.cache import cache_result

@cache_result(ttl=3600, key_prefix="margin_trends")
def get_margin_trends(org: Organization, period_months: int = 6) -> MarginTrends:
    ...
```

Cache key includes tenant (via current schema) and function arguments automatically.

### 5. Register the function

Add to `apps/data_access/insight_functions/__init__.py`:

```python
from .finance import get_margin_trends

__all__ = [
    # ... existing functions
    "get_margin_trends",
]

INSIGHT_FUNCTIONS = {
    # ... existing entries
    "get_margin_trends": get_margin_trends,
}
```

### 6. Write tests

Location: `apps/data_access/insight_functions/tests/test_<category>.py`

Required tests:
- Happy path (full data available)
- Edge case: no data (raises InsufficientData)
- Edge case: partial data
- Edge case: boundary conditions

Example:
```python
import pytest
from apps.data_access.insight_functions import get_margin_trends
from apps.data_access.exceptions import InsufficientData

@pytest.mark.django_db
def test_margin_trends_with_full_data(org_with_financial_history):
    result = get_margin_trends(org_with_financial_history)

    assert result.data_points_count >= 6
    assert result.trend_direction in ("improving", "stable", "declining")
    assert 0 <= result.gross_margin_pct <= 100

@pytest.mark.django_db
def test_margin_trends_with_no_data(organization):
    with pytest.raises(InsufficientData):
        get_margin_trends(organization)
```

### 7. Document in docstring

Good docstrings explain:
- What the function computes
- Input parameters and their constraints
- Return value structure
- When it raises exceptions
- Assumptions and caveats

### 8. (Optional) Reference in agent prompts

If an agent should use this function, reference it in the specialist's YAML prompt:

```yaml
# apps/agents/prompts/finance_specialist.yaml

tools_available:
  - get_cash_runway_projection
  - get_margin_trends  # New
```

## Verification Checklist

- [ ] Function is pure (no side effects)
- [ ] Inputs and outputs typed
- [ ] Docstring explains behavior
- [ ] Raises `InsufficientData` appropriately
- [ ] Tests cover happy path, edge cases, error cases
- [ ] Registered in `INSIGHT_FUNCTIONS` dict
- [ ] Caching added if expensive
- [ ] No framework-specific branding (Scaling Up, EOS, OKR) in name
- [ ] Function name follows `get_<noun>_<qualifier>` pattern
