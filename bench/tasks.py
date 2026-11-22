"""Benchmark tasks. Each is run once per mode with identical prompts; checks are deterministic."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import fixture

STATE_FILE = Path(__file__).resolve().parent.parent / ".state" / "notion.json"


@dataclass
class Ctx:
    server: str
    run_tag: str  # unique per run, e.g. "code-write-2"
    state: dict[str, Any]  # Notion IDs from the seeder ({} for mock)


@dataclass(frozen=True)
class Task:
    id: str
    kind: str  # read | aggregate | write
    prompt: Callable[[Ctx], str]
    check: Callable[[str, Ctx], tuple[bool, str]]
    servers: tuple[str, ...] = ("notion", "mock")
    cleanup: Callable[[Ctx], None] | None = None


def _numbers(text: str) -> list[int]:
    text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text.replace(",", ""))  # ignore dates
    return [int(n) for n in re.findall(r"(?<![\w.])\d+(?!\.?\d)(?!\w)", text)]


# ---- read / aggregate tasks -------------------------------------------------

def _lookup_check(ans: str, ctx: Ctx) -> tuple[bool, str]:
    ok = fixture.CODE_WORD in ans
    return ok, "" if ok else f"expected {fixture.CODE_WORD}"


_OWNER, _STATUS = "Diego", "In progress"


def _agg_check(ans: str, ctx: Ctx) -> tuple[bool, str]:
    exp = fixture.expected_points(_OWNER, _STATUS)
    ok = exp in _numbers(ans)
    return ok, "" if ok else f"expected {exp}"


def _blocked_check(ans: str, ctx: Ctx) -> tuple[bool, str]:
    exp = fixture.expected_names("Blocked")
    missing = [n for n in exp if n.lower() not in ans.lower()]
    extra = [p["Name"] for p in fixture.projects() if p["Status"] != "Blocked" and p["Name"].lower() in ans.lower()]
    ok = not missing and not extra
    return ok, "" if ok else f"missing={missing} extra={extra}"


def _overdue_check(ans: str, ctx: Ctx) -> tuple[bool, str]:
    owner, n = fixture.owner_with_most_overdue()
    ok = owner.lower() in ans.lower() and n in _numbers(ans)
    return ok, "" if ok else f"expected {owner} with {n}"


# ---- write tasks (Notion only; verified via REST, then cleaned up) ----------

def _report_title(ctx: Ctx) -> str:
    return f"Bench Report {ctx.run_tag}"


def _find_child_page(ctx: Ctx, title: str) -> str | None:
    from .notion_api import Notion

    for b in Notion().children(ctx.state["sandbox_page_id"]):
        if b["type"] == "child_page" and b["child_page"]["title"].strip() == title:
            return b["id"]
    return None


def _write_check(ans: str, ctx: Ctx) -> tuple[bool, str]:
    from .notion_api import Notion, block_text

    pid = _find_child_page(ctx, _report_title(ctx))
    if not pid:
        return False, "report page not found under sandbox page"
    blocks = Notion().children(pid)
    bullets = [block_text(b) for b in blocks if b["type"] == "bulleted_list_item"]
    want = fixture.top_points(3)
    missing = [w for w in want if not any(w.lower() in b.lower() for b in bullets)]
    ok = not missing and len(bullets) == 3
    return ok, "" if ok else f"bullets={bullets} missing={missing}"


def _write_cleanup(ctx: Ctx) -> None:
    from .notion_api import Notion

    if pid := _find_child_page(ctx, _report_title(ctx)):
        Notion().archive(pid)


_UPDATE_TARGET = fixture.projects()[3]["Name"]


def _update_check(ans: str, ctx: Ctx) -> tuple[bool, str]:
    from .notion_api import Notion

    page = Notion().req("GET", f"/pages/{ctx.state['project_ids'][_UPDATE_TARGET]}")
    pts = page["properties"]["Points"]["number"]
    status = page["properties"]["Status"]["select"]["name"]
    ok = pts == 99 and status == "Done"
    return ok, "" if ok else f"Points={pts} Status={status}"


def _update_cleanup(ctx: Ctx) -> None:
    from .notion_api import Notion

    orig = next(p for p in fixture.projects() if p["Name"] == _UPDATE_TARGET)
    Notion().req("PATCH", f"/pages/{ctx.state['project_ids'][_UPDATE_TARGET]}", json={"properties": {
        "Points": {"number": orig["Points"]}, "Status": {"select": {"name": orig["Status"]}}}})


TASKS: list[Task] = [
    Task(
        "lookup", "read",
        lambda c: f"Find the page titled '{fixture.MEETING_PAGE}' and tell me the launch code word mentioned in it.",
        _lookup_check,
    ),
    Task(
        "aggregate", "aggregate",
        lambda c: (f"In the '{fixture.DB_TITLE}' database, what is the total of the Points property across all "
                   f"projects whose Owner is {_OWNER} and Status is '{_STATUS}'? Reply with the number."),
        _agg_check,
    ),
    Task(
        "filter_list", "aggregate",
        lambda c: f"List the names of every project in the '{fixture.DB_TITLE}' database whose Status is 'Blocked'. Names only.",
        _blocked_check,
    ),
    Task(
        "overdue", "aggregate",
        lambda c: (f"Using the '{fixture.DB_TITLE}' database: treat today as 2026-06-01. A project is overdue if its "
                   "Due date is before today and its Status is not 'Done'. Which Owner has the most overdue projects, "
                   "and how many?"),
        _overdue_check,
    ),
    Task(
        "write", "write",
        lambda c: (f"Find the 3 projects with the highest Points in the '{fixture.DB_TITLE}' database. Then create a new "
                   f"page as a child of the '{fixture.SANDBOX_TITLE}' page, titled exactly '{_report_title(c)}', whose "
                   "body is a bulleted list with one bullet per project: '<project name> - <points>'."),
        _write_check, servers=("notion",), cleanup=_write_cleanup,
    ),
    Task(
        "update", "write",
        lambda c: (f"In the '{fixture.DB_TITLE}' database, set the project '{_UPDATE_TARGET}' to Points = 99 and "
                   "Status = 'Done'."),
        _update_check, servers=("notion",), cleanup=_update_cleanup,
    ),
]


def tasks_for(server: str, only: list[str] | None = None) -> list[Task]:
    ts = [t for t in TASKS if server in t.servers]
    if only:
        unknown = set(only) - {t.id for t in ts}
        if unknown:
            raise SystemExit(f"Unknown task(s) for {server}: {sorted(unknown)}")
        ts = [t for t in ts if t.id in only]
    return ts


def load_state(server: str) -> dict[str, Any]:
    if server != "notion":
        return {}
    if not STATE_FILE.exists():
        raise SystemExit("No Notion fixtures yet. Run `uv run bench-seed` first.")
    return json.loads(STATE_FILE.read_text())
