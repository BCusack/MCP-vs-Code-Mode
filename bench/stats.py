"""Confidence intervals for benchmark results, from existing raw JSONL (no API calls).

    uv run bench-stats results/raw/20261122T230231Z_notion.jsonl --base mcp
    uv run bench-stats results/raw/ablation_combined_notion.jsonl --base code

For each mode: mean per task run with a 95% bootstrap CI, the median, and the change against
the base mode with its own 95% CI. Cost differs a lot between tasks, so the bootstrap resamples
runs *within each task* (stratified) and weights every task equally. With 3 runs per task the
CIs are rough; read them as "is the sign clear?", not as precise bounds.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

from bench.report import ROOT, MODE_LABELS, _load

METRICS = [  # (key, label, fmt)
    ("cost_usd", "Cost (USD)", "${:.4f}"),
    ("total_tokens", "Total tokens", "{:,.0f}"),
    ("wall_seconds", "Wall time (s)", "{:.1f}"),
]


def _group(rows: list[dict], key: str) -> dict[str, dict[str, list[float]]]:
    """mode -> task -> values."""
    out: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        out[r["mode"]][r["task"]].append(float(r[key]))
    return out


def _task_mean(by_task: dict[str, list[float]]) -> float:
    return st.mean(st.mean(v) for v in by_task.values())


def _resample(by_task: dict[str, list[float]], rng: random.Random) -> float:
    return st.mean(st.mean(rng.choices(v, k=len(v))) for v in by_task.values())


def _ci(samples: list[float]) -> tuple[float, float]:
    s = sorted(samples)
    return s[int(0.025 * len(s))], s[int(0.975 * len(s)) - 1]


def compute(rows: list[dict], base: str, key: str, iters: int = 10_000, seed: int = 0) -> list[dict]:
    """One dict per mode: mean, ci, median, and (vs base) delta, delta_ci, tasks_better, n_tasks."""
    g = _group(rows, key)
    if base not in g:
        raise ValueError(f"base mode {base!r} not in data (have {sorted(g)})")
    rng = random.Random(seed)
    boots = {m: [_resample(g[m], rng) for _ in range(iters)] for m in g}
    out = []
    order = [m for m in MODE_LABELS if m in g] + sorted(m for m in g if m not in MODE_LABELS)
    for m in order:
        vals = [v for vs in g[m].values() for v in vs]
        d = {"mode": m, "n": len(vals), "mean": _task_mean(g[m]), "ci": _ci(boots[m]),
             "median": st.median(vals)}
        if m != base:
            shared = sorted(set(g[m]) & set(g[base]))
            d["delta"] = d["mean"] / _task_mean(g[base]) - 1
            d["delta_ci"] = _ci([a / b - 1 for a, b in zip(boots[m], boots[base])])
            d["tasks_better"] = sum(st.mean(g[m][t]) < st.mean(g[base][t]) for t in shared)
            d["n_tasks"] = len(shared)
        out.append(d)
    return out


def render(paths: list[Path], base: str) -> str:
    rows = _load(paths)
    label = lambda m: MODE_LABELS.get(m, m)  # noqa: E731
    L = [f"## Confidence intervals: {', '.join(p.name for p in paths)}", "",
         f"Base: **{label(base)}**. Mean per task run (tasks weighted equally) with a 95% stratified "
         f"bootstrap CI; Δ is against the base, with its own 95% CI. \"Tasks better\" counts tasks "
         f"where the mode's mean is lower than the base's. A Δ CI that crosses 0% is a tie.", ""]
    for key, name, fmt in METRICS:
        L += [f"### {name}", "",
              "| Mode | Runs | Mean | 95% CI | Median | Δ vs base | Δ 95% CI | Tasks better |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for d in compute(rows, base, key):
            ci = f"{fmt.format(d['ci'][0])} to {fmt.format(d['ci'][1])}"
            if "delta" in d:
                lo, hi = d["delta_ci"]
                tail = f"{d['delta']:+.0%} | {lo:+.0%} to {hi:+.0%} | {d['tasks_better']}/{d['n_tasks']}"
            else:
                tail = "base | | "
            L.append(f"| {label(d['mode'])} | {d['n']} | {fmt.format(d['mean'])} | {ci} | "
                     f"{fmt.format(d['median'])} | {tail} |")
        L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--base", default="mcp", help="mode to compare against (default: mcp)")
    ap.add_argument("--out", type=Path, help="append to this Markdown file instead of printing")
    a = ap.parse_args()
    text = render(a.paths, a.base)
    if a.out:
        with a.out.open("a") as f:
            f.write(text + "\n")
        print(f"wrote {a.out.relative_to(ROOT) if a.out.is_absolute() else a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
