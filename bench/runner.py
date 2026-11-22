"""Run the benchmark: every task, in both modes, N times, same model, same MCP server.

    uv run bench-run                               # Notion, all tasks, 3 runs each
    uv run bench-run --server mock --runs 1        # offline smoke test (no Notion needed)
    uv run bench-run --tasks aggregate overdue --runs 5 --model claude-sonnet-5-5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from rich.console import Console

from .codemode import CodeRunner, McpBridge, build_code_tool, code_mode_prompt
from .metrics import RunMetrics, fill_from_messages
from .ptc import McpCallCounter, PromptCapture, build_ptc_middleware
from .pricing import price_for
from .servers import ServerSpec, get_server
from .tasks import Ctx, Task, load_state, tasks_for

console = Console()
ROOT = Path(__file__).resolve().parent.parent
RUN_TIMEOUT_S = 600

BASE_PROMPT = (
    "You are an assistant working in {label}. Complete the user's task yourself using your tools - "
    "do not ask clarifying questions. When done, give a short final answer."
)


def make_model(model: str, effort: str) -> ChatAnthropic:
    return ChatAnthropic(model=model, max_tokens=16_000, reasoning_effort=effort, max_retries=4)


async def run_one(*, spec: ServerSpec, session, mode: str, task: Task, ctx: Ctx, model: str,
                  effort: str, cache: bool, run: int, mcp_tools, raw_tools,
                  capture: PromptCapture | None = None, ptc_parse_json: bool = True) -> RunMetrics:
    rm = RunMetrics(server=spec.name, mode=mode, task=task.id, model=model, run=run)
    system = BASE_PROMPT.format(label=spec.label)
    bridge = None
    counter = McpCallCounter({t.name for t in mcp_tools})
    middleware: list = [AnthropicPromptCachingMiddleware(ttl="5m")] if cache else []
    if mode == "mcp":
        tools = mcp_tools
    elif mode == "code":
        bridge = McpBridge(session, raw_tools)
        tools = [build_code_tool(CodeRunner(bridge, spec.namespace))]
        system += "\n\n" + code_mode_prompt(spec.namespace, spec.label, raw_tools)
    elif mode == "ptc":
        tools = []  # the middleware adds `eval`; MCP tools are reachable only from code
        middleware.append(build_ptc_middleware(mcp_tools, parse_json=ptc_parse_json))
        rm.extra["ptc_parse_json"] = ptc_parse_json
    else:
        raise ValueError(f"unknown mode {mode!r}")
    if capture is not None:
        middleware.append(capture)  # last, so it sees the final request

    agent = create_agent(make_model(model, effort), tools, system_prompt=system, middleware=middleware)
    messages = []
    t0 = time.perf_counter()

    async def drive():
        nonlocal messages
        async for state in agent.astream({"messages": [{"role": "user", "content": task.prompt(ctx)}]},
                                         config={"recursion_limit": 60, "callbacks": [counter]},
                                         stream_mode="values"):
            messages = state["messages"]

    try:
        await asyncio.wait_for(drive(), RUN_TIMEOUT_S)
    except Exception as e:  # keep partial metrics
        rm.error = f"{type(e).__name__}: {e}"[:500]
    rm.wall_seconds = round(time.perf_counter() - t0, 2)
    fill_from_messages(rm, messages)
    if mode == "mcp":
        rm.mcp_calls = rm.agent_tool_calls
    elif mode == "code":
        rm.mcp_calls = bridge.calls
        rm.extra["mcp_errors_inside_code"] = bridge.errors
    else:  # ptc: counted from tool callbacks fired inside eval
        rm.mcp_calls = counter.calls
        rm.extra["mcp_errors_inside_code"] = counter.errors

    if rm.error is None:
        try:
            rm.success, detail = await asyncio.to_thread(task.check, rm.final_answer, ctx)
            if detail:
                rm.extra["check_detail"] = detail
        except Exception as e:
            rm.extra["check_detail"] = f"check crashed: {e}"
    if task.cleanup:
        try:
            await asyncio.to_thread(task.cleanup, ctx)
        except Exception as e:
            rm.extra["cleanup_error"] = str(e)[:300]
    return rm


async def main_async(a: argparse.Namespace) -> Path:
    spec = get_server(a.server)
    price_for(a.model)  # fail fast on unknown pricing
    state = load_state(spec.name)
    tasks = tasks_for(spec.name, a.tasks)
    modes = a.modes

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results" / "raw" / f"{stamp}_{spec.name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    client = MultiServerMCPClient({spec.name: spec.connection})
    async with client.session(spec.name) as session:
        raw_tools = (await session.list_tools()).tools
        mcp_tools = await load_mcp_tools(session)
        console.print(f"[bold]{spec.name}[/bold]: {len(raw_tools)} MCP tools | model={a.model} effort={a.effort} "
                      f"cache={'on' if a.cache else 'off'} | {len(tasks)} tasks x {len(modes)} modes x {a.runs} runs")
        captured: set[str] = set()  # modes whose first-call prompt was dumped to results/prompts/
        with out.open("w") as f:
            for task in tasks:
                for run in range(1, a.runs + 1):
                    # alternate which mode goes first to spread out cache/latency effects
                    order = modes if run % 2 else list(reversed(modes))
                    for mode in order:
                        ctx = Ctx(server=spec.name, run_tag=f"{mode}-{task.id}-{run}-{stamp}", state=state)
                        capture = PromptCapture() if mode not in captured else None
                        rm = await run_one(spec=spec, session=session, mode=mode, task=task, ctx=ctx,
                                           model=a.model, effort=a.effort, cache=a.cache, run=run,
                                           mcp_tools=mcp_tools, raw_tools=raw_tools, capture=capture,
                                           ptc_parse_json=a.ptc_parse_json)
                        if capture is not None and capture.system is not None:
                            captured.add(mode)
                            p = ROOT / "results" / "prompts" / f"{spec.name}_{mode}.md"
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.write_text(capture.as_markdown(mode))
                        f.write(json.dumps(rm.to_dict()) + "\n")
                        f.flush()
                        mark = "[green]PASS[/green]" if rm.success else "[red]FAIL[/red]"
                        console.print(f"{mark} {task.id:<12} {mode:<5} run{run}  tokens={rm.total_tokens:>8,}  "
                                      f"${rm.cost_usd:.4f}  {rm.wall_seconds:>6.1f}s  llm={rm.llm_calls} "
                                      f"mcp={rm.mcp_calls}" + (f"  [yellow]{rm.error or rm.extra.get('check_detail', '')}"[:160] + "[/yellow]"
                                                               if not rm.success else ""))
    console.print(f"raw results: {out}")
    return out


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default="notion")
    ap.add_argument("--tasks", nargs="*", help="task ids (default: all for the server)")
    ap.add_argument("--modes", nargs="*", default=["mcp", "code", "ptc"], choices=["mcp", "code", "ptc"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--ptc-parse-json", action=argparse.BooleanOptionalAction, default=True,
                    help="ptc mode: give code parsed JSON from MCP tools, like code mode (default on)")
    ap.add_argument("--model", default=os.environ.get("BENCH_MODEL", "claude-opus-5-5"))
    ap.add_argument("--effort", default=os.environ.get("BENCH_EFFORT", "medium"),
                    choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--no-cache", dest="cache", action="store_false", help="disable prompt caching")
    ap.add_argument("--no-report", action="store_true")
    a = ap.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[yellow]ANTHROPIC_API_KEY not set; relying on other Anthropic credentials if present.[/yellow]")
    raw = asyncio.run(main_async(a))
    if not a.no_report:
        from .report import build_report

        md = build_report([raw], name=raw.stem)  # per-run; `bench-report` publishes results/report.md
        console.print(f"[bold green]report: {md}[/bold green]")


if __name__ == "__main__":
    main()
