"""Default MCP integration registry — single source of truth.

Avoids the previous pattern of every caller building its own dict and missing
new providers. Use ``default_gateway()`` everywhere instead of ``MCPGateway({...})``.
"""

from __future__ import annotations

from apps.connectors.asana.integration import AsanaIntegration
from apps.connectors.basecamp.integration import BasecampIntegration
from apps.connectors.caflou.integration import CaflouIntegration
from apps.connectors.calendly.integration import CalendlyIntegration
from apps.connectors.canva.integration import CanvaIntegration
from apps.connectors.dropbox.integration import DropboxIntegration
from apps.connectors.ecomail.integration import EcomailIntegration
from apps.connectors.fapi.integration import FapiIntegration
from apps.connectors.hubspot.integration import HubspotIntegration
from apps.connectors.jira.integration import JiraIntegration
from apps.connectors.mailchimp.integration import MailchimpIntegration
from apps.connectors.microsoft365.integration import Microsoft365Integration
from apps.connectors.notion.integration import NotionIntegration
from apps.connectors.pipedrive.integration import PipedriveIntegration
from apps.connectors.raynet.integration import RaynetIntegration
from apps.connectors.salesforce.integration import SalesforceIntegration
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
        "raynet": RaynetIntegration(),
        "caflou": CaflouIntegration(),
        "ecomail": EcomailIntegration(),
        "fapi": FapiIntegration(),
        "microsoft365": Microsoft365Integration(),
        "salesforce": SalesforceIntegration(),
        "asana": AsanaIntegration(),
        "basecamp": BasecampIntegration(),
        "mailchimp": MailchimpIntegration(),
        "calendly": CalendlyIntegration(),
        "hubspot": HubspotIntegration(),
        "jira": JiraIntegration(),
        "notion": NotionIntegration(),
        "dropbox": DropboxIntegration(),
    }


def default_gateway() -> MCPGateway:
    return MCPGateway(default_integrations())
