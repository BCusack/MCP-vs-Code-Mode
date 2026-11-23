"""End-to-end pipeline test with a scripted fake LLM (no API key): runner -> metrics -> report."""

import json
import sys

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from bench import fixture, runner
from bench.report import build_report
from bench.servers import get_server
from bench.tasks import Ctx, tasks_for

USAGE = {"input_tokens": 1000, "output_tokens": 50, "total_tokens": 1050,
         "input_token_details": {"cache_read": 400, "cache_creation": 100}}

CODE = """
rows, cur = [], None
while True:
    r = await notion.query_data_source(data_source_id="ds-bench-projects", start_cursor=cur)
    rows += r["results"]
    if not r["has_more"]:
        break
    cur = r["next_cursor"]
sum(x["properties"]["Points"]["number"] for x in rows
    if x["properties"]["Owner"]["select"]["name"] == "Diego"
    and x["properties"]["Status"]["select"]["name"] == "In progress")
"""


# PTC (default --ptc-parse-json): MCP tools resolve to parsed objects inside JS, like code mode.
JS = """
let rows = [], cur = null;
while (true) {
  const d = await tools.queryDataSource({ data_source_id: "ds-bench-projects", start_cursor: cur });
  rows.push(...d.results);
  if (!d.has_more) break;
  cur = d.next_cursor;
}
rows.filter(x => x.properties.Owner.select.name === "Diego"
              && x.properties.Status.select.name === "In progress")
    .reduce((a, x) => a + x.properties.Points.number, 0);
"""


class FakeToolModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kw):
        return self


def _script(mode: str):
    answer = str(fixture.expected_points("Diego", "In progress"))
    if mode == "code":
        call = {"name": "execute_python", "args": {"code": CODE}, "id": "c1", "type": "tool_call"}
    elif mode == "ptc":
        call = {"name": "eval", "args": {"code": JS}, "id": "c1", "type": "tool_call"}
    else:
        call = {"name": "query_data_source", "args": {"data_source_id": "ds-bench-projects"}, "id": "c1",
                "type": "tool_call"}
    return iter([
        AIMessage(content="", tool_calls=[call], usage_metadata=USAGE),
        AIMessage(content=f"The total is {answer}.", usage_metadata=USAGE),
    ])


async def test_pipeline(tmp_path, monkeypatch):
    spec = get_server("mock")
    task = tasks_for("mock", ["aggregate"])[0]
    rows = []
    async with MultiServerMCPClient({"mock": spec.connection}).session("mock") as s:
        raw_tools = (await s.list_tools()).tools
        mcp_tools = await load_mcp_tools(s)
        for mode in ("mcp", "code", "ptc"):
            monkeypatch.setattr(runner, "make_model", lambda m, e, _mode=mode: FakeToolModel(messages=_script(_mode)))
            rm = await runner.run_one(spec=spec, session=s, mode=mode, task=task, ctx=Ctx("mock", "t", {}),
                                      model="claude-opus-5-5", effort="medium", cache=False, run=1,
                                      mcp_tools=mcp_tools, raw_tools=raw_tools)
            assert rm.error is None, rm.error
            assert rm.success, rm.extra
            assert rm.llm_calls == 2 and rm.input_tokens == 2000 and rm.cache_read_tokens == 800
            # 2 calls x (500 uncached*$4 + 400 read*$0.20 + 100 write*$5 + 50 out*$20) / 1M
            assert abs(rm.cost_usd - 2 * (500 * 4 + 400 * 0.2 + 100 * 5 + 50 * 20) / 1e6) < 1e-9
            rows.append(rm)
    assert rows[0].mcp_calls == 1 and rows[1].mcp_calls == 6
    # ptc calls happen inside eval; counted via tool callbacks, not model tool calls
    assert rows[2].mcp_calls == 6 and rows[2].agent_tool_calls == 1
    # code modes return only the result; MCP mode dumps a raw page of rows into context
    assert rows[1].tool_result_chars < rows[0].tool_result_chars
    assert rows[2].tool_result_chars < rows[0].tool_result_chars

    raw = tmp_path / "r.jsonl"
    raw.write_text("\n".join(json.dumps(r.to_dict()) for r in rows))
    monkeypatch.setattr("bench.report.ROOT", tmp_path)
    md = build_report([raw]).read_text()
    assert "## Headline" in md and "| aggregate | code |" in md
    # per-run reports (what bench-run writes) never touch the published report
    per_run = build_report([raw], name="r")
    assert per_run == tmp_path / "results" / "reports" / "r.md" and per_run.exists()
    assert (tmp_path / "results" / "reports" / "r.summary.json").exists()
