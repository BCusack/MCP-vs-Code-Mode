# MCP vs Code Mode: benchmark report

- **Server(s):** notion  
- **Model(s):** claude-opus-5-5  
- **Tasks:** 6 x 3 run(s) per mode  
- **Raw data:** `results/raw/20261122T230231Z_notion.jsonl`

Values are means per task run unless noted. Δ = each code mode vs classic MCP (negative is better for everything except success rate).

## Headline

| Metric | MCP | Code (py) | PTC (js) | Δ Code (py) | Δ PTC (js) | Best |
|---|---:|---:|---:|---:|---:|:---:|
| Success rate | 100% | 100% | 100% | +0% | +0% | - |
| Total tokens | 57,150 | 19,163 | 27,590 | -66% | -52% | code |
| Input tokens (incl. cached) | 56,668 | 18,490 | 26,908 | -67% | -53% | code |
| Uncached input tokens | 9 | 9 | 9 | +9% | +3% | mcp |
| Cache-read tokens | 44,352 | 14,172 | 21,642 | -68% | -51% | code |
| Output tokens (incl. thinking) | 482 | 673 | 682 | +40% | +42% | mcp |
| Context overhead (1st call input) | 8,942 | 2,132 | 5,474 | -76% | -39% | code |
| Cost (USD) | $0.0801 | $0.0379 | $0.0443 | -53% | -45% | code |
| Wall time (s) | 7.7 | 9.8 | 10.9 | +28% | +41% | mcp |
| LLM round-trips | 3.3 | 3.7 | 3.4 | +12% | +3% | mcp |
| Tool calls by model | 2.5 | 2.7 | 2.4 | +9% | -2% | ptc |
| Calls reaching MCP server | 2.5 | 3.1 | 3.1 | +22% | +24% | mcp |
| Tool output into context (chars) | 24,029 | 7,515 | 5,709 | -69% | -76% | ptc |
| Tool errors | 0.00 | 0.00 | 0.00 | n/a | n/a | - |
| Total cost, all runs | $1.4415 | $0.6818 | $0.7974 | -53% | -45% | |
| Cost per successful run | $0.0801 | $0.0379 | $0.0443 | | | |

## Per task

| Task | Mode | Success | Total tokens | Cost | Wall s | LLM calls | MCP calls | Tool output chars |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| lookup | mcp | 100% | 34,314 | $0.0311 | 5.2 | 3.0 | 2.0 | 8,992 |
| lookup | code | 100% | 8,620 | $0.0133 | 6.1 | 3.0 | 2.0 | 3,205 |
| lookup | ptc | 100% | 19,486 | $0.0204 | 7.9 | 3.0 | 3.0 | 3,741 |
| | **Δ code** | | **-75%** | **-57%** | **+16%** | | | |
| | **Δ ptc** | | **-43%** | **-35%** | **+50%** | | | |
| aggregate | mcp | 100% | 32,360 | $0.0323 | 5.7 | 3.0 | 2.0 | 7,528 |
| aggregate | code | 100% | 18,163 | $0.0491 | 9.1 | 3.3 | 3.0 | 11,117 |
| aggregate | ptc | 100% | 19,747 | $0.0233 | 8.5 | 3.0 | 2.7 | 2,657 |
| | **Δ code** | | **-44%** | **+52%** | **+60%** | | | |
| | **Δ ptc** | | **-39%** | **-28%** | **+49%** | | | |
| filter_list | mcp | 100% | 35,967 | $0.0520 | 6.1 | 3.0 | 2.0 | 14,909 |
| filter_list | code | 100% | 17,465 | $0.0294 | 9.8 | 4.0 | 3.0 | 4,515 |
| filter_list | ptc | 100% | 31,690 | $0.0540 | 12.1 | 3.3 | 3.0 | 9,787 |
| | **Δ code** | | **-51%** | **-43%** | **+62%** | | | |
| | **Δ ptc** | | **-12%** | **+4%** | **+101%** | | | |
| overdue | mcp | 100% | 41,800 | $0.0842 | 10.2 | 3.0 | 2.0 | 25,291 |
| overdue | code | 100% | 28,443 | $0.0555 | 11.2 | 4.0 | 2.0 | 12,782 |
| overdue | ptc | 100% | 33,267 | $0.0571 | 11.8 | 3.7 | 2.3 | 8,269 |
| | **Δ code** | | **-32%** | **-34%** | **+11%** | | | |
| | **Δ ptc** | | **-20%** | **-32%** | **+16%** | | | |
| write | mcp | 100% | 155,979 | $0.2500 | 11.8 | 4.0 | 4.0 | 82,116 |
| write | code | 100% | 23,895 | $0.0500 | 12.6 | 4.0 | 4.3 | 8,301 |
| write | ptc | 100% | 37,939 | $0.0792 | 13.8 | 4.0 | 4.3 | 8,442 |
| | **Δ code** | | **-85%** | **-80%** | **+7%** | | | |
| | **Δ ptc** | | **-76%** | **-68%** | **+17%** | | | |
| update | mcp | 100% | 42,479 | $0.0310 | 7.1 | 4.0 | 3.0 | 5,337 |
| update | code | 100% | 18,391 | $0.0300 | 10.2 | 4.0 | 4.0 | 5,171 |
| update | ptc | 100% | 23,410 | $0.0318 | 11.2 | 3.7 | 3.3 | 1,358 |
| | **Δ code** | | **-57%** | **-3%** | **+43%** | | | |
| | **Δ ptc** | | **-45%** | **+3%** | **+56%** | | | |

## How to read this

- **Context overhead** is the input size of the first model call: system prompt + tool definitions + question. MCP mode pays for every tool schema; code mode pays for a compact API listing.
- **Modes:** `code` = our Python `execute_python` over generated stubs; `ptc` = LangChain `langchain-quickjs` (JS in QuickJS/WASM, MCP tools as `tools.*`).
- **Tool output into context** is how much raw tool data the model had to read. Code mode keeps intermediate data in the Python process and only returns what the code prints.
- **Cost** uses `bench/pricing.py` (cache reads/writes priced separately). Output tokens include thinking tokens.
- Small run counts are noisy. Use `--runs 5` or more before drawing conclusions.
