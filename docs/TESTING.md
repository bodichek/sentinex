# Testing Strategy

## Overview

Sentinex uses `pytest` with `pytest-django` as the testing framework. Tests are organized by scope:
- **Unit tests**: per-app, fast, isolated, mock external dependencies
- **Integration tests**: per-feature, hit real database and Redis, mock external APIs
- **End-to-end tests**: full stack including agents and data access

## Principles

1. **Write tests after implementation** (not TDD strict) during MVP phase
2. **Every Insight Function has at least one unit test**
3. **Every addon has at least one integration test**
4. **Tenant isolation has dedicated tests**
5. **Fast feedback**: unit tests should run in seconds, full suite under 2 minutes
6. **Meaningful coverage, not coverage numbers**: 70% target, but quality over quantity

## Test Organization

```
sentinex/
├── apps/
│   ├── core/
│   │   └── tests/
│   │       ├── test_models.py
│   │       ├── test_services.py
│   │       └── test_views.py
│   ├── agents/
│   │   └── tests/
│   │       ├── test_orchestrator.py
│   │       ├── test_specialists.py
│   │       ├── test_guardrails.py
│   │       └── test_llm_gateway.py
│   ├── data_access/
│   │   └── tests/
│   │       ├── test_insight_functions.py
│   │       ├── test_mcp_gateway.py
│   │       └── test_sync_pipelines.py
│   └── addons/
│       └── weekly_brief/
│           └── tests/
│               ├── test_services.py
│               └── test_integration.py
├── tests/                      # Integration tests at repo root
│   ├── conftest.py             # Shared fixtures
│   ├── test_tenant_isolation.py
│   ├── test_end_to_end_weekly_brief.py
│   └── test_addon_activation.py
└── pyproject.toml              # pytest configuration
```

## Running Tests

### All tests

```bash
poetry run pytest
```

### Specific app

```bash
poetry run pytest apps/agents/
```

### Specific test

```bash
poetry run pytest apps/agents/tests/test_orchestrator.py::test_handle_query
```

### With coverage

```bash
poetry run pytest --cov=apps --cov-report=html
```

HTML report at `htmlcov/index.html`.

### Fast mode (skip slow tests)

```bash
poetry run pytest -m "not slow"
```

### Integration tests only

```bash
poetry run pytest -m integration
```

### Parallel execution

```bash
poetry run pytest -n auto
```

Requires `pytest-xdist`.

## Configuration

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py", "*_test.py"]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "tenant_isolation: tenant isolation tests",
]
addopts = [
    "--strict-markers",
    "--tb=short",
    "--reuse-db",
]
```

## Fixtures

### Shared Fixtures

`tests/conftest.py`:

```python
import pytest
from django_tenants.utils import schema_context
from apps.core.models import Tenant, Domain

@pytest.fixture
def tenant(db):
    tenant = Tenant.objects.create(
        schema_name="test_tenant",
        name="Test Tenant",
    )
    Domain.objects.create(
        tenant=tenant,
        domain="test.sentinex.local",
        is_primary=True,
    )
    return tenant

@pytest.fixture
def tenant_context(tenant):
    with schema_context(tenant.schema_name):
        yield tenant

@pytest.fixture
def organization(tenant_context):
    from apps.core.models import Organization
    return Organization.objects.create(name="Test Org")

@pytest.fixture
def user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )

@pytest.fixture
def authenticated_client(client, user):
    client.force_login(user)
    return client
