# Handoff / status

Last updated: 2026-11-24. Worked on in Claude Code (WSL2, `~/projects/mcp-vs-code-mode`).

## Status: wrapped up after Phase 2

The project stops here. Results and conclusions are in [FINDINGS.md](FINDINGS.md). The phase
plan, including the follow-ups that were not run, is in [PLAN.md](PLAN.md).

Headline (Notion MCP server, 24 tools, `claude-opus-5-5`, effort medium, caching on): code mode
cost $0.038 per run against $0.080 for classic MCP tool calling (-53%), with 66% fewer tokens.
LangChain's PTC (JS) came in at -45%. Inside code mode, a fully listed, detailed API
(`code:api=full`) was cheapest; lazy discovery through `describe()` cost more at this tool count.

## Done

- Harness, Notion seeder, 6 tasks, metrics, report, offline mock server and tests (PR #1).
- CI: `secrets` (gitleaks over full history) and `tests` (pytest). Green on `master`.
- `master` is protected by the "Protect master" ruleset (active).
- First live run (PR #5). Live runs against Claude and Notion: MCP vs code vs ptc, 54 runs
  (`results/report.md`).
- `ptc` mode with LangChain `langchain-quickjs` (PRs #6, #7).
- Phase 2 code-mode ablations, 126 runs (`results/ablation_report.md`, PRs #8, #9).
- Findings write-up with diagrams, plus a design for a multi-agent, full-API code mode
  ([MULTI_AGENT.md](MULTI_AGENT.md), not built or measured) (PR #10).
- First-call prompt dumps for every mode in `results/prompts/`.
- Stale branches from merged PRs deleted (2026-11-24).
- Cloudflare code-mode emulations (`cf-stateless`, `cf-durable`), 90-run session on 2026-11-24
  (`results/cloudflare_report.md`, FINDINGS section 3). Notion fixtures were re-seeded for it.

## Open (none planned)

1. **Phase 3 tasks** where code mode should gain most: `bulk_aggregate` (150+ rows,
   pagination), `join` (two data sources), `bulk_update`. Needs a bigger fixture and a re-seed.
2. **Phase 4 reproducibility (partly done):** the server is pinned to 2.6.1 and
   `bench-stats` gives 95% CIs and medians (`results/stats.md`). Still open: `--runs 5`+ to
   tighten the CIs (`api=full` crosses zero), and recording versions in `summary.json`.
3. **Phase 6 (parked):** build the multi-agent design and test it against a single
   `code:api=full` agent on Phase 3 tasks.
4. **Other MCP servers:** Google Workspace, GitHub, Slack, Linear/Jira, plus Postgres and
   filesystem as control cases. Add a `ServerSpec` in `bench/servers.py` and tasks in
   `bench/tasks.py`.

Live runs cost money: ask before each one (see CLAUDE.md).

## Design notes

- Code mode gives the model one `execute_python` tool plus a signature listing (compact by
  default, `api=full` for nested types and per-parameter docs). `describe("fn")` returns a
  function's full schema on demand. Only printed output returns to the model, and variables
  persist between calls within a run (unless `state=fresh`).
- `ptc` mode parses MCP JSON results for the model (`--ptc-parse-json`, on by default) and
  works around a `langchain-quickjs` 0.4.0 crash on list-valued schema `type` with
  `ts_safe_schema`.
- Metrics come from `AIMessage.usage_metadata`. langchain-anthropic's `input_tokens` *includes*
  cache reads and writes, and `metrics.py` splits them out for cost.
- In MCP mode `mcp_calls` equals the number of tool calls. In code mode it is counted by
  `McpBridge`, in `ptc` by `McpCallCounter`.
- Modes alternate order each run to spread out cache and latency effects.
- The Notion server (API 2025-09-03) uses data sources; the seeder's 2022-06-28 database is
  readable as one. Every run in both reports passed its check.
