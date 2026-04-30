"""Default MCP integration registry — single source of truth.

Avoids the previous pattern of every caller building its own dict and missing
new providers. Use ``default_gateway()`` everywhere instead of ``MCPGateway({...})``.
"""

from __future__ import annotations

from apps.connectors.canva.integration import CanvaIntegration
from apps.connectors.pipedrive.integration import PipedriveIntegration
from apps.connectors.slack.integration import SlackIntegration
from apps.connectors.smartemailing.integration import SmartEmailingIntegration
from apps.connectors.trello.integration import TrelloIntegration
from apps.data_access.mcp.base import MCPIntegration
from apps.data_access.mcp.gateway import MCPGateway
from apps.data_access.mcp.integrations.google_workspace import GoogleWorkspaceIntegration
from apps.data_access.mcp.integrations.google_workspace_dwd import (
    GoogleWorkspaceDWDIntegration,
)


def default_integrations() -> dict[str, MCPIntegration]:
    return {
        "google_workspace": GoogleWorkspaceIntegration(),
        "google_workspace_dwd": GoogleWorkspaceDWDIntegration(),
        "slack": SlackIntegration(),
        "smartemailing": SmartEmailingIntegration(),
        "pipedrive": PipedriveIntegration(),
        "canva": CanvaIntegration(),
        "trello": TrelloIntegration(),
    }


def default_gateway() -> MCPGateway:
    return MCPGateway(default_integrations())
