"""PTC mode: LangChain's off-the-shelf code mode (`langchain-quickjs`).

The model gets one `eval` tool and writes JavaScript that runs in QuickJS (WebAssembly,
in-process). The MCP tools are exposed inside the interpreter as `tools.<camelCaseName>()`,
and the middleware renders them as TypeScript signatures in the system prompt. The MCP
tools are NOT given to the model directly, matching our own `code` mode.

Limits are aligned with `bench.codemode` (timeout, output size) so the comparison is
about the design, not the defaults. By default the MCP tools are wrapped to return parsed
JSON, as `McpBridge` does for code mode (`--no-ptc-parse-json` gives the raw behavior). State persists for the whole run (one agent invoke),
like our `CodeRunner`.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from langchain.agents.middleware import AgentMiddleware
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.tools import BaseTool, StructuredTool
from langchain_quickjs import CodeInterpreterMiddleware

from .codemode import EXEC_TIMEOUT_S, MAX_OUTPUT_CHARS


def parse_mcp_content(content: Any, artifact: Any = None) -> Any:
    """MCP result -> native value, the same rules as `McpBridge.call` in code mode.

    Prefer `structuredContent`; otherwise join the text blocks and parse JSON, falling
    back to the raw text.
    """
    structured = artifact.get("structured_content") if isinstance(artifact, dict) else None
    if structured is not None:
        return structured
    if isinstance(content, str):
        text = content
    else:
        text = "\n".join(b.get("text", "") for b in content or []
                         if isinstance(b, dict) and b.get("type") == "text")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def with_parsed_json(tool: BaseTool) -> BaseTool:
    """Wrap an MCP adapter tool so code inside `eval` gets parsed JSON, not content blocks.

    Without this, `tools.x()` resolves to `[{type: "text", text: "<json>"}]` even though
    the middleware's prompt tells the model results are already typed. Errors raise (a
    rejected Promise in JS), as `McpBridge` raises in code mode; `handle_tool_error=False`
    makes them fire `on_tool_error`, so `McpCallCounter` counts them.
    """
    inner = tool.coroutine
    if inner is None:
        raise TypeError(f"{tool.name} has no coroutine; expected an MCP adapter tool")

    async def call(**kwargs: Any) -> Any:
        args = {k: v for k, v in kwargs.items() if v is not None}  # JS null == omitted, as in code mode
        content, artifact = await inner(**args)
        return parse_mcp_content(content, artifact)

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        coroutine=call,
        metadata=tool.metadata,
        handle_tool_error=False,
    )


def build_ptc_middleware(mcp_tools: list[BaseTool], *, parse_json: bool = True) -> CodeInterpreterMiddleware:
    return CodeInterpreterMiddleware(
        ptc=[with_parsed_json(t) for t in mcp_tools] if parse_json else list(mcp_tools),
        timeout=float(EXEC_TIMEOUT_S),  # default 5s is too short for real API calls
        max_result_chars=MAX_OUTPUT_CHARS,  # default 4000; match code mode
        mode="turn",  # one run == one turn; state persists across evals within it
        subagents=False,  # no `task()` global: keep the surface equal to code mode
    )


class McpCallCounter(AsyncCallbackHandler):
    """Counts MCP tool invocations, including those made from inside `eval`.

    The PTC bridge passes the run's callbacks to each `tool.arun`, so tool start/error
    events fire for calls that never appear as model tool calls.
    """

    def __init__(self, tool_names: set[str]):
        self.tool_names = tool_names
        self.calls = 0
        self.errors = 0
        self._mcp_runs: set[UUID] = set()

    async def on_tool_start(self, serialized: dict[str, Any] | None, input_str: str, *,
                            run_id: UUID, **kwargs: Any) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name")
        if name in self.tool_names:
            self.calls += 1
            self._mcp_runs.add(run_id)

    async def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        if run_id in self._mcp_runs:
            self.errors += 1


class PromptCapture(AgentMiddleware):
    """Records what the model saw on its first call: system prompt and tool schemas.

    Must be the LAST middleware so it sees the request after every other middleware
    (e.g. the interpreter's prompt addendum) has modified it.
    """

    def __init__(self) -> None:
        super().__init__()
        self.system: str | None = None
        self.tools: list[dict[str, Any]] = []

    def _record(self, request: Any) -> None:
        if self.system is not None:
            return
        msg = request.system_message
        self.system = (msg.text if hasattr(msg, "text") else str(msg.content)) if msg is not None else ""
        for t in request.tools or []:
            if isinstance(t, BaseTool):
                schema = t.tool_call_schema
                schema = schema if isinstance(schema, dict) else schema.model_json_schema()
                self.tools.append({"name": t.name, "description": t.description, "input_schema": schema})
            else:
                self.tools.append(t if isinstance(t, dict) else {"repr": repr(t)})

    def wrap_model_call(self, request, handler):
        self._record(request)
        return handler(request)

    async def awrap_model_call(self, request, handler):
        self._record(request)
        return await handler(request)

    def as_markdown(self, mode: str) -> str:
        import json

        tools = json.dumps(self.tools, indent=1, default=str)
        return (f"# What the model saw: `{mode}` mode\n\n## System prompt\n\n````\n{self.system}\n````\n\n"
                f"## Tools ({len(self.tools)})\n\n```json\n{tools}\n```\n")
