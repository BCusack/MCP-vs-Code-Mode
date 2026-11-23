# Findings: MCP vs Code Mode on the Notion MCP server

Date: 2026-11-23. Model `claude-opus-5-5`, effort medium, prompt caching on. Official Notion MCP
server (24 tools). 6 tasks (lookup, aggregate, filter_list, overdue, write, update), 3 runs per
task and mode. Every mode ran on the same LangGraph `create_agent`, base prompt and MCP session.

Data: [`results/report.md`](../results/report.md) (MCP vs code vs ptc, 54 runs) and
[`results/ablation_report.md`](../results/ablation_report.md) (code-mode variants, 126 runs).
What each mode's model saw on its first call is in [`results/prompts/`](../results/prompts/).
Every run in both reports passed its deterministic check.

## 1. Code mode beats classic MCP tool calling

| | MCP | Code (Python) | PTC (LangChain, JS) |
|---|---:|---:|---:|
| Cost per run | $0.0801 | $0.0379 (**-53%**) | $0.0443 (-45%) |
| Total tokens per run | 57,150 | 19,163 (-66%) | 27,590 (-52%) |
| First-call input (tokens) | 8,942 | 2,132 | 5,474 |
| Wall time (s) | 7.7 | 9.8 | 10.9 |
| Success | 100% | 100% | 100% |

- **The saving comes from two places.** The prompt is smaller (one code tool and an API listing,
  instead of 24 JSON schemas), and raw API responses stay in the interpreter instead of going
  into the model's context.
- **The bigger the task, the bigger the win.** On `write` (several API calls), MCP used 156k
  tokens and $0.25 per run. Code mode used 24k tokens and $0.05 (-80%).
- **Code mode is slower** (+27% wall time for Python, +42% for PTC). It makes fewer model
  calls, but each one writes code that then has to run. Here it trades seconds for dollars.

## 2. What matters inside code mode (ablations)

Change against default `code` mode (compact stubs, all functions listed, variables kept between
calls):

| Variant | Cost Δ | First-call input | Tool output into context | Verdict |
|---|---:|---:|---:|---|
| `api=full`: nested types plus per-parameter docs | **-13%** | 4,448 (+109%) | 3,216 (-49%) | Cheapest overall, and on 4 of 6 tasks (all the multi-call ones) |
| `discovery=index`: skills-style YAML frontmatter | +8% | 2,007 | 8,087 | No gain |
| `discovery=index,describe=doc`: plus a readable `describe()` | +8% | 2,016 | 8,503 | No gain |
| `state=fresh`: variables wiped between calls (Cloudflare's model) | +10% | 2,145 | 8,428 | Keeping state is slightly better |
| `ptc`: LangChain `langchain-quickjs` | +25% | 5,474 | 5,582 | Costs more than our Python |
| `discovery=names`: names only, details through `describe()` | **+57%** | 1,327 | 19,727 (+213%) | Worst |

- **Give the model the full API up front.** `api=full` doubles the prompt, but with caching
  that costs little, and the model writes correct code on the first try and prints less. A
  more detailed API is worth paying for.
- **Lazy discovery (Cloudflare's current design, skills-style progressive disclosure) loses at
  this size.** Each `describe()` round adds a model call and brings schema text into context.
  With 24 tools, loading everything up front is cheaper. Lazy discovery likely only pays off
  with hundreds of tools, which this benchmark did not test.
- **The format of the listing matters little.** YAML frontmatter and Python stubs came out
  within noise of each other (index entries were generated from the schemas, not hand-written).
- **Python vs JS:** `code:api=full` shows about as much API detail as PTC's TypeScript
  signatures, and it cost about 30% less. So PTC's higher cost is not just its larger prompt.
  It may come from JS/QuickJS or from the middleware's own prompt text; this benchmark did not
  separate the two.
- **Keeping state between calls** helps a little (`fresh` +10%), mostly through re-fetching.

## 3. Integration lessons

- **MCP tools inside LangChain's PTC return raw content blocks** (`[{type: "text", text:
  "<json>"}]`), while its prompt tells the model that results need no `JSON.parse`. We parse the
  JSON for the model (`--ptc-parse-json`, on by default) so the comparison measures the design,
  not this integration gap.
- **langchain-quickjs 0.4.0 crashes on list-valued JSON Schema `type`**, which the Notion server
  uses. Worked around with `ts_safe_schema` in `bench/ptc.py`.
- **The Notion server's schemas repeat a shared `$defs` block in every tool**, so one raw
  `describe()` is about 1,500 tokens. Rendering it as a signature cuts that to 130 to 220.
- **PTC's inner MCP calls can be traced:** the bridge passes the run's callbacks into each tool
  call, so they show up in LangSmith and can be counted.

## Caveats

- 3 runs per task and mode. Treat differences under about ±10% (index, fresh) as ties.
- One server (Notion, 24 tools), one model, and small tasks. Phase 3 (large paginated reads,
  joins, bulk updates) was not run. Code mode should gain most there.
- The `@notionhq/notion-mcp-server` version was not pinned. The ablation's `update` task was
  re-run in a second session after the first ran out of API credit; the report combines both.
- Code mode's `exec` is not a security sandbox. Any real use needs an isolated runtime.

## Recommendation

For an agent calling an MCP server with tens of tools: use code mode. Give the model a
detailed, fully listed API, keep interpreter state for the whole run, and parse tool results
into native values before the code sees them.
