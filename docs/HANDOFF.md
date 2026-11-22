# Handoff / status

Last updated: 2026-11-22. This was built in a Claude Code cloud session and is being continued in Claude Code in VS Code (WSL2, `~/projects/mcp-vs-code-mode`).

## Done

- Benchmark harness, Notion seeder, 6 tasks, metrics, report, and an offline mock server with tests. Merged in PR #1.
- CI: `secrets` runs gitleaks over the full history, and `tests` runs pytest. Both are green on `master`.
- Repo is public. `master` is the default branch.

## Not done yet (in order)

1. **Protect `master`** (repo owner, in the GitHub UI). As of the last check, GitHub reported `master` as *not protected*.
   Settings → Rules → Rulesets → New branch ruleset:
   - Enforcement **Active**. Target `master` (or "Include default branch").
   - Restrict deletions, block force pushes.
   - Require a pull request with 1 approval, and dismiss stale approvals.
   - Require status checks `secrets` and `tests`.
   - Bypass list: **Repository admin**, mode "For pull requests only". GitHub never lets a PR's author approve it, and Claude's PRs show up as authored by the owner, so the owner merges their own PRs through the bypass.
   - Optionally add `.github/CODEOWNERS` with `* @BCusack` and tick "Require review from Code Owners".
   - Also delete the merged branch `ccr-853f1a15-h4b8xe`.
2. **First real run. Nothing has run against live Claude or Notion yet** (the build environment had no keys).
   - `cp .env.example .env` and fill it in. Then `uv run bench-run --server mock --runs 1` (cheap check that the Claude path works).
   - `uv run bench-seed`, then `uv run bench-run --tasks lookup aggregate --runs 1`, then the full run.
3. **Things to watch on the first live run:**
   - The Notion MCP server (`@notionhq/notion-mcp-server`, Notion API 2025-09-03) uses data sources. The agent must find the `data_source_id` through `retrieve_a_database` or search. If both modes keep failing there, consider adding a hint to `BASE_PROMPT` (it goes to both modes).
   - The seeder uses Notion API `2022-06-28` to create the database. That should be readable as a data source under 2025-09-03, but this hasn't been checked.
   - Some MCP tool params are typed `dict | str` (the server accepts JSON strings). Check that the code-mode signatures don't confuse the model.
   - Check that cache tokens show up in the report (`cache_read_tokens` > 0 on later calls). If not, check that the caching middleware is applying.
   - Check that `pricing.py` matches current pricing.
4. **Next MCP servers to compare** (README has the list): Google Workspace (Docs/Sheets), GitHub, Slack, Linear/Jira, plus Postgres and filesystem as control cases. Add a `ServerSpec` in `bench/servers.py` and tasks in `bench/tasks.py`.

## Design notes

- Code mode gives the model one `execute_python` tool plus a compact signature listing. `describe("fn")` returns a function's full schema on demand. Only printed output returns to the model, and variables persist between calls within a run.
- Metrics come from `AIMessage.usage_metadata`. langchain-anthropic's `input_tokens` *includes* cache reads and writes, and `metrics.py` splits them out for cost.
- In MCP mode `mcp_calls` equals the number of tool calls. In code mode it is counted by `McpBridge`.
- Modes alternate order each run to spread out cache and latency effects.
