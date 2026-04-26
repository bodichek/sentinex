# Skill: Add MCP Integration

Use this skill when adding a new MCP server integration to Sentinex.

## When to Use

- Need to connect Sentinex to a new external system that has an MCP server
- Expanding data source coverage
- Adding enterprise integrations (Microsoft 365, Slack, HubSpot, etc.)

## Prerequisites

- MCP server exists and is production-ready
- OAuth credentials available (client ID, client secret)
- Clear understanding of what data the integration provides

## Steps

### 1. Evaluate the integration

Before implementing, confirm:
- Does the MCP server follow MCP standard?
- What authentication does it need?
- What's the rate limit?
- What data does it expose?
- Does it support EU-hosted option?

### 2. Create integration class

Location: `apps/data_access/mcp/integrations/<integration_name>.py`

```python
from apps.data_access.mcp.base import MCPIntegration

class Microsoft365Integration(MCPIntegration):
    name = "microsoft365"
    display_name = "Microsoft 365"
    description = "Connect to Outlook, OneDrive, Teams"

    # MCP server configuration
    mcp_server_config = {
        "type": "stdio",  # or "sse", "websocket"
        "command": "npx",
        "args": ["@modelcontextprotocol/server-microsoft365"],
    }

    # OAuth configuration
    oauth_config = {
        "provider": "microsoft",
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": [
            "offline_access",
            "Mail.Read",
            "Calendars.Read",
            "Files.Read",
        ],
        "redirect_uri_name": "mcp_oauth_callback",
    }

    # Available tools (for reference, actual list comes from MCP server)
    documented_tools = [
        "read_email",
        "list_calendar_events",
        "search_files",
    ]

    # Rate limits
    rate_limits = {
        "per_minute": 60,
        "per_hour": 3000,
    }
```

### 3. Add OAuth credentials

Environment variables in `.env`:
```
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
```

Add to settings:
```python
# config/settings/base.py

OAUTH_PROVIDERS = {
    "microsoft": {
        "client_id": env("MICROSOFT_CLIENT_ID"),
        "client_secret": env("MICROSOFT_CLIENT_SECRET"),
    },
}
```

### 4. Create connection UI

User flow:
1. User visits tenant settings → Integrations
2. Clicks "Connect Microsoft 365"
3. Redirected to Microsoft OAuth
4. Returns to callback URL
5. Credentials stored encrypted
6. Integration marked as active

Implementation points:
- View: `apps/core/views/integrations.py`
- URL: `/integrations/<integration_name>/connect/`
- Callback: `/integrations/<integration_name>/callback/`

### 5. Store credentials

Use the `Credential` model with django-cryptography:

```python
Credential.objects.update_or_create(
    tenant=request.tenant,
    integration="microsoft365",
    defaults={
        "oauth_tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
        },
        "is_active": True,
    },
)
```

Fields are automatically encrypted.

### 6. Register in MCP Gateway

Add to `apps/data_access/mcp/gateway.py`:

```python
INTEGRATIONS = {
    "google_workspace": GoogleWorkspaceIntegration,
    "microsoft365": Microsoft365Integration,  # New
}
```

### 7. Test the integration

#### Manual test

1. Connect integration via UI
2. Call MCP Gateway from shell:

```python
from apps.data_access.mcp.gateway import MCPGateway

gateway = MCPGateway(tenant=my_tenant)
result = gateway.call(
    integration="microsoft365",
    tool="list_calendar_events",
    params={"date": "2026-04-22"},
)
print(result)
```

#### Automated tests

```python
@pytest.mark.integration
def test_microsoft365_integration(tenant_with_connected_ms365, mock_mcp_server):
    gateway = MCPGateway(tenant=tenant_with_connected_ms365)
    result = gateway.call(
        integration="microsoft365",
        tool="list_calendar_events",
        params={"date": "2026-04-22"},
    )
    assert isinstance(result, list)
```

### 8. Add to sync pipelines (if periodic sync needed)

If the integration should sync data automatically:

Create Celery task:
```python
# apps/data_access/sync/microsoft365.py

from celery import shared_task
from apps.core.models import Organization

@shared_task
def sync_microsoft365_data(org_id):
    org = Organization.objects.get(pk=org_id)
    # Fetch data via gateway
    # Transform to metrics
    # Store as DataSnapshot
```

Schedule:
```python
# config/celery.py

app.conf.beat_schedule["sync_microsoft365"] = {
    "task": "apps.data_access.sync.microsoft365.sync_all_tenants",
    "schedule": crontab(minute=0),  # hourly
}
```

### 9. Update documentation

- Add to `docs/DATA_ACCESS.md` under "Supported MCP Servers"
- Document in addon docs if specific addons rely on it

## Verification Checklist

- [ ] Integration class created with correct config
- [ ] OAuth credentials in `.env` and settings
- [ ] Connection UI working (connect, disconnect)
- [ ] Credentials stored encrypted
- [ ] MCP Gateway can call integration
- [ ] Token refresh working
- [ ] Rate limiting configured
- [ ] Tests written (manual + automated)
- [ ] Documentation updated
