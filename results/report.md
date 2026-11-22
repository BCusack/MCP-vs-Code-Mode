# MCP vs Code Mode: benchmark report

- **Server(s):** notion  
- **Model(s):** claude-opus-5-5  
- **Tasks:** 6 x 3 run(s) per mode  
- **Raw data:** `results/raw/20261122T213907Z_notion.jsonl`

Values are means per task run unless noted. Delta = code mode vs classic MCP (negative is better for everything except success rate).

## Headline

| Metric | MCP | Code mode | Delta | Better |
|---|---:|---:|---:|:---:|
| Success rate | 100% | 100% | +0% | - |
| Total tokens | 48,901 | 18,270 | -63% | code |
| Input tokens (incl. cached) | 48,421 | 17,611 | -64% | code |
| Uncached input tokens | 9 | 9 | +6% | mcp |
| Cache-read tokens | 38,129 | 12,856 | -66% | code |
| Output tokens (incl. thinking) | 481 | 659 | +37% | mcp |
| Context overhead (1st call input) | 8,942 | 2,132 | -76% | code |
| Cost (USD) | $0.0687 | $0.0395 | -42% | code |
| Wall time (s) | 8.3 | 9.9 | +19% | mcp |
| LLM round-trips | 3.3 | 3.6 | +8% | mcp |
| Tool calls by model | 2.5 | 2.6 | +4% | mcp |
| Calls reaching MCP server | 2.5 | 3.0 | +20% | mcp |
| Tool output into context (chars) | 19,066 | 7,713 | -60% | code |
| Tool errors | 0.00 | 0.00 | n/a | - |
| Total cost, all runs | $1.2363 | $0.7114 | -42% | |
| Cost per successful run | $0.0687 | $0.0395 | | |

## Per task

| Task | Mode | Success | Total tokens | Cost | Wall s | LLM calls | MCP calls | Tool output chars |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| lookup | mcp | 100% | 32,118 | $0.0402 | 6.1 | 3.0 | 2.0 | 6,611 |
| lookup | code | 100% | 8,593 | $0.0172 | 7.4 | 3.0 | 2.0 | 3,205 |
| | **delta** | | **-73%** | **-57%** | **+22%** | | | |
| aggregate | mcp | 100% | 32,570 | $0.0335 | 6.1 | 3.0 | 2.0 | 8,016 |
| aggregate | code | 100% | 18,423 | $0.0513 | 8.7 | 3.0 | 3.0 | 14,244 |
| | **delta** | | **-43%** | **+53%** | **+44%** | | | |
| filter_list | mcp | 100% | 37,731 | $0.0605 | 6.7 | 3.0 | 2.0 | 18,381 |
| filter_list | code | 100% | 15,951 | $0.0332 | 9.7 | 3.7 | 3.0 | 4,820 |
| | **delta** | | **-58%** | **-45%** | **+44%** | | | |
| overdue | mcp | 100% | 41,590 | $0.0826 | 10.2 | 3.0 | 2.0 | 25,557 |
| overdue | code | 100% | 28,251 | $0.0595 | 10.3 | 4.0 | 2.0 | 12,678 |
| | **delta** | | **-32%** | **-28%** | **+0%** | | | |
| write | mcp | 100% | 106,958 | $0.1646 | 12.6 | 4.0 | 4.0 | 50,480 |
| write | code | 100% | 23,299 | $0.0494 | 13.2 | 4.0 | 4.0 | 7,798 |
| | **delta** | | **-78%** | **-70%** | **+5%** | | | |
| update | mcp | 100% | 42,440 | $0.0307 | 8.2 | 4.0 | 3.0 | 5,349 |
| update | code | 100% | 15,103 | $0.0266 | 10.2 | 4.0 | 4.0 | 3,532 |
| | **delta** | | **-64%** | **-13%** | **+25%** | | | |

## How to read this

- **Context overhead** is the input size of the first model call: system prompt + tool definitions + question. MCP mode pays for every tool schema; code mode pays for a compact API listing.
- **Tool output into context** is how much raw tool data the model had to read. Code mode keeps intermediate data in the Python process and only returns what the code prints.
- **Cost** uses `bench/pricing.py` (cache reads/writes priced separately). Output tokens include thinking tokens.
- Small run counts are noisy. Use `--runs 5` or more before drawing conclusions.
