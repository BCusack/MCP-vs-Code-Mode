"""Deterministic test data shared by the Notion seeder, the mock server, and the task checks."""

from __future__ import annotations

import datetime as dt
import random

STATUSES = ["Not started", "In progress", "Done", "Blocked"]
OWNERS = ["Ava", "Ben", "Chloe", "Diego", "Priya"]
ADJ = ["Amber", "Brisk", "Cobalt", "Dapper", "Ember", "Frost", "Gilded", "Harbor", "Ivory", "Jade",
       "Kinetic", "Lunar", "Mosaic", "Nimbus", "Onyx", "Pioneer", "Quartz", "Radiant", "Sable", "Tidal"]
NOUN = ["Falcon", "Atlas", "Beacon", "Compass", "Delta", "Echo", "Forge", "Grove"]

N_PROJECTS = 60
CODE_WORD = "PERIWINKLE-42"
MEETING_PAGE = "Bench Meeting Notes"
DB_TITLE = "Bench Projects"
SANDBOX_TITLE = "MCP Bench Sandbox"


def projects() -> list[dict]:
    rng = random.Random(1234)
    names = [f"{a} {n}" for a in ADJ for n in NOUN]
    rng.shuffle(names)
    base = dt.date(2026, 1, 5)
    out = []
    for i in range(N_PROJECTS):
        out.append({
            "Name": f"Project {names[i]}",
            "Status": rng.choice(STATUSES),
            "Owner": rng.choice(OWNERS),
            "Points": rng.randint(1, 13),
            "Due": (base + dt.timedelta(days=rng.randint(0, 300))).isoformat(),
        })
    # Give the top 3 unambiguous scores so "highest Points" has one right answer.
    for idx, pts in ((7, 21), (19, 17), (41, 15)):
        out[idx]["Points"] = pts
    return out


def meeting_notes() -> list[str]:
    """~40 paragraphs; the code word is buried near the end."""
    rng = random.Random(99)
    filler = [
        "Discussed roadmap sequencing and dependencies across teams.",
        "Reviewed open incidents; no new sev-1 issues this week.",
        "Agreed to revisit hiring plan after the planning offsite.",
        "Design review for the onboarding flow is scheduled for Thursday.",
        "Budget variance is within tolerance for the quarter.",
        "Action item: follow up with legal on the vendor contract.",
    ]
    paras = [f"{i + 1}. {rng.choice(filler)}" for i in range(38)]
    paras.insert(33, f"Launch code word for the release is {CODE_WORD}. Keep it internal.")
    return paras


# ---- expected answers -------------------------------------------------------

def expected_points(owner: str, status: str) -> int:
    return sum(p["Points"] for p in projects() if p["Owner"] == owner and p["Status"] == status)


def expected_names(status: str) -> list[str]:
    return sorted(p["Name"] for p in projects() if p["Status"] == status)


def top_points(n: int = 3) -> list[str]:
    ranked = sorted(projects(), key=lambda p: (-p["Points"], p["Name"]))
    return [p["Name"] for p in ranked[:n]]


def owner_with_most_overdue(today: str = "2026-06-01") -> tuple[str, int]:
    counts: dict[str, int] = {}
    for p in projects():
        if p["Status"] != "Done" and p["Due"] < today:
            counts[p["Owner"]] = counts.get(p["Owner"], 0) + 1
    best = max(sorted(counts), key=lambda o: counts[o])
    return best, counts[best]
