# MCP vs Code Mode: benchmark report

- **Server(s):** notion  
- **Model(s):** claude-opus-5-5  
- **Tasks:** 6 x 3 run(s) per mode  
- **Raw data:** `results/raw/ablation_combined_notion.jsonl`

Values are means per task run unless noted. Δ = each mode vs **Code (py)** (negative is better for everything except success rate).

## Headline

| Metric | Code (py) | PTC (js) | code:api=full | code:discovery=index | code:discovery=index,describe=doc | code:discovery=names | code:state=fresh | Δ PTC (js) | Δ code:api=full | Δ code:discovery=index | Δ code:discovery=index,describe=doc | Δ code:discovery=names | Δ code:state=fresh | Best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| Success rate | 100% | 100% | 100% | 100% | 100% | 100% | 100% | +0% | +0% | +0% | +0% | +0% | +0% | - |
| Total tokens | 17,877 | 25,815 | 22,625 | 18,276 | 20,645 | 30,564 | 18,497 | +44% | +27% | +2% | +15% | +71% | +3% | code |
| Input tokens (incl. cached) | 17,214 | 25,164 | 21,921 | 17,626 | 19,942 | 29,818 | 17,789 | +46% | +27% | +2% | +16% | +73% | +3% | code |
| Uncached input tokens | 9 | 9 | 10 | 9 | 10 | 10 | 9 | -9% | +4% | -2% | +2% | +6% | -6% | ptc |
| Cache-read tokens | 13,025 | 19,313 | 19,115 | 12,760 | 15,396 | 22,107 | 13,060 | +48% | +47% | -2% | +18% | +70% | +0% | code:discovery=index |
| Output tokens (incl. thinking) | 663 | 651 | 703 | 650 | 704 | 746 | 708 | -2% | +6% | -2% | +6% | +12% | +7% | code:discovery=index |
| Context overhead (1st call input) | 2,132 | 5,474 | 4,448 | 2,007 | 2,016 | 1,327 | 2,145 | +157% | +109% | -6% | -5% | -38% | +1% | code:discovery=names |
| Cost (USD) | $0.0368 | $0.0461 | $0.0319 | $0.0399 | $0.0399 | $0.0579 | $0.0404 | +25% | -13% | +8% | +8% | +57% | +10% | code:api=full |
| Wall time (s) | 9.9 | 10.3 | 10.2 | 9.8 | 11.2 | 10.9 | 9.9 | +4% | +2% | -1% | +13% | +9% | +0% | code:discovery=index |
| LLM round-trips | 3.7 | 3.3 | 3.9 | 3.6 | 3.8 | 4.0 | 3.4 | -12% | +4% | -3% | +3% | +7% | -7% | ptc |
| Tool calls by model | 2.7 | 2.3 | 2.9 | 2.6 | 2.8 | 3.0 | 2.4 | -16% | +6% | -4% | +4% | +10% | -10% | ptc |
| Calls reaching MCP server | 2.9 | 2.9 | 3.2 | 2.8 | 3.1 | 2.9 | 3.4 | +2% | +10% | -2% | +8% | +0% | +17% | code:discovery=index |
| Tool output into context (chars) | 6,309 | 5,582 | 3,216 | 8,087 | 8,503 | 19,727 | 8,428 | -12% | -49% | +28% | +35% | +213% | +34% | code:api=full |
| Tool errors | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a | n/a | n/a | n/a | n/a | n/a | - |
| Total cost, all runs | $0.6625 | $0.8304 | $0.5745 | $0.7177 | $0.7176 | $1.0418 | $0.7273 | +25% | -13% | +8% | +8% | +57% | +10% | |
| Cost per successful run | $0.0368 | $0.0461 | $0.0319 | $0.0399 | $0.0399 | $0.0579 | $0.0404 | | | | | | | |

## Per task

