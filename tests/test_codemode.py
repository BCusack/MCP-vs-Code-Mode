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

    assert parse_mode("code") == ("code", {"state": "persist", "api": "compact", "discovery": "upfront",
                                           "describe": "json"})
    assert parse_mode("code:api=full,state=fresh")[1] == {"state": "fresh", "api": "full", "discovery": "upfront",
                                                          "describe": "json"}
    assert mode_name("code:describe=doc,discovery=index") == "code:discovery=index,describe=doc"
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
        # the default prompt is unchanged by the describe option
        assert code_mode_prompt("notion", "x", tools, describe="json") == compact

        # discovery=index: skills-style YAML frontmatter, generated from the schema
        index = code_mode_prompt("notion", "x", tools, discovery="index")
        assert "```yaml\n- name: notion." in index and "- name: notion.query_data_source\n  description: " in index
        assert "  required: [data_source_id]" in index and "async def" not in index
        assert len(names) < len(index)  # vs compact: see Notion sizes in docs/PLAN.md (mock tools are tiny)

        # describe=doc returns the readable signature, and accepts the qualified name
        doc = CodeRunner(McpBridge(s, tools), "notion", describe="doc")
        out = await doc.run('print(describe("notion.query_data_source"))')
        assert out.startswith("async def notion.query_data_source(data_source_id: str") and "input_schema" not in out
        raw = CodeRunner(McpBridge(s, tools), "notion")
        assert '"input_schema"' in await raw.run('print(describe("query_data_source"))')

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


def test_cloudflare_mode_specs():
    import pytest

    from bench.runner import mode_name, parse_mode

    assert parse_mode("ptc") == ("ptc", {"state": "persist"})
    assert mode_name("ptc:state=persist") == "ptc"
    assert mode_name("cf-stateless") == "ptc:state=fresh"
    assert mode_name("cf-durable") == "code:state=fresh,discovery=search,describe=doc"
    with pytest.raises(ValueError):
        parse_mode("ptc:api=full")


async def test_discovery_search():
    async with MultiServerMCPClient(CONN).session("mock") as s:
        tools = (await s.list_tools()).tools
        prompt = code_mode_prompt("notion", "x", tools, discovery="search")
        assert "async def" not in prompt and "search(" in prompt
        assert "notion.query_data_source" not in prompt  # nothing listed up front

        r = CodeRunner(McpBridge(s, tools), "notion", persist=False, describe="doc", search=True)
        out = await r.run('print(search("query data source rows"))')
        assert out.splitlines()[0].startswith("notion.query_data_source")  # best match ranks first
        assert "no functions match" in await r.run('print(search("zzzz"))')
        assert "NameError" in await CodeRunner(McpBridge(s, tools), "notion").run("search('x')")  # only when enabled


def test_ptc_fresh_state_uses_call_mode():
    from bench.ptc import build_ptc_middleware

    assert build_ptc_middleware([], persist=False)._mode == "call"  # fresh QuickJS REPL per eval
    assert build_ptc_middleware([])._mode == "turn"
