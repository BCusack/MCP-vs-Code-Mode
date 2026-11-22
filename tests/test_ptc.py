"""ptc mode details: raw vs parsed MCP results inside JS, and MCP error counting."""

from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from bench import runner
from bench.ptc import parse_mcp_content
from bench.servers import get_server
from bench.tasks import Ctx, tasks_for
from tests.test_pipeline import USAGE, FakeToolModel

PROBE = 'const r = await tools.queryDataSource({ data_source_id: "ds-bench-projects" }); ' \
        '[Array.isArray(r), typeof r.has_more].join(",")'
BAD = 'try { await tools.queryDataSource({ data_source_id: "nope" }); "no error" } ' \
      'catch (e) { "rejected" }'


class SpyModel(FakeToolModel):
    seen: list = []

    async def _agenerate(self, messages, *a, **k):
        SpyModel.seen.append(messages)
        return await super()._agenerate(messages, *a, **k)


async def _run_eval(monkeypatch, code: str, parse_json: bool):
    spec = get_server("mock")
    task = tasks_for("mock", ["aggregate"])[0]
    script = iter([
        AIMessage(content="", tool_calls=[{"name": "eval", "args": {"code": code}, "id": "c1", "type": "tool_call"}],
                  usage_metadata=USAGE),
        AIMessage(content="done", usage_metadata=USAGE),
    ])
    SpyModel.seen = []
    monkeypatch.setattr(runner, "make_model", lambda m, e: SpyModel(messages=script))
    async with MultiServerMCPClient({"mock": spec.connection}).session("mock") as s:
        rm = await runner.run_one(spec=spec, session=s, mode="ptc", task=task, ctx=Ctx("mock", "t", {}),
                                  model="claude-opus-5-5", effort="medium", cache=False, run=1,
                                  mcp_tools=await load_mcp_tools(s), raw_tools=(await s.list_tools()).tools,
                                  ptc_parse_json=parse_json)
    out = [m.content for m in SpyModel.seen[-1] if isinstance(m, ToolMessage)][0]
    return rm, out


async def test_parsed_vs_raw(monkeypatch):
    rm, out = await _run_eval(monkeypatch, PROBE, parse_json=True)
    assert "false,boolean" in out and rm.mcp_calls == 1 and rm.extra["ptc_parse_json"] is True
    rm, out = await _run_eval(monkeypatch, PROBE, parse_json=False)
    assert "true,undefined" in out  # raw MCP content blocks: an array of {type, text}


async def test_mcp_error_rejects_and_is_counted(monkeypatch):
    rm, out = await _run_eval(monkeypatch, BAD, parse_json=True)
    assert "rejected" in out
    assert rm.mcp_calls == 1 and rm.extra["mcp_errors_inside_code"] == 1


def test_parse_mcp_content():
    assert parse_mcp_content([{"type": "text", "text": '{"a": 1}'}]) == {"a": 1}
    assert parse_mcp_content('{"a": 1}') == {"a": 1}
    assert parse_mcp_content([{"type": "text", "text": "not json"}]) == "not json"
    assert parse_mcp_content([], {"structured_content": {"b": 2}}) == {"b": 2}
