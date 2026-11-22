"""Turn a finished LangGraph message list into benchmark metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from .pricing import price_for


@dataclass
class RunMetrics:
    server: str
    mode: str  # "mcp" | "code"
    task: str
    model: str
    run: int
    success: bool = False
    error: str | None = None
    final_answer: str = ""
    wall_seconds: float = 0.0
    llm_calls: int = 0
    agent_tool_calls: int = 0  # tool calls the model made (code mode: execute_python calls)
    mcp_calls: int = 0  # actual calls that reached the MCP server
    tool_errors: int = 0
    tool_result_chars: int = 0  # tool output that was fed back into the model's context
    first_call_input_tokens: int = 0  # system prompt + tool defs + question: fixed overhead
    input_tokens: int = 0  # total, including cached
    uncached_input_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0
    output_tokens: int = 0  # includes thinking
    thinking_tokens: int = 0
    cost_usd: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["total_tokens"] = self.total_tokens
        return d


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict):
                parts.append(str(c.get("text") or c.get("content") or c))
        return "\n".join(parts)
    return str(content)


def final_answer(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            if isinstance(m.content, list):
                text = "\n".join(
                    c.get("text", "") for c in m.content if isinstance(c, dict) and c.get("type") == "text"
                )
            else:
                text = str(m.content)
            if text.strip():
                return text.strip()
    return ""


def fill_from_messages(rm: RunMetrics, messages: list[BaseMessage]) -> None:
    first = True
    for m in messages:
        if isinstance(m, AIMessage):
            rm.llm_calls += 1
            rm.agent_tool_calls += len(m.tool_calls or [])
            u = m.usage_metadata or {}
            details = u.get("input_token_details") or {}
            cache_read = details.get("cache_read") or 0
            w5 = (details.get("ephemeral_5m_input_tokens") or 0) or (details.get("cache_creation") or 0)
            w1 = details.get("ephemeral_1h_input_tokens") or 0
            inp = u.get("input_tokens") or 0
            rm.input_tokens += inp
            rm.cache_read_tokens += cache_read
            rm.cache_write_5m_tokens += w5
            rm.cache_write_1h_tokens += w1
            rm.uncached_input_tokens += max(inp - cache_read - w5 - w1, 0)
            rm.output_tokens += u.get("output_tokens") or 0
            rm.thinking_tokens += (u.get("output_token_details") or {}).get("reasoning") or 0
            if first:
                rm.first_call_input_tokens = inp
                first = False
        elif isinstance(m, ToolMessage):
            rm.tool_result_chars += len(_content_text(m.content))
            if getattr(m, "status", None) == "error":
                rm.tool_errors += 1
    p = price_for(rm.model)
    rm.cost_usd = (
        rm.uncached_input_tokens * p.input
        + rm.cache_read_tokens * p.cache_read
        + rm.cache_write_5m_tokens * p.cache_write_5m
        + rm.cache_write_1h_tokens * p.cache_write_1h
        + rm.output_tokens * p.output
    ) / 1_000_000
    rm.final_answer = final_answer(messages)
