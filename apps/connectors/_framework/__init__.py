"""Connector ingest framework.

Sits on top of the existing MCP layer (apps.data_access.mcp) which handles
OAuth, credential storage and tool-style calls. This package adds the
ETL ingest pipeline: rate limiting, retry, sync runs, provenance, identity
resolution hooks.

Import the specific module you need:
    from apps.connectors._framework.base_sync import BaseSync
    from apps.connectors._framework.identity_hook import resolve_person
    from apps.connectors._framework.provenance import ProvenanceMixin
    from apps.connectors._framework.rate_limit import TokenBucket
    from apps.connectors._framework.retry import retry_with_backoff
"""

default_app_config = "apps.connectors._framework.apps.ConnectorFrameworkConfig"
