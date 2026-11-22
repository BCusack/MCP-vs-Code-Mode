"""Offline tests: code-mode bridge/runner against the mock MCP server. No API keys needed."""

import sys

from langchain_mcp_adapters.client import MultiServerMCPClient

from bench import fixture
from bench.codemode import CodeRunner, McpBridge, code_mode_prompt, py_name

CONN = {"mock": {"transport": "stdio", "command": sys.executable, "args": ["-m", "bench.mock_server"]}}


def test_py_name():
    assert py_name("API-post-search") == "post_search"
    assert py_name("query-data-source") == "query_data_source"
    assert py_name("class") == "t_class"


async def test_code_mode_aggregates_in_code():
    async with MultiServerMCPClient(CONN).session("mock") as s:
        tools = (await s.list_tools()).tools
        bridge = McpBridge(s, tools)
        runner = CodeRunner(bridge, "notion")
        assert "async def notion.query_data_source" in code_mode_prompt("notion", "x", tools)

        out = await runner.run("""
rows, cur = [], None
while True:
    r = await notion.query_data_source(data_source_id="ds-bench-projects", start_cursor=cur)
    rows += r["results"]
    if not r["has_more"]:
        break
    cur = r["next_cursor"]
p = lambda row, k: row["properties"][k]
total = sum(p(x, "Points")["number"] for x in rows
            if p(x, "Owner")["select"]["name"] == "Diego" and p(x, "Status")["select"]["name"] == "In progress")
total
""")
        assert out.strip() == str(fixture.expected_points("Diego", "In progress"))
        assert bridge.calls == 6  # 60 rows / 10 per page

        # state persists between calls; disallowed imports are surfaced as errors
        assert (await runner.run("len(rows)")).strip() == "60"
        assert "not allowed" in await runner.run("import os")
        assert "not allowed" in await runner.run("import subprocess")
