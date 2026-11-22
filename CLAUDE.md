# MCP vs Code Mode

A personal benchmark comparing **classic MCP tool calling** with **code mode** (the model writes Python against an API generated from the same MCP server). The first target is the official Notion MCP server. The harness is a LangGraph agent on Claude. The output is `results/report.md`.

Open items and history: @docs/HANDOFF.md

## Commands

```bash
uv sync                                   # install (Python 3.12, uv). Node 18+ is needed for npx
uv run pytest -q                          # offline tests, no keys, ~5s. Run after every change
uv run bench-run --server mock --runs 1   # offline-data smoke test (still calls Claude: needs ANTHROPIC_API_KEY)
uv run bench-seed                         # create Notion fixtures (needs NOTION_TOKEN + NOTION_PARENT_PAGE_ID)
uv run bench-run                          # full run: 6 tasks x 2 modes x 3 runs. COSTS MONEY, ask first
uv run bench-report [results/raw/*.jsonl] # rebuild report from raw results
uv run bench-seed --teardown              # archive Notion fixtures
```

## Layout

- `bench/runner.py`: CLI and per-run loop. `run_one()` builds a `create_agent` with either the MCP tools or the single `execute_python` tool.
- `bench/codemode.py`: code mode. Builds a Python API from MCP tool schemas (`signature`), plus `McpBridge` (calls the MCP session and counts calls) and `CodeRunner` (persistent async exec with an import allowlist).
- `bench/metrics.py`: turns the LangGraph message list into `RunMetrics` (tokens, cache, cost, calls, tool-output chars).
- `bench/tasks.py`: task prompts and **deterministic** checks. Write tasks verify through the Notion REST API, then clean up.
- `bench/fixture.py`: the single source of truth for test data and expected answers (seeded RNG).
- `bench/seed_notion.py`, `bench/notion_api.py`: fixture seeding and verification only. The agents never use them.
- `bench/servers.py`: MCP server registry (`notion`, `mock`). `bench/mock_server.py` is the offline FastMCP stand-in.
- `bench/pricing.py`: $/MTok table. Verify against anthropic.com/pricing. `pricing.json` overrides it.
- `bench/report.py`: writes `results/report.md` and `results/summary.json`.

## Rules

- **Public repo: never commit secrets.** Keys live only in `.env` (git-ignored). Never read, print or echo `.env` or token values. `.state/` (Notion IDs) and `results/raw/` are git-ignored. CI runs gitleaks over the full history.
- **Keep the comparison fair.** Both modes must get the same model, effort, caching, prompt base, MCP session and tasks. Any change to one mode's harness needs a matching consideration for the other.
- **Task checks stay deterministic.** Derive expected answers from `fixture.py`, never from an LLM judge. Give new fixture data unambiguous answers (no ties).
- **Code-mode exec is not a security sandbox.** Keep the import allowlist and the removed builtins. Only point it at a throwaway workspace.
- **Default model is `claude-opus-5-5`** (override with `--model` or `BENCH_MODEL`). Opus 5.5 cannot disable thinking. Control depth with `--effort`, which defaults to medium.
- **Live runs cost money.** Ask before running `bench-run` against real APIs, and prefer `--tasks` and a small `--runs` while iterating.

## Git

- `master` is the default branch, and it is meant to be protected. Work on a feature branch and open a PR. Both CI checks (`secrets`, `tests`) must pass.
- Install the local secret hook once with `uvx pre-commit install`.
