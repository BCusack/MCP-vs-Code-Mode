"""MCP servers under test. Add a new server here plus its tasks in tasks.py."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ServerSpec:
    name: str
    label: str  # how the prompt refers to it
    namespace: str  # Python object name in code mode
    connection: dict[str, Any]  # langchain-mcp-adapters connection dict


def get_server(name: str) -> ServerSpec:
    if name == "notion":
        token = os.environ.get("NOTION_TOKEN")
        if not token:
            raise SystemExit("NOTION_TOKEN is not set (see .env.example)")
        return ServerSpec(
            name="notion",
            label="the user's Notion workspace",
            namespace="notion",
            connection={
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@notionhq/notion-mcp-server@2.6.1"],  # version the published results ran on
                # Passed only to the child process; never logged or written to results.
                # The MCP SDK merges this over its safe default env (HOME, PATH, ...),
                # so other secrets (ANTHROPIC_API_KEY, LANGSMITH_*) stay out of the child.
                "env": {"NOTION_TOKEN": token},
            },
        )
    if name == "mock":
        return ServerSpec(
            name="mock",
            label="a Notion-like workspace",
            namespace="notion",
            connection={"transport": "stdio", "command": sys.executable, "args": ["-m", "bench.mock_server"]},
        )
    raise SystemExit(f"Unknown server {name!r}. Known: notion, mock")
