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


def test_mode_specs():
    import pytest

    from bench.runner import mode_name, parse_mode

    assert parse_mode("code") == ("code", {"state": "persist", "api": "compact", "discovery": "upfront"})
    assert parse_mode("code:api=full,state=fresh")[1] == {"state": "fresh", "api": "full", "discovery": "upfront"}
    assert mode_name("code:api=compact") == "code"  # defaults collapse to the plain name
    assert mode_name("code:api=full,state=fresh") == "code:state=fresh,api=full"  # fixed option order
    assert mode_name("ptc") == "ptc"
    for bad in ("code:api=huge", "code:color=red", "mcp:api=full", "nope"):
        with pytest.raises(ValueError):
            parse_mode(bad)


async def test_code_mode_variants():
    async with MultiServerMCPClient(CONN).session("mock") as s:
        tools = (await s.list_tools()).tools
        compact = code_mode_prompt("notion", "x", tools)
        full = code_mode_prompt("notion", "x", tools, api="full")
        names = code_mode_prompt("notion", "x", tools, discovery="names")
        assert len(full) >= len(compact)  # mock params carry no descriptions; see test_signature_full
        assert "async def" not in names and "notion.query_data_source  #" in names
        assert len(names) < len(compact)

        fresh = CodeRunner(McpBridge(s, tools), "notion", persist=False)
        assert (await fresh.run("x = 41\nx + 1")).strip() == "42"
        assert "NameError" in await fresh.run("x")  # state=fresh: nothing survives between calls
        assert "dict" in (await fresh.run("type(json.loads('{}')).__name__"))  # base globals still there


def test_signature_full():
    from mcp.types import Tool

    from bench.codemode import signature, signature_full

    t = Tool(name="API-patch-page", description="Notion | Update page properties", inputSchema={
        "type": "object", "required": ["page_id"],
        "properties": {
            "page_id": {"type": "string", "description": "The page ID"},
            "properties": {"type": "object", "description": "Property values to set",
                           "properties": {"Status": {"type": "object", "properties": {
                               "select": {"type": "object", "properties": {"name": {"type": "string"}}}}}}},
            "archived": {"type": ["boolean", "null"]},
            "icon": {"enum": ["emoji", "external"]},
        }})
    compact, full = signature("notion", t), signature_full("notion", t)
    assert "properties: dict = None" in compact  # compact stops at the top level
    assert '{"Status?": {"select?": {"name?": str}}}' in full  # full shows nested shape
    assert "archived: bool | None = None" in full and "Literal['emoji', 'external']" in full
    assert "Args:" in full and "page_id: The page ID" in full and "Args:" not in compact
