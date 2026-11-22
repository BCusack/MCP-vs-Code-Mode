"""Aggregate raw JSONL results into results/report.md and results/summary.json.

    uv run bench-report                       # latest raw file
    uv run bench-report results/raw/*.jsonl   # combine several
"""

from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (key, label, lower_is_better, fmt)
METRICS = [
    ("success", "Success rate", False, "{:.0%}"),
    ("total_tokens", "Total tokens", True, "{:,.0f}"),
    ("input_tokens", "Input tokens (incl. cached)", True, "{:,.0f}"),
    ("uncached_input_tokens", "Uncached input tokens", True, "{:,.0f}"),
    ("cache_read_tokens", "Cache-read tokens", True, "{:,.0f}"),
    ("output_tokens", "Output tokens (incl. thinking)", True, "{:,.0f}"),
    ("first_call_input_tokens", "Context overhead (1st call input)", True, "{:,.0f}"),
    ("cost_usd", "Cost (USD)", True, "${:.4f}"),
    ("wall_seconds", "Wall time (s)", True, "{:.1f}"),
    ("llm_calls", "LLM round-trips", True, "{:.1f}"),
    ("agent_tool_calls", "Tool calls by model", True, "{:.1f}"),
    ("mcp_calls", "Calls reaching MCP server", True, "{:.1f}"),
    ("tool_result_chars", "Tool output into context (chars)", True, "{:,.0f}"),
    ("tool_errors", "Tool errors", True, "{:.2f}"),
]


def _load(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        rows += [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    return rows


def _mean(rows: list[dict], key: str) -> float:
    vals = [float(r[key]) for r in rows]
    return st.mean(vals) if vals else 0.0


def _delta(code: float, mcp: float) -> str:
    if mcp == 0:
        return "n/a"
    return f"{(code - mcp) / mcp:+.0%}"


def _fmt(fmt: str, v: float) -> str:
    return fmt.format(v)


def build_report(paths: list[Path]) -> Path:
    rows = _load(paths)
    if not rows:
        raise SystemExit("no rows")
    by_mode: dict[str, list[dict]] = defaultdict(list)
    by_task: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_mode[r["mode"]].append(r)
        by_task[(r["task"], r["mode"])].append(r)
    tasks = list(dict.fromkeys(r["task"] for r in rows))
    modes = [m for m in ("mcp", "code") if m in by_mode]
    models = sorted({r["model"] for r in rows})
    servers = sorted({r["server"] for r in rows})
    runs = max(r["run"] for r in rows)

    summary: dict = {"servers": servers, "models": models, "runs_per_task": runs, "overall": {}, "per_task": {}}
    for m in modes:
        summary["overall"][m] = {k: _mean(by_mode[m], k) for k, *_ in METRICS}
        succ = sum(r["success"] for r in by_mode[m])
        total_cost = sum(r["cost_usd"] for r in by_mode[m])
        summary["overall"][m]["total_cost_usd"] = total_cost
        summary["overall"][m]["cost_per_success_usd"] = total_cost / succ if succ else None
    for t in tasks:
        summary["per_task"][t] = {m: {k: _mean(by_task[(t, m)], k) for k, *_ in METRICS}
                                  for m in modes if by_task.get((t, m))}

    L: list[str] = []
    L.append("# MCP vs Code Mode: benchmark report\n")
    L.append(f"- **Server(s):** {', '.join(servers)}  \n- **Model(s):** {', '.join(models)}  \n"
             f"- **Tasks:** {len(tasks)} x {runs} run(s) per mode  \n- **Raw data:** "
             + ", ".join(f"`{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}`" for p in paths) + "\n")
    L.append("Values are means per task run unless noted. Delta = code mode vs classic MCP "
             "(negative is better for everything except success rate).\n")

    if len(modes) == 2:
        o = summary["overall"]
        L.append("## Headline\n")
        L.append("| Metric | MCP | Code mode | Delta | Better |\n|---|---:|---:|---:|:---:|")
        for key, label, lower, fmt in METRICS:
            a, b = o["mcp"][key], o["code"][key]
            better = "-" if a == b else ("code" if (b < a) == lower else "mcp")
            L.append(f"| {label} | {_fmt(fmt, a)} | {_fmt(fmt, b)} | {_delta(b, a)} | {better} |")
        cps = [o[m]["cost_per_success_usd"] for m in ("mcp", "code")]
        L.append(f"| Total cost, all runs | ${o['mcp']['total_cost_usd']:.4f} | ${o['code']['total_cost_usd']:.4f} | "
                 f"{_delta(o['code']['total_cost_usd'], o['mcp']['total_cost_usd'])} | |")
        L.append("| Cost per successful run | " + " | ".join(f"${c:.4f}" if c else "n/a" for c in cps) + " | | |\n")

        L.append("## Per task\n")
        L.append("| Task | Mode | Success | Total tokens | Cost | Wall s | LLM calls | MCP calls | Tool output chars |")
        L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        for t in tasks:
            for m in modes:
                s = summary["per_task"][t].get(m)
                if not s:
                    continue
                L.append(f"| {t} | {m} | {s['success']:.0%} | {s['total_tokens']:,.0f} | ${s['cost_usd']:.4f} | "
                         f"{s['wall_seconds']:.1f} | {s['llm_calls']:.1f} | {s['mcp_calls']:.1f} | {s['tool_result_chars']:,.0f} |")
            pt = summary["per_task"][t]
            if "mcp" in pt and "code" in pt:
                L.append(f"| | **delta** | | **{_delta(pt['code']['total_tokens'], pt['mcp']['total_tokens'])}** | "
                         f"**{_delta(pt['code']['cost_usd'], pt['mcp']['cost_usd'])}** | "
                         f"**{_delta(pt['code']['wall_seconds'], pt['mcp']['wall_seconds'])}** | | | |")
        L.append("")

    fails = [r for r in rows if not r["success"]]
    if fails:
        L.append("## Failures\n")
        for r in fails:
            why = r.get("error") or r.get("extra", {}).get("check_detail", "")
            L.append(f"- `{r['task']}` / {r['mode']} / run {r['run']}: {why[:300]}")
        L.append("")

    L.append("## How to read this\n")
    L.append("- **Context overhead** is the input size of the first model call: system prompt + tool definitions + "
             "question. MCP mode pays for every tool schema; code mode pays for a compact API listing.\n"
             "- **Tool output into context** is how much raw tool data the model had to read. Code mode keeps "
             "intermediate data in the Python process and only returns what the code prints.\n"
             "- **Cost** uses `bench/pricing.py` (cache reads/writes priced separately). Output tokens include "
             "thinking tokens.\n"
             "- Small run counts are noisy. Use `--runs 5` or more before drawing conclusions.\n")

    res = ROOT / "results"
    res.mkdir(exist_ok=True)
    (res / "summary.json").write_text(json.dumps(summary, indent=2))
    md = res / "report.md"
    md.write_text("\n".join(L))
    return md


def main() -> None:
    args = [Path(a) for a in sys.argv[1:]]
    if not args:
        raws = sorted((ROOT / "results" / "raw").glob("*.jsonl"))
        if not raws:
            raise SystemExit("no results/raw/*.jsonl yet; run `uv run bench-run` first")
        args = [raws[-1]]
    print(build_report(args))


if __name__ == "__main__":
    main()