| Task | Mode | Success | Total tokens | Cost | Wall s | LLM calls | MCP calls | Tool output chars |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| lookup | code | 100% | 8,637 | $0.0177 | 6.4 | 3.0 | 2.0 | 3,205 |
| lookup | ptc | 100% | 19,378 | $0.0287 | 7.2 | 3.0 | 3.0 | 3,606 |
| lookup | code:api=full | 100% | 15,907 | $0.0252 | 6.0 | 3.0 | 2.7 | 3,322 |
| lookup | code:discovery=index | 100% | 8,230 | $0.0175 | 4.7 | 3.0 | 2.0 | 3,205 |
| lookup | code:discovery=index,describe=doc | 100% | 8,271 | $0.0171 | 6.9 | 3.0 | 2.0 | 3,205 |
| lookup | code:discovery=names | 100% | 12,334 | $0.0319 | 6.5 | 3.3 | 2.0 | 10,237 |
| lookup | code:state=fresh | 100% | 9,296 | $0.0211 | 7.2 | 3.0 | 3.0 | 3,600 |
| | **Δ ptc** | | **+124%** | **+63%** | **+13%** | | | |
| | **Δ code:api=full** | | **+84%** | **+43%** | **-6%** | | | |
| | **Δ code:discovery=index** | | **-5%** | **-1%** | **-26%** | | | |
| | **Δ code:discovery=index,describe=doc** | | **-4%** | **-3%** | **+8%** | | | |
| | **Δ code:discovery=names** | | **+43%** | **+81%** | **+2%** | | | |
| | **Δ code:state=fresh** | | **+8%** | **+19%** | **+13%** | | | |
| aggregate | code | 100% | 15,271 | $0.0358 | 8.3 | 3.3 | 2.3 | 7,009 |
| aggregate | ptc | 100% | 20,647 | $0.0453 | 7.8 | 2.7 | 2.7 | 8,243 |
| aggregate | code:api=full | 100% | 20,628 | $0.0295 | 9.8 | 3.3 | 2.7 | 4,054 |
| aggregate | code:discovery=index | 100% | 18,781 | $0.0522 | 8.1 | 3.0 | 2.0 | 15,146 |
| aggregate | code:discovery=index,describe=doc | 100% | 18,877 | $0.0533 | 9.2 | 3.0 | 3.0 | 15,047 |
| aggregate | code:discovery=names | 100% | 27,650 | $0.0628 | 8.1 | 3.3 | 2.0 | 24,733 |
| aggregate | code:state=fresh | 100% | 19,283 | $0.0481 | 8.4 | 3.0 | 3.0 | 15,047 |
| | **Δ ptc** | | **+35%** | **+27%** | **-6%** | | | |
| | **Δ code:api=full** | | **+35%** | **-17%** | **+19%** | | | |
| | **Δ code:discovery=index** | | **+23%** | **+46%** | **-2%** | | | |
| | **Δ code:discovery=index,describe=doc** | | **+24%** | **+49%** | **+11%** | | | |
| | **Δ code:discovery=names** | | **+81%** | **+75%** | **-2%** | | | |
| | **Δ code:state=fresh** | | **+26%** | **+34%** | **+1%** | | | |
| filter_list | code | 100% | 17,694 | $0.0293 | 9.8 | 4.0 | 3.0 | 4,757 |
| filter_list | ptc | 100% | 18,895 | $0.0300 | 9.6 | 3.0 | 2.3 | 1,641 |
| filter_list | code:api=full | 100% | 21,059 | $0.0241 | 9.0 | 4.0 | 3.0 | 1,695 |
| filter_list | code:discovery=index | 100% | 15,377 | $0.0331 | 10.9 | 3.7 | 3.0 | 5,213 |
| filter_list | code:discovery=index,describe=doc | 100% | 20,458 | $0.0280 | 10.8 | 4.0 | 3.0 | 7,089 |
| filter_list | code:discovery=names | 100% | 20,196 | $0.0547 | 9.2 | 3.3 | 2.7 | 16,275 |
| filter_list | code:state=fresh | 100% | 13,767 | $0.0364 | 9.3 | 3.0 | 3.0 | 6,434 |
| | **Δ ptc** | | **+7%** | **+2%** | **-2%** | | | |
| | **Δ code:api=full** | | **+19%** | **-18%** | **-7%** | | | |
| | **Δ code:discovery=index** | | **-13%** | **+13%** | **+12%** | | | |
| | **Δ code:discovery=index,describe=doc** | | **+16%** | **-5%** | **+11%** | | | |
| | **Δ code:discovery=names** | | **+14%** | **+86%** | **-5%** | | | |
| | **Δ code:state=fresh** | | **-22%** | **+24%** | **-5%** | | | |
| overdue | code | 100% | 28,239 | $0.0593 | 11.2 | 4.0 | 2.0 | 12,548 |
| overdue | ptc | 100% | 35,173 | $0.0596 | 12.5 | 3.7 | 2.0 | 9,756 |
| overdue | code:api=full | 100% | 31,139 | $0.0428 | 12.8 | 5.0 | 2.0 | 4,156 |
| overdue | code:discovery=index | 100% | 27,757 | $0.0540 | 11.8 | 4.0 | 2.0 | 12,548 |
| overdue | code:discovery=index,describe=doc | 100% | 39,409 | $0.0635 | 17.1 | 5.0 | 2.7 | 14,872 |
| overdue | code:discovery=names | 100% | 36,375 | $0.0667 | 10.6 | 4.0 | 2.0 | 23,095 |
| overdue | code:state=fresh | 100% | 23,975 | $0.0502 | 11.7 | 3.7 | 2.7 | 10,447 |
| | **Δ ptc** | | **+25%** | **+0%** | **+12%** | | | |
| | **Δ code:api=full** | | **+10%** | **-28%** | **+15%** | | | |
| | **Δ code:discovery=index** | | **-2%** | **-9%** | **+5%** | | | |
| | **Δ code:discovery=index,describe=doc** | | **+40%** | **+7%** | **+53%** | | | |
| | **Δ code:discovery=names** | | **+29%** | **+12%** | **-5%** | | | |
| | **Δ code:state=fresh** | | **-15%** | **-15%** | **+4%** | | | |
| write | code | 100% | 22,733 | $0.0491 | 13.5 | 4.0 | 4.0 | 7,279 |
| write | ptc | 100% | 36,389 | $0.0768 | 13.2 | 4.0 | 4.0 | 7,016 |
| write | code:api=full | 100% | 24,288 | $0.0367 | 14.1 | 4.0 | 4.3 | 3,156 |
| write | code:discovery=index | 100% | 22,375 | $0.0476 | 12.8 | 4.0 | 4.0 | 7,309 |
| write | code:discovery=index,describe=doc | 100% | 22,876 | $0.0482 | 12.4 | 4.0 | 4.0 | 7,663 |
| write | code:discovery=names | 100% | 49,861 | $0.0912 | 17.4 | 5.0 | 5.0 | 24,703 |
| write | code:state=fresh | 100% | 24,534 | $0.0523 | 13.1 | 4.0 | 4.7 | 8,847 |
| | **Δ ptc** | | **+60%** | **+56%** | **-3%** | | | |
| | **Δ code:api=full** | | **+7%** | **-25%** | **+5%** | | | |
| | **Δ code:discovery=index** | | **-2%** | **-3%** | **-6%** | | | |
| | **Δ code:discovery=index,describe=doc** | | **+1%** | **-2%** | **-8%** | | | |
| | **Δ code:discovery=names** | | **+119%** | **+86%** | **+29%** | | | |
| | **Δ code:state=fresh** | | **+8%** | **+7%** | **-3%** | | | |
| update | code | 100% | 14,690 | $0.0296 | 10.6 | 4.0 | 4.0 | 3,055 |
| update | ptc | 100% | 24,407 | $0.0364 | 11.6 | 3.3 | 3.7 | 3,232 |
| update | code:api=full | 100% | 22,729 | $0.0331 | 9.3 | 4.0 | 4.3 | 2,912 |
| update | code:discovery=index | 100% | 17,137 | $0.0348 | 10.7 | 4.0 | 4.0 | 5,098 |
| update | code:discovery=index,describe=doc | 100% | 13,982 | $0.0291 | 11.0 | 4.0 | 4.0 | 3,145 |
| update | code:discovery=names | 100% | 36,969 | $0.0400 | 13.4 | 5.0 | 3.7 | 19,319 |
| update | code:state=fresh | 100% | 20,125 | $0.0344 | 10.1 | 4.0 | 4.0 | 6,190 |
| | **Δ ptc** | | **+66%** | **+23%** | **+10%** | | | |
| | **Δ code:api=full** | | **+55%** | **+12%** | **-12%** | | | |
| | **Δ code:discovery=index** | | **+17%** | **+18%** | **+1%** | | | |
| | **Δ code:discovery=index,describe=doc** | | **-5%** | **-2%** | **+3%** | | | |
| | **Δ code:discovery=names** | | **+152%** | **+35%** | **+26%** | | | |
| | **Δ code:state=fresh** | | **+37%** | **+16%** | **-5%** | | | |

## How to read this

- **Context overhead** is the input size of the first model call: system prompt + tool definitions + question. MCP mode pays for every tool schema; code mode pays for a compact API listing.
- **Modes:** `code` = our Python `execute_python` over generated stubs; `ptc` = LangChain `langchain-quickjs` (JS in QuickJS/WASM, MCP tools as `tools.*`).
- **Tool output into context** is how much raw tool data the model had to read. Code mode keeps intermediate data in the Python process and only returns what the code prints.
- **Cost** uses `bench/pricing.py` (cache reads/writes priced separately). Output tokens include thinking tokens.
- Small run counts are noisy. Use `--runs 5` or more before drawing conclusions.