```

### Mock Fixtures

```python
@pytest.fixture
def mock_llm(mocker):
    """Mock the LLM gateway to return a fixed response."""
    mock = mocker.patch("apps.agents.llm_gateway.complete")
    mock.return_value = {
        "content": "Mocked LLM response",
        "model": "claude-sonnet-4",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    return mock

@pytest.fixture
def mock_mcp_gateway(mocker):
    """Mock MCP Gateway to return fixed data."""
    mock = mocker.patch("apps.data_access.mcp.gateway.MCPGateway.call")
    mock.return_value = {"result": "mocked"}
    return mock
```

## Unit Test Examples

### Testing Insight Functions

```python
# apps/data_access/insight_functions/tests/test_strategic.py

import pytest
from datetime import date
from apps.data_access.insight_functions import get_weekly_metrics

@pytest.mark.django_db
def test_get_weekly_metrics_with_data(organization_with_metrics):
    result = get_weekly_metrics(organization_with_metrics)

    assert result.period_start is not None
    assert result.period_end == date.today()
    assert result.data_quality == "high"
    assert "revenue" in result.key_indicators

@pytest.mark.django_db
def test_get_weekly_metrics_with_no_data(organization):
    result = get_weekly_metrics(organization)

    assert result.data_quality == "missing"
    assert result.key_indicators == {}
```

### Testing Agents

```python
# apps/agents/tests/test_orchestrator.py

import pytest
from apps.agents.orchestrator import Orchestrator

def test_orchestrator_classifies_intent(mock_llm):
    orch = Orchestrator()
    intent = orch.classify("What's our cash runway?")

    assert intent == "finance"

@pytest.mark.django_db
def test_orchestrator_handles_query(organization, user, mock_llm):
    orch = Orchestrator()
    response = orch.handle(
        query="How is Q1 going?",
        context={"organization": organization, "user": user},
    )

    assert response is not None
    assert mock_llm.called
```

### Testing Guardrails

```python
# apps/agents/tests/test_guardrails.py

from apps.agents.guardrails import check_cost_budget, check_scope, mask_pii

def test_cost_budget_rejects_over_limit():
    result = check_cost_budget(
        estimated_cost=100,
        budget_remaining=50,
    )
    assert result.passed is False
    assert "budget" in result.reason.lower()

def test_pii_masking_redacts_emails():
    text = "Contact John at john@example.com for details"
    masked = mask_pii(text)

    assert "john@example.com" not in masked
    assert "[EMAIL_0]" in masked
```

## Integration Test Examples

### End-to-End Weekly Brief

```python
# tests/test_end_to_end_weekly_brief.py

import pytest
from django_tenants.utils import schema_context
from apps.addons.weekly_brief.services import WeeklyBriefGenerator

@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_weekly_brief_full_flow(tenant, organization, mock_llm, mock_mcp_gateway):
    with schema_context(tenant.schema_name):
        generator = WeeklyBriefGenerator(organization)
        brief = generator.generate()

        assert brief is not None
        assert "metrics" in brief
        assert "anomalies" in brief
        assert "commitments" in brief
```

### Tenant Isolation

```python
# tests/test_tenant_isolation.py

import pytest
from django_tenants.utils import schema_context
from apps.core.models import Tenant, Organization

@pytest.mark.tenant_isolation
@pytest.mark.django_db(transaction=True)
def test_organizations_isolated_between_tenants(db):
    # Tenant A
    tenant_a = Tenant.objects.create(schema_name="a", name="A")
    with schema_context("a"):
        Organization.objects.create(name="Org A")

    # Tenant B
    tenant_b = Tenant.objects.create(schema_name="b", name="B")
    with schema_context("b"):
        Organization.objects.create(name="Org B")

    # Verify isolation
    with schema_context("a"):
        orgs = list(Organization.objects.all())
        assert len(orgs) == 1
        assert orgs[0].name == "Org A"

    with schema_context("b"):
        orgs = list(Organization.objects.all())
        assert len(orgs) == 1
        assert orgs[0].name == "Org B"
```

## Test Data Strategy

### Fixtures Over Setup Code

Prefer pytest fixtures for reusable test data:

```python
@pytest.fixture
def organization_with_metrics(organization):
    DataSnapshot.objects.create(
        organization=organization,
        source="finance",
        metrics={"cash": 1000000, "burn": 100000},
    )
    return organization
```

### Factories (factory_boy)

For complex objects:

```python
# apps/core/tests/factories.py

import factory
from apps.core.models import Organization

class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")
    industry = "Technology"
```

Use in tests:

```python
def test_something(db):
    org = OrganizationFactory()
    assert org.name.startswith("Org")
```

## Performance Testing

Not in MVP scope. Add when we have production traffic patterns.

## CI Integration

GitHub Actions runs tests on every PR. See `.github/workflows/ci.yml`.

Required before merge:
- All tests pass
- Linting passes (`ruff check`)
- Type checking passes (`mypy`)

## Debugging Tests

### Run with pdb

```bash
poetry run pytest --pdb
```

Drops into debugger on first failure.

### Increase verbosity

```bash
poetry run pytest -vvv
```

### Show print statements

```bash
poetry run pytest -s
```

### Capture logs

```python
def test_something(caplog):
    with caplog.at_level("INFO"):
        do_thing()

    assert "expected log message" in caplog.text
```

## Common Pitfalls

1. **Forgetting tenant context**: tests that create tenant data must use `schema_context`
2. **Database leaks**: always use `@pytest.mark.django_db` or transaction
3. **Real LLM calls in tests**: always mock LLM gateway unless explicitly testing integration
4. **Flaky tests**: if a test is flaky, investigate and fix — don't retry it
5. **Slow tests**: mark with `@pytest.mark.slow`, skip in regular runs
