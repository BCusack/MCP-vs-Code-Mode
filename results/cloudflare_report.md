# MCP vs Code Mode: benchmark report

- **Server(s):** notion  
- **Model(s):** claude-opus-5-5  
- **Tasks:** 6 x 3 run(s) per mode  
- **Raw data:** `results/raw/20261124T011144Z_notion.jsonl`

Values are means per task run unless noted. Δ = each mode vs **MCP** (negative is better for everything except success rate).

## Headline

| Metric | MCP | Code (py) | PTC (js) | CF stateless (js) | CF durable (py) | Δ Code (py) | Δ PTC (js) | Δ CF stateless (js) | Δ CF durable (py) | Best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| Success rate | 100% | 100% | 100% | 100% | 100% | +0% | +0% | +0% | +0% | - |
| Total tokens | 57,020 | 18,213 | 26,623 | 27,798 | 13,507 | -68% | -53% | -51% | -76% | code:state=fresh,discovery=search,describe=doc |
| Input tokens (incl. cached) | 56,526 | 17,558 | 25,962 | 27,034 | 12,675 | -69% | -54% | -52% | -78% | code:state=fresh,discovery=search,describe=doc |
| Uncached input tokens | 9 | 9 | 9 | 9 | 12 | +9% | +0% | +0% | +40% | mcp |
| Cache-read tokens | 43,910 | 13,894 | 19,963 | 20,916 | 9,811 | -68% | -55% | -52% | -78% | code:state=fresh,discovery=search,describe=doc |
| Output tokens (incl. thinking) | 494 | 655 | 661 | 764 | 832 | +33% | +34% | +55% | +68% | mcp |
| Context overhead (1st call input) | 8,942 | 2,132 | 5,474 | 5,457 | 867 | -76% | -39% | -39% | -90% | code:state=fresh,discovery=search,describe=doc |
| Cost (USD) | $0.0817 | $0.0342 | $0.0472 | $0.0500 | $0.0329 | -58% | -42% | -39% | -60% | code:state=fresh,discovery=search,describe=doc |
| Wall time (s) | 9.5 | 11.1 | 11.9 | 11.8 | 15.0 | +16% | +25% | +24% | +57% | mcp |
| LLM round-trips | 3.3 | 3.7 | 3.3 | 3.3 | 5.1 | +12% | +0% | +0% | +52% | mcp |
| Tool calls by model | 2.5 | 2.7 | 2.3 | 2.3 | 4.1 | +9% | -7% | -7% | +62% | ptc |
| Calls reaching MCP server | 2.5 | 3.1 | 2.8 | 3.7 | 2.7 | +24% | +11% | +49% | +9% | mcp |
| Tool output into context (chars) | 23,664 | 6,989 | 5,736 | 7,053 | 5,583 | -70% | -76% | -70% | -76% | code:state=fresh,discovery=search,describe=doc |
| Tool errors | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a | n/a | n/a | n/a | - |
| Total cost, all runs | $1.4712 | $0.6154 | $0.8496 | $0.9008 | $0.5924 | -58% | -42% | -39% | -60% | |
| Cost per successful run | $0.0817 | $0.0342 | $0.0472 | $0.0500 | $0.0329 | | | | | |

## Per task

