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
MODE_LABELS = {"mcp": "MCP", "code": "Code (py)", "ptc": "PTC (js)",
               # emulations of Cloudflare's @cloudflare/codemode designs (see runner.ALIASES)
               "ptc:state=fresh": "CF stateless (js)",
               "code:state=fresh,discovery=search,describe=doc": "CF durable (py)"}
# code: our Python execute_python + generated stubs. ptc: langchain-quickjs CodeInterpreterMiddleware.

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


def build_report(paths: list[Path], name: str | None = None) -> Path:
    """Write a report for `paths`.

    With `name`, writes `results/reports/<name>.md` (+ `.summary.json`): used by `bench-run`
    so a smoke test never replaces the published report. Without it, writes the published
    `results/report.md` and `results/summary.json` (what `bench-report` does).
    """
    rows = _load(paths)
    if not rows:
        raise SystemExit("no rows")
    by_mode: dict[str, list[dict]] = defaultdict(list)
    by_task: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_mode[r["mode"]].append(r)
        by_task[(r["task"], r["mode"])].append(r)
    tasks = list(dict.fromkeys(r["task"] for r in rows))
    # known modes first, then code-mode variants (e.g. "code:api=full") in sorted order
    modes = [m for m in MODE_LABELS if m in by_mode] + sorted(m for m in by_mode if m not in MODE_LABELS)
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
    base = "mcp" if "mcp" in modes else modes[0]  # ablation runs without mcp compare against the first mode
    L.append(f"Values are means per task run unless noted. Δ = each mode vs **{MODE_LABELS.get(base, base)}** "
             "(negative is better for everything except success rate).\n")

    others = [m for m in modes if m != base]
    if others:
        o = summary["overall"]
        L.append("## Headline\n")
        L.append("| Metric | " + " | ".join(MODE_LABELS.get(m, m) for m in modes) + " | "
                 + " | ".join(f"Δ {MODE_LABELS.get(m, m)}" for m in others) + " | Best |")
        L.append("|---|" + "---:|" * (len(modes) + len(others)) + ":---:|")
        for key, label, lower, fmt in METRICS:
            vals = {m: o[m][key] for m in modes}
            if len(set(vals.values())) == 1:
                best = "-"
            else:
                best = (min if lower else max)(modes, key=lambda m: vals[m])
            L.append(f"| {label} | " + " | ".join(_fmt(fmt, vals[m]) for m in modes) + " | "
                     + " | ".join(_delta(vals[m], vals[base]) for m in others) + f" | {best} |")
        pad = " |" * len(others)
        L.append("| Total cost, all runs | " + " | ".join(f"${o[m]['total_cost_usd']:.4f}" for m in modes) + " | "
                 + " | ".join(_delta(o[m]["total_cost_usd"], o[base]["total_cost_usd"]) for m in others) + " | |")
        L.append("| Cost per successful run | " + " | ".join(
            f"${o[m]['cost_per_success_usd']:.4f}" if o[m]["cost_per_success_usd"] else "n/a" for m in modes)
            + " |" + pad + " |\n")

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
            for m in others:
                if base in pt and m in pt:
                    L.append(f"| | **Δ {m}** | | **{_delta(pt[m]['total_tokens'], pt[base]['total_tokens'])}** | "
                             f"**{_delta(pt[m]['cost_usd'], pt[base]['cost_usd'])}** | "
                             f"**{_delta(pt[m]['wall_seconds'], pt[base]['wall_seconds'])}** | | | |")
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
             "- **Modes:** `code` = our Python `execute_python` over generated stubs; `ptc` = LangChain "
             "`langchain-quickjs` (JS in QuickJS/WASM, MCP tools as `tools.*`).\n"
             "- **Tool output into context** is how much raw tool data the model had to read. Code mode keeps "
             "intermediate data in the Python process and only returns what the code prints.\n"
             "- **Cost** uses `bench/pricing.py` (cache reads/writes priced separately). Output tokens include "
             "thinking tokens.\n"
             "- Small run counts are noisy. Use `--runs 5` or more before drawing conclusions.\n")

    res = ROOT / "results"
    if name:
        res = res / "reports"
        md, sj = res / f"{name}.md", res / f"{name}.summary.json"
    else:
        md, sj = res / "report.md", res / "summary.json"
    res.mkdir(parents=True, exist_ok=True)
    sj.write_text(json.dumps(summary, indent=2))
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
