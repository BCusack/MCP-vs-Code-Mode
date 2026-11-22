"""Create the benchmark fixtures in Notion under NOTION_PARENT_PAGE_ID.

    uv run bench-seed            # create if missing
    uv run bench-seed --force    # archive the old sandbox and recreate
    uv run bench-seed --teardown # archive the sandbox

Writes IDs to .state/notion.json (git-ignored).
"""

from __future__ import annotations

import argparse
import json
import os

from dotenv import load_dotenv
from rich.console import Console

from . import fixture
from .notion_api import Notion, rich
from .tasks import STATE_FILE

console = Console()


def _norm(page_id: str) -> str:
    return page_id.strip().split("?")[0].split("-")[-1] if "notion.so" in page_id else page_id.strip()


def seed(n: Notion, parent: str) -> dict:
    sandbox = n.req("POST", "/pages", json={
        "parent": {"page_id": parent},
        "properties": {"title": {"title": rich(fixture.SANDBOX_TITLE)}},
        "children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich(
            "Auto-generated fixtures for the MCP vs Code Mode benchmark. Safe to delete.")}}],
    })
    console.print(f"sandbox page: {sandbox['id']}")

    meeting = n.req("POST", "/pages", json={
        "parent": {"page_id": sandbox["id"]},
        "properties": {"title": {"title": rich(fixture.MEETING_PAGE)}},
        "children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich(t)}}
                     for t in fixture.meeting_notes()],
    })

    db = n.req("POST", "/databases", json={
        "parent": {"type": "page_id", "page_id": sandbox["id"]},
        "title": rich(fixture.DB_TITLE),
        "properties": {
            "Name": {"title": {}},
            "Status": {"select": {"options": [{"name": s} for s in fixture.STATUSES]}},
            "Owner": {"select": {"options": [{"name": o} for o in fixture.OWNERS]}},
            "Points": {"number": {"format": "number"}},
            "Due": {"date": {}},
        },
    })
    ids = {}
    for i, p in enumerate(fixture.projects(), 1):
        page = n.req("POST", "/pages", json={"parent": {"database_id": db["id"]}, "properties": {
            "Name": {"title": rich(p["Name"])},
            "Status": {"select": {"name": p["Status"]}},
            "Owner": {"select": {"name": p["Owner"]}},
            "Points": {"number": p["Points"]},
            "Due": {"date": {"start": p["Due"]}},
        }})
        ids[p["Name"]] = page["id"]
        console.print(f"  rows {i}/{fixture.N_PROJECTS}", end="\r")
    console.print()
    return {"sandbox_page_id": sandbox["id"], "meeting_page_id": meeting["id"],
            "database_id": db["id"], "project_ids": ids}


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--teardown", action="store_true")
    a = ap.parse_args()

    n = Notion()
    if STATE_FILE.exists() and (a.force or a.teardown):
        old = json.loads(STATE_FILE.read_text())
        n.archive(old["sandbox_page_id"])
        STATE_FILE.unlink()
        console.print("archived old sandbox")
    if a.teardown:
        return
    if STATE_FILE.exists():
        console.print(f"Fixtures already exist ({STATE_FILE}). Use --force to recreate.")
        return
    parent = os.environ.get("NOTION_PARENT_PAGE_ID")
    if not parent:
        raise SystemExit("NOTION_PARENT_PAGE_ID is not set (see .env.example)")
    state = seed(n, _norm(parent))
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))
    console.print(f"[green]Seeded. State written to {STATE_FILE}[/green]")


if __name__ == "__main__":
    main()
