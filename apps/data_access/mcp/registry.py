"""Default MCP integration registry — single source of truth.

Avoids the previous pattern of every caller building its own dict and missing
new providers. Use ``default_gateway()`` everywhere instead of ``MCPGateway({...})``.
"""

from __future__ import annotations

from apps.data_access.mcp.base import MCPIntegration
from apps.data_access.mcp.gateway import MCPGateway
from apps.data_access.mcp.integrations.google_workspace import GoogleWorkspaceIntegration
from apps.data_access.mcp.integrations.google_workspace_dwd import (
    GoogleWorkspaceDWDIntegration,
)
from apps.data_access.mcp.integrations.slack import SlackIntegration


def default_integrations() -> dict[str, MCPIntegration]:
    return {
        "google_workspace": GoogleWorkspaceIntegration(),
        "google_workspace_dwd": GoogleWorkspaceDWDIntegration(),
        "slack": SlackIntegration(),
    }


def default_gateway() -> MCPGateway:
    return MCPGateway(default_integrations())
