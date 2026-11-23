# Plan: MCP vs Code Mode, next stage

Goal: measure classic MCP tool calling against code mode fairly, and find out which parts of
code mode cause the savings. Wrapping every agent tool (files, shell) the way Claude Code's
Code Mode does, and the TypeScript port, are out of scope for now.

## Modes

| Mode | What it is |
|---|---|
| `mcp` | The model calls MCP tools directly |
| `code` | Our Python `execute_python` over generated stubs (`bench/codemode.py`) |
| `ptc` | LangChain `langchain-quickjs` `CodeInterpreterMiddleware`: the model writes JS that runs in QuickJS/WASM, with the MCP tools exposed as `tools.*` (`bench/ptc.py`) |

`ptc` runs on plain `create_agent`, not `deepagents`. Deep Agents adds its own system prompt
and built-in tools, which would break the fairness rule.

## Phase 1: `ptc` mode (offline, $0). Status: done

- `bench/ptc.py`: middleware factory with limits matched to `code` (120 s timeout, 20k output
  chars, state kept for the run, no subagents). MCP tools are reachable only from code.
- MCP calls inside `eval` are counted by `McpCallCounter`. The PTC bridge passes the run's
  callbacks to each `tool.arun`, which is also why LangSmith shows each of those calls as a
  child span.
- `PromptCapture` writes what the model saw on its first call, for each mode, to
  `results/prompts/<server>_<mode>.md`.
- The report shows any set of modes, with MCP as the baseline and a delta column for each
  code mode.

### Findings so far

- `ptc` renders the MCP tools as TypeScript signatures from their JSON schemas, using the first
  line of each description and `Promise<unknown>` as the return type. That is close to our
  compact stubs.
- **Inside JS, MCP tools return raw MCP content blocks** (`[{type: "text", text: "<json>"}]`).
  The middleware's own prompt says "You do NOT need to JSON.parse results", which is wrong for
  MCP tools. Our `code` mode parses the JSON for the model.

### Decision: parse JSON for `ptc` (on by default)

`--ptc-parse-json` (the default) wraps each MCP tool with `with_parsed_json`, which uses the
same rules as `McpBridge`: prefer `structuredContent`, otherwise parse the JSON text, drop
`null` arguments, and raise on MCP errors (a rejected Promise in JS, counted in
`mcp_errors_inside_code`). This way the comparison isolates the design (JS/WASM vs Python)
from the integration gap. `--no-ptc-parse-json` restores the raw behavior as shipped, and each
result row records which setting was used (`extra.ptc_parse_json`).

## Phase 2: ablations of `code` mode. Status: built, not run live yet

Variants are mode specs, so they run side by side in one invocation (same MCP session,
alternating order) and show up as separate columns in the report:

```bash
uv run bench-run --modes code code:state=fresh code:api=full code:discovery=names \
  code:discovery=index code:discovery=index,describe=doc --runs 3
```

| Option | Values (default first) | Question it answers |
|---|---|---|
| `state` | `persist` / `fresh` | Does keeping state between calls matter? (Cloudflare: fresh; ours and LangChain: kept) |
| `api` | `compact` / `full` | Do nested types and per-parameter docs reduce `describe()` calls and errors, and what do they cost? |
| `discovery` | `upfront` / `names` / `index` | Is it cheaper to list names only and look up details with `describe()`? (Cloudflare's current design). `index` lists the API as skills-style YAML frontmatter (name, description, required/optional parameter names) |
| `describe` | `json` / `doc` | What should `describe()` return: the raw MCP input schema, or a readable page (the `api=full` signature with parameter docs, like a skill's body loaded on demand)? |

Prompt size on the real Notion tools (24 functions, code-mode addendum only): compact about
1,080 tokens, `api=full` about 2,780, `discovery=names` about 540, `discovery=index` about 1,000
(close to compact: it drops types but adds YAML keys). `api=full` gives roughly the detail `ptc`
shows (TS signatures, about 5.5k tokens for the whole first call), so comparing `code:api=full`
with `ptc` separates "more API detail" from "JS instead of Python".

`describe()` for one Notion function is about 1,500 tokens as `json` (each tool's schema repeats
the shared `$defs`) and 130 to 220 as `doc`. The `index` entries are generated from the schemas,
never hand-written, so code mode gets no prompt tuning that MCP mode lacks.

Without `mcp` in `--modes`, the report uses the first mode as the baseline.

## Phase 3: tasks where code mode should matter more

`bulk_aggregate` (150+ rows, needs pagination), `join` (two data sources, multi-hop), and
`bulk_update` (update N pages that match a filter). Checks are deterministic and come from
`fixture.py`. This needs a bigger fixture and a re-seed.

## Phase 4: reproducibility

- Pin `@notionhq/notion-mcp-server` again, or record its version and a hash of the tool list.
- Use `--runs 5` or more, and report mean ± 95% CI and the median.
- Record the model, effort, `langchain-quickjs` version and server version in `summary.json`.

## Phase 5: live runs (paid, ask before each one)

1. Mock smoke test: `--server mock --modes ptc --runs 1`
2. `--tasks lookup aggregate --modes mcp code ptc --runs 1`
3. Full run: 9 tasks × 3 modes × 5 runs, estimated at $7 to 10. Then the ablations.
