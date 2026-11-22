# MCP vs Code Mode

A small personal benchmark: does **code mode** beat **classic MCP tool calling**?

Both modes use the **same LangGraph agent** (`langchain.agents.create_agent`), the **same Claude model**, the **same MCP server** (the official Notion MCP server), and the **same tasks**. Only the way the model reaches the tools differs.

| | Classic MCP | Code mode |
|---|---|---|
| What the model sees | All 24 Notion tool schemas (~80 KB of JSON) | One `execute_python` tool plus a compact Python API listing (~4 KB) generated from the same MCP server |
| How it calls Notion | One tool call per API call. Every raw JSON response goes back into the context. | Writes Python that calls `await notion.query_data_source(...)` etc. Loops, filters and math run in code, and only what the code `print`s goes back to the model. |
| Inspired by | - | Cloudflare "Code Mode", Anthropic "Code execution with MCP" |

## Metrics in the report

Per task, per mode, averaged over N runs:

- **Success rate**, checked deterministically against known fixture data (no LLM judge)
- **Tokens**: total, input (cached vs uncached), cache reads, output (including thinking)
- **Cost (USD)**, from `bench/pricing.py`, with cache reads and writes priced separately; also **cost per successful run**
- **Context overhead**: input tokens on the first call (system prompt + tool definitions)
- **Wall-clock time**
- **LLM round-trips**, **tool calls the model made**, and **calls that actually hit the MCP server**
- **Tool output fed back into context** (chars), which shows how much raw data the model had to read
- **Tool errors**, plus a failures list with the reason for each

## Tasks (Notion)

The seeder creates a sandbox page containing a 60-row `Bench Projects` database and a `Bench Meeting Notes` page. The data is deterministic, so every answer has exactly one correct value.

| id | type | what it tests |
|---|---|---|
| `lookup` | read | Find a page and pull a fact buried in its body |
| `aggregate` | aggregate | Sum Points for one owner/status (needs pagination and filtering) |
| `filter_list` | aggregate | List all 13 Blocked projects |
| `overdue` | aggregate | Date logic plus group-by: which owner has the most overdue projects |
| `write` | write | Find the top 3 by Points and create a page with a bulleted list (verified, then archived) |
| `update` | write | Update two properties on one row (verified, then restored) |

## Setup (WSL2)

```bash
cd ~/projects
git clone https://github.com/bcusack/mcp-vs-code-mode.git
cd mcp-vs-code-mode
uv sync                       # needs Node 18+ too (npx runs the Notion MCP server)
cp .env.example .env          # .env is git-ignored. Keys go ONLY there.
uvx pre-commit install        # optional: gitleaks blocks commits that contain secrets
```

Fill in `.env`:

1. `ANTHROPIC_API_KEY`: from console.anthropic.com
2. `NOTION_TOKEN`: create an **internal integration** at notion.so/profile/integrations (read, update and insert content)
3. `NOTION_PARENT_PAGE_ID`: create an empty throwaway page, connect the integration to it (`...` > Connections), then paste its URL or ID

Then:

```bash
uv run bench-seed                  # creates the fixtures under your page (~1 min, rate limited)
uv run bench-run                   # all 6 tasks x 2 modes x 3 runs, then writes results/report.md
uv run bench-run --tasks aggregate overdue --runs 5
uv run bench-run --model claude-sonnet-5-5 --effort low
uv run bench-run --no-cache        # see what prompt caching does for MCP mode's big tool list
uv run bench-report results/raw/*.jsonl   # combine several runs into one report
uv run bench-seed --teardown       # archive the sandbox when you're done
```

Without a Notion account, `uv run bench-run --server mock --runs 1` runs the four read tasks against a local mock MCP server with the same data. `uv run pytest` runs the offline tests, which need no keys.

A full default run is 36 agent runs on Claude Opus 5.5. Expect a few dollars; check the report's cost table and scale `--runs` to suit.

## Keeping secrets out of the public repo

- Keys live only in `.env`, which `.gitignore` excludes. `.env.example` has empty placeholders.
- `.state/` (your Notion page and database IDs) and `results/raw/` (per-run metrics, including final answers) are git-ignored.
- The Notion token goes only to the MCP child process's environment. It is never logged or written to results.
- gitleaks runs as a pre-commit hook (opt-in) and in CI on every push.

## Caveats

- **Code mode's sandbox is not a security boundary.** Model-written code runs in-process with an import allowlist and no `open`/`eval`. That guards against accidents, not attacks, so only point it at a test workspace. For real use, run the code in an isolated container or V8 isolate.
- The code-mode API listing uses one-line signatures. The model calls `describe("fn")` to get a full schema on demand (progressive disclosure). A richer typed listing would cost more tokens up front but may cut errors.
- Prompt caching is on by default for both modes (realistic). Run with `--no-cache` to see raw context cost.
- LLM runs are noisy. Use 5 or more runs before trusting small differences.

## Adding another MCP server

1. Add a `ServerSpec` in `bench/servers.py` (stdio command or HTTP URL).
2. Add tasks with deterministic checks in `bench/tasks.py` (`servers=("yourserver",)`).
3. `uv run bench-run --server yourserver`

### Good candidates to test next

Code mode should win most where tool lists are large or responses are big and need filtering:

| Server | Why it's interesting |
|---|---|
| **Google Drive / Docs / Sheets** (e.g. `taylorwilsdon/google_workspace_mcp`) | Many tools (50+) and large document bodies. Sheets aggregation is a natural code-mode win. |
| **GitHub** (`github/github-mcp-server`) | Around 90 tools with very large schemas. Paginated issue/PR listings. |
| **Slack** | Paging channel history then summarizing or filtering. |
| **Linear / Jira / Atlassian** | Database-like queries plus cross-object joins, similar to the Notion tasks. |
| **Postgres / SQLite MCP** | Control case: SQL already does the "code" part, so the gap should shrink. |
| **Filesystem** (`@modelcontextprotocol/server-filesystem`) | Few, small tools. Control case where classic MCP may win. |
| **Playwright / browser** | Huge DOM snapshots in tool results, which stresses context. |
