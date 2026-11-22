"""Offline stand-in for Notion: same fixture data, verbose Notion-shaped responses, 10-row pages.

Lets you smoke-test the harness (and compare modes) without a Notion account:
    uv run bench-run --server mock --runs 1
"""

from __future__ import annotations

import uuid

from mcp.server.fastmcp import FastMCP

from bench import fixture

mcp = FastMCP("mock-notion")

_ROWS = [
    {
        "object": "page",
        "id": str(uuid.UUID(int=i + 1)),
        "created_time": "2026-01-01T00:00:00.000Z",
        "last_edited_time": "2026-01-02T00:00:00.000Z",
        "archived": False,
        "url": f"https://www.notion.so/mock-{i + 1}",
        "parent": {"type": "data_source_id", "data_source_id": "ds-bench-projects"},
        "properties": {
            "Name": {"id": "title", "type": "title", "title": [{"type": "text", "plain_text": p["Name"], "annotations": {"bold": False, "italic": False, "code": False, "color": "default"}}]},
            "Status": {"id": "st", "type": "select", "select": {"name": p["Status"], "color": "default"}},
            "Owner": {"id": "ow", "type": "select", "select": {"name": p["Owner"], "color": "default"}},
            "Points": {"id": "pt", "type": "number", "number": p["Points"]},
            "Due": {"id": "du", "type": "date", "date": {"start": p["Due"], "end": None, "time_zone": None}},
        },
    }
    for i, p in enumerate(fixture.projects())
]
_MEETING_ID = "00000000-0000-0000-0000-00000000beef"


@mcp.tool()
def search(query: str = "") -> dict:
    """Search pages and data sources by title."""
    results = []
    if query.lower() in fixture.MEETING_PAGE.lower():
        results.append({"object": "page", "id": _MEETING_ID, "properties": {"title": {"title": [{"plain_text": fixture.MEETING_PAGE}]}}})
    if query.lower() in fixture.DB_TITLE.lower():
        results.append({"object": "data_source", "id": "ds-bench-projects", "title": [{"plain_text": fixture.DB_TITLE}]})
    return {"object": "list", "results": results, "has_more": False}


@mcp.tool()
def query_data_source(data_source_id: str, start_cursor: str | None = None, page_size: int = 10) -> dict:
    """Query rows of a data source (database). Paginated: max 10 rows per call; pass next_cursor as start_cursor."""
    if data_source_id != "ds-bench-projects":
        raise ValueError("unknown data_source_id")
    start = int(start_cursor or 0)
    size = max(1, min(page_size, 10))
    chunk = _ROWS[start:start + size]
    nxt = start + size
    return {"object": "list", "results": chunk, "has_more": nxt < len(_ROWS), "next_cursor": str(nxt) if nxt < len(_ROWS) else None}


@mcp.tool()
def get_block_children(block_id: str) -> dict:
    """List the content blocks of a page."""
    if block_id != _MEETING_ID:
        return {"object": "list", "results": []}
    return {"object": "list", "results": [
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"plain_text": t}]}}
        for t in fixture.meeting_notes()
    ]}


if __name__ == "__main__":
    mcp.run()