| Task | Mode | Success | Total tokens | Cost | Wall s | LLM calls | MCP calls | Tool output chars |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| lookup | mcp | 100% | 34,316 | $0.0458 | 7.3 | 3.0 | 2.0 | 8,996 |
| lookup | code | 100% | 8,761 | $0.0185 | 6.6 | 3.0 | 2.3 | 3,325 |
| lookup | ptc | 100% | 19,353 | $0.0287 | 8.4 | 3.0 | 3.0 | 3,739 |
| lookup | ptc:state=fresh | 100% | 20,103 | $0.0243 | 7.3 | 3.0 | 3.3 | 5,234 |
| lookup | code:state=fresh,discovery=search,describe=doc | 100% | 7,574 | $0.0166 | 15.7 | 4.0 | 2.0 | 5,156 |
| | **Δ code** | | **-74%** | **-60%** | **-10%** | | | |
| | **Δ ptc** | | **-44%** | **-37%** | **+14%** | | | |
| | **Δ ptc:state=fresh** | | **-41%** | **-47%** | **-0%** | | | |
| | **Δ code:state=fresh,discovery=search,describe=doc** | | **-78%** | **-64%** | **+113%** | | | |
| aggregate | mcp | 100% | 32,537 | $0.0332 | 6.2 | 3.0 | 2.0 | 8,016 |
| aggregate | code | 100% | 20,255 | $0.0433 | 9.3 | 3.3 | 3.0 | 13,183 |
| aggregate | ptc | 100% | 21,547 | $0.0402 | 12.2 | 3.0 | 2.0 | 4,982 |
| aggregate | ptc:state=fresh | 100% | 25,145 | $0.0378 | 8.9 | 3.0 | 3.0 | 6,656 |
| aggregate | code:state=fresh,discovery=search,describe=doc | 100% | 10,146 | $0.0284 | 11.7 | 4.7 | 2.0 | 4,159 |
| | **Δ code** | | **-38%** | **+30%** | **+48%** | | | |
| | **Δ ptc** | | **-34%** | **+21%** | **+96%** | | | |
| | **Δ ptc:state=fresh** | | **-23%** | **+14%** | **+42%** | | | |
| | **Δ code:state=fresh,discovery=search,describe=doc** | | **-69%** | **-14%** | **+88%** | | | |
| filter_list | mcp | 100% | 35,937 | $0.0519 | 6.5 | 3.0 | 2.0 | 14,913 |
| filter_list | code | 100% | 17,601 | $0.0237 | 11.5 | 4.0 | 3.0 | 4,762 |
| filter_list | ptc | 100% | 20,974 | $0.0375 | 12.9 | 3.0 | 2.3 | 3,783 |
| filter_list | ptc:state=fresh | 100% | 19,831 | $0.0301 | 10.1 | 3.0 | 3.0 | 2,565 |
| filter_list | code:state=fresh,discovery=search,describe=doc | 100% | 10,499 | $0.0280 | 10.7 | 4.3 | 2.0 | 4,933 |
| | **Δ code** | | **-51%** | **-54%** | **+77%** | | | |
| | **Δ ptc** | | **-42%** | **-28%** | **+99%** | | | |
| | **Δ ptc:state=fresh** | | **-45%** | **-42%** | **+56%** | | | |
| | **Δ code:state=fresh,discovery=search,describe=doc** | | **-71%** | **-46%** | **+65%** | | | |
| overdue | mcp | 100% | 40,135 | $0.0764 | 12.6 | 3.0 | 2.0 | 21,808 |
| overdue | code | 100% | 25,896 | $0.0486 | 13.5 | 4.0 | 2.3 | 10,640 |
| overdue | ptc | 100% | 34,933 | $0.0610 | 12.5 | 3.7 | 2.0 | 10,062 |
| overdue | ptc:state=fresh | 100% | 27,600 | $0.0656 | 12.3 | 3.0 | 3.0 | 10,253 |
| overdue | code:state=fresh,discovery=search,describe=doc | 100% | 10,824 | $0.0326 | 14.4 | 5.3 | 3.0 | 2,817 |
| | **Δ code** | | **-35%** | **-36%** | **+7%** | | | |
| | **Δ ptc** | | **-13%** | **-20%** | **-1%** | | | |
| | **Δ ptc:state=fresh** | | **-31%** | **-14%** | **-2%** | | | |
| | **Δ code:state=fresh,discovery=search,describe=doc** | | **-73%** | **-57%** | **+14%** | | | |
| write | mcp | 100% | 156,739 | $0.2523 | 14.5 | 4.0 | 4.0 | 82,904 |
| write | code | 100% | 22,914 | $0.0471 | 15.4 | 4.0 | 4.0 | 7,418 |
| write | ptc | 100% | 38,571 | $0.0793 | 14.0 | 4.0 | 4.0 | 8,702 |
| write | ptc:state=fresh | 100% | 41,873 | $0.0923 | 17.3 | 4.3 | 6.0 | 10,073 |
| write | code:state=fresh,discovery=search,describe=doc | 100% | 27,460 | $0.0645 | 19.9 | 6.0 | 4.3 | 12,035 |
| | **Δ code** | | **-85%** | **-81%** | **+6%** | | | |
| | **Δ ptc** | | **-75%** | **-69%** | **-3%** | | | |
| | **Δ ptc:state=fresh** | | **-73%** | **-63%** | **+19%** | | | |
| | **Δ code:state=fresh,discovery=search,describe=doc** | | **-82%** | **-74%** | **+37%** | | | |
| update | mcp | 100% | 42,456 | $0.0308 | 10.0 | 4.0 | 3.0 | 5,349 |
| update | code | 100% | 13,851 | $0.0240 | 10.3 | 4.0 | 4.0 | 2,605 |
| update | ptc | 100% | 24,360 | $0.0365 | 11.5 | 3.3 | 3.3 | 3,147 |
| update | ptc:state=fresh | 100% | 32,238 | $0.0501 | 15.0 | 3.7 | 4.0 | 7,539 |
| update | code:state=fresh,discovery=search,describe=doc | 100% | 14,540 | $0.0274 | 17.7 | 6.0 | 3.0 | 4,399 |
| | **Δ code** | | **-67%** | **-22%** | **+2%** | | | |
| | **Δ ptc** | | **-43%** | **+18%** | **+15%** | | | |
| | **Δ ptc:state=fresh** | | **-24%** | **+63%** | **+50%** | | | |
| | **Δ code:state=fresh,discovery=search,describe=doc** | | **-66%** | **-11%** | **+77%** | | | |

## How to read this

- **Context overhead** is the input size of the first model call: system prompt + tool definitions + question. MCP mode pays for every tool schema; code mode pays for a compact API listing.
- **Modes:** `code` = our Python `execute_python` over generated stubs; `ptc` = LangChain `langchain-quickjs` (JS in QuickJS/WASM, MCP tools as `tools.*`).
- **Tool output into context** is how much raw tool data the model had to read. Code mode keeps intermediate data in the Python process and only returns what the code prints.
- **Cost** uses `bench/pricing.py` (cache reads/writes priced separately). Output tokens include thinking tokens.
- Small run counts are noisy. Use `--runs 5` or more before drawing conclusions.
