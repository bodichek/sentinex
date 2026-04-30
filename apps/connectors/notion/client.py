"""Notion MCP client — Streamable HTTP transport (mirrors Canva connector)."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)
NOTION_MCP_URL = "https://mcp.notion.com/mcp"


@dataclass
class ToolResult:
    is_error: bool
    text_blocks: list[str] = field(default_factory=list)
    structured: list[Any] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def first_json(self) -> Any:
        for blob in self.text_blocks:
            blob = blob.strip()
            if blob.startswith(("{", "[")):
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    continue
        return self.structured[0] if self.structured else None


async def _async_call_tool(
    access_token: str, tool: str, arguments: dict[str, Any] | None
) -> ToolResult:
    from mcp import ClientSession  # type: ignore[import-not-found]
    from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-not-found]

    headers = {"Authorization": f"Bearer {access_token}"}
    async with streamablehttp_client(NOTION_MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.call_tool(tool, arguments=arguments or {})

    text_blocks: list[str] = []
    structured: list[Any] = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text_blocks.append(getattr(block, "text", "") or "")
        else:
            structured.append(block)
    return ToolResult(
        is_error=bool(getattr(response, "isError", False)),
        text_blocks=text_blocks,
        structured=structured,
        raw=getattr(response, "model_dump", lambda: {})() or {},
    )


async def _async_list_tools(access_token: str) -> list[dict[str, Any]]:
    from mcp import ClientSession  # type: ignore[import-not-found]
    from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-not-found]

    headers = {"Authorization": f"Bearer {access_token}"}
    async with streamablehttp_client(NOTION_MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
    return [
        {
            "name": getattr(t, "name", ""),
            "description": getattr(t, "description", ""),
            "input_schema": getattr(t, "inputSchema", None),
        }
        for t in getattr(tools, "tools", []) or []
    ]


def _run(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return asyncio.get_running_loop().run_until_complete(coro)


def call_tool(access_token: str, tool: str, arguments: dict[str, Any] | None = None) -> ToolResult:
    return _run(_async_call_tool(access_token, tool, arguments))


def list_tools(access_token: str) -> list[dict[str, Any]]:
    return _run(_async_list_tools(access_token))
