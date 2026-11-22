"""Tiny Notion REST helper used ONLY for seeding fixtures and verifying task results.

The agents never use this: they go through the Notion MCP server.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

NOTION_VERSION = "2022-06-28"  # stable, still supported; fine for fixtures


class Notion:
    def __init__(self, token: str | None = None):
        token = token or os.environ.get("NOTION_TOKEN")
        if not token:
            raise SystemExit("NOTION_TOKEN is not set (see .env.example)")
        self.http = httpx.Client(
            base_url="https://api.notion.com/v1",
            headers={"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION},
            timeout=30,
        )

    def req(self, method: str, path: str, **kw: Any) -> dict[str, Any]:
        for attempt in range(6):
            r = self.http.request(method, path, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(float(r.headers.get("Retry-After", 1 + attempt)))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Notion {method} {path} -> {r.status_code}: {r.text[:500]}")
            return r.json()
        raise RuntimeError(f"Notion {method} {path}: retries exhausted")

    def children(self, block_id: str) -> list[dict[str, Any]]:
        out, cursor = [], None
        while True:
            params = {"page_size": 100} | ({"start_cursor": cursor} if cursor else {})
            data = self.req("GET", f"/blocks/{block_id}/children", params=params)
            out += data["results"]
            if not data.get("has_more"):
                return out
            cursor = data["next_cursor"]

    def archive(self, page_id: str) -> None:
        self.req("PATCH", f"/pages/{page_id}", json={"archived": True})


def rich(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text}}]


def block_text(block: dict[str, Any]) -> str:
    body = block.get(block["type"], {})
    if "rich_text" in body:
        return "".join(t.get("plain_text", "") for t in body["rich_text"])
    if "title" in body:
        return body["title"]
    return ""
