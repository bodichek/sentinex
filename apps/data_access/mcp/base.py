"""Abstract interface every MCP integration must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from apps.data_access.models import Integration


@dataclass
class MCPCallResult:
    ok: bool
    data: Any = None
    error: str = ""


class MCPIntegration(ABC):
    provider: str = ""

    @abstractmethod
    def authorization_url(self, state: str, redirect_uri: str) -> str: ...

    @abstractmethod
    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]: ...

    @abstractmethod
    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult: ...
