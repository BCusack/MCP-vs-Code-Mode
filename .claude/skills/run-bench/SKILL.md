---
name: run-bench
description: Run the MCP vs Code Mode benchmark and summarize the report. Use when asked to run, re-run, or compare benchmark results.
---

# Run the benchmark

1. Run `uv run pytest -q` first. If it fails, stop and fix it.
2. Check that `.env` exists with `test -f .env`. **Do not read it.** If it is missing, tell the user to `cp .env.example .env` and fill it in.
3. Confirm scope and cost with the user before any live run. Live runs call Claude and spend money. Suggest starting small:
   - Offline data: `uv run bench-run --server mock --runs 1`
   - Notion: if `.state/notion.json` is missing, run `uv run bench-seed` first. Then `uv run bench-run --tasks <ids> --runs <n>`.
   - Pass through any `--model`, `--effort` or `--no-cache` the user asks for.
4. Read `results/report.md` and give the user:
   - The headline table's winners: tokens, cost, cost per success, wall time, success rate.
   - Any failures, with the reason from the report's Failures section.
   - A caveat if runs per task are below 5 (the results are noisy).
5. If a failure looks like a harness bug rather than model behavior, investigate `bench/` and propose a fix. Keep the two modes symmetric.
