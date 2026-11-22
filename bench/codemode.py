"""Code mode: expose an MCP server to the model as a Python API instead of as tools.

The model gets a single tool, `execute_python`. Inside it, every MCP tool is an async
function on a namespace object (e.g. `await notion.query_data_source(...)`). Results
stay in the Python process; only what the code prints goes back into the model's
context. This mirrors Cloudflare's "Code Mode" and Anthropic's "code execution with MCP".

NOTE: this runs model-written code in-process with a restricted import list. It is a
guard against accidents, NOT a security sandbox. Only point it at a test workspace.
"""

from __future__ import annotations

import ast
import asyncio
import builtins
import contextlib
import io
import json
import keyword
import re
import textwrap
import traceback
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.types import Tool as McpTool

ALLOWED_IMPORTS = {
    "json", "re", "math", "statistics", "datetime", "collections", "itertools",
    "functools", "operator", "string", "textwrap", "decimal", "fractions", "uuid", "asyncio",
}
MAX_OUTPUT_CHARS = 20_000
EXEC_TIMEOUT_S = 120


def py_name(tool_name: str) -> str:
    name = re.sub(r"\W+", "_", tool_name).strip("_").lower()
    name = re.sub(r"^api_", "", name)  # notion-mcp-server prefixes tools with "API-"
    if not name or name[0].isdigit() or keyword.iskeyword(name):
        name = f"t_{name}"
    return name


_JSON_TO_PY = {"string": "str", "integer": "int", "number": "float", "boolean": "bool",
               "array": "list", "object": "dict", "null": "None"}


def _type_of(schema: dict[str, Any]) -> str:
    t = schema.get("type")
    if isinstance(t, list):
        return " | ".join(_JSON_TO_PY.get(x, "Any") for x in t)
    if t:
        return _JSON_TO_PY.get(t, "Any")
    if "enum" in schema:
        return "Literal[" + ", ".join(repr(e) for e in schema["enum"][:6]) + "]"
    for k in ("anyOf", "oneOf"):
        if k in schema:
            return " | ".join(_type_of(s) for s in schema[k][:4])
    return "Any"


def signature(namespace: str, tool: McpTool) -> str:
    """Compact one-function Python stub (the 'typed API' the model codes against)."""
    schema = tool.inputSchema or {}
    props: dict[str, Any] = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])
    params = []
    for pname, pschema in sorted(props.items(), key=lambda kv: kv[0] not in required):
        t = _type_of(pschema or {})
        params.append(f"{pname}: {t}" if pname in required else f"{pname}: {t} = None")
    desc = (tool.description or "").strip().splitlines()[0][:160] if tool.description else ""
    sig = f"async def {namespace}.{py_name(tool.name)}({', '.join(params)}) -> Any"
    return f"{sig}\n    \"\"\"{desc}\"\"\"" if desc else sig


def _py_type_full(schema: Any, depth: int = 0) -> str:
    """Nested Python-ish type for `api=full`: inline TypedDict-style dicts, Literals, unions."""
    if not isinstance(schema, dict):
        return "Any"
    if "enum" in schema:
        vals = schema["enum"][:12]
        return "Literal[" + ", ".join(repr(v) for v in vals) + (", ..." if len(schema["enum"]) > 12 else "") + "]"
    for k in ("anyOf", "oneOf"):
        if k in schema:
            return " | ".join(dict.fromkeys(_py_type_full(x, depth) for x in schema[k]))
    t = schema.get("type")
    if isinstance(t, list):
        return " | ".join(_py_type_full({**schema, "type": x}, depth) for x in t)
    if t == "array":
        return f"list[{_py_type_full(schema.get('items'), depth + 1)}]"
    if t == "object":
        props = schema.get("properties") or {}
        if not props or depth >= 3:
            return "dict"
        req = set(schema.get("required") or [])
        inner = ", ".join(f'"{k}{"" if k in req else "?"}": {_py_type_full(v, depth + 1)}' for k, v in props.items())
        return "{" + inner + "}"
    return _JSON_TO_PY.get(t, "Any") if t else "Any"


def signature_full(namespace: str, tool: McpTool) -> str:
    """`api=full`: nested parameter types plus an Args section with each parameter's description.

    Roughly the detail Cloudflare's TS interfaces (with doc comments) and langchain-quickjs's TS
    signatures give the model, so `compact` vs `full` measures what that detail is worth.
    """
    from langchain_core.utils.json_schema import dereference_refs

    schema = dereference_refs(tool.inputSchema or {})
    props: dict[str, Any] = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])
    params, args_doc = [], []
    for pname, pschema in sorted(props.items(), key=lambda kv: kv[0] not in required):
        t = _py_type_full(pschema or {})
        params.append(f"{pname}: {t}" if pname in required else f"{pname}: {t} = None")
        pdesc = " ".join(str((pschema or {}).get("description", "")).split())[:200]
        if pdesc:
            args_doc.append(f"        {pname}: {pdesc}")
    desc = " ".join((tool.description or "").split())[:300]
    doc = desc + ("\n    Args:\n" + "\n".join(args_doc) if args_doc else "")
    sig = f"async def {namespace}.{py_name(tool.name)}({', '.join(params)}) -> Any"
    return f"{sig}\n    \"\"\"{doc}\"\"\"" if doc else sig


def name_line(namespace: str, tool: McpTool) -> str:
    """`discovery=names`: just the function name and a one-line purpose; details via describe()."""
    desc = (tool.description or "").strip().splitlines()[0][:120] if tool.description else ""
    return f"{namespace}.{py_name(tool.name)}" + (f"  # {desc}" if desc else "")


@dataclass
class McpBridge:
    """Async callables bound to a live MCP session; counts calls that hit the server."""

    session: ClientSession
    tools: list[McpTool]
    calls: int = 0
    errors: int = 0
    by_py_name: dict[str, McpTool] = field(init=False)

    def __post_init__(self) -> None:
        self.by_py_name = {py_name(t.name): t for t in self.tools}

    async def call(self, py: str, **kwargs: Any) -> Any:
        tool = self.by_py_name[py]
        args = {k: v for k, v in kwargs.items() if v is not None}
        self.calls += 1
        res = await self.session.call_tool(tool.name, args)
        if res.structuredContent is not None:
            out: Any = res.structuredContent
        else:
            texts = [c.text for c in res.content if getattr(c, "type", None) == "text"]
            raw = "\n".join(texts)
            try:
                out = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                out = raw
        if res.isError:
            self.errors += 1
            raise RuntimeError(f"{tool.name} failed: {str(out)[:2000]}")
        return out

    def describe(self, py: str) -> str:
        t = self.by_py_name[py]
        return json.dumps({"name": py, "description": t.description, "input_schema": t.inputSchema}, indent=1)


class _Namespace:
    def __init__(self, bridge: McpBridge, name: str):
        self._bridge = bridge
        self._name = name

    def __getattr__(self, item: str):
        if item not in self._bridge.by_py_name:
            raise AttributeError(f"{self._name} has no function {item!r}. Available: {sorted(self._bridge.by_py_name)}")

        async def fn(**kwargs: Any) -> Any:
            return await self._bridge.call(item, **kwargs)

        fn.__name__ = item
        return fn

    def __dir__(self):
        return sorted(self._bridge.by_py_name)


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"import of {name!r} is not allowed in code mode")
    return builtins.__import__(name, globals, locals, fromlist, level)


class CodeRunner:
    """A persistent async 'REPL': variables survive between execute_python calls."""

    def __init__(self, bridge: McpBridge, namespace: str, persist: bool = True):
        safe_builtins = {k: getattr(builtins, k) for k in dir(builtins)
                         if k not in {"open", "exec", "eval", "compile", "input", "breakpoint", "exit", "quit"}}
        safe_builtins["__import__"] = _safe_import
        self.bridge = bridge
        self.globals: dict[str, Any] = {
            "__builtins__": safe_builtins,
            namespace: _Namespace(bridge, namespace),
            "describe": bridge.describe,
            "json": json,
            "asyncio": asyncio,
        }
        self.persist = persist
        self._initial = dict(self.globals)

    async def run(self, code: str) -> str:
        if not self.persist:  # `state=fresh`: every call starts from a clean namespace
            self.globals = dict(self._initial)
        code = textwrap.dedent(code)
        tree = ast.parse(code, mode="exec")
        # Make the last bare expression print itself, like a notebook cell.
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last = tree.body[-1]
            tree.body[-1] = ast.Expr(ast.Call(ast.Name("print", ast.Load()), [last.value], []))
        # Wrap in an async function so top-level `await` works; export locals back to globals.
        fn = ast.AsyncFunctionDef(
            name="__cm_main__",
            args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=tree.body + [ast.Return(ast.Call(ast.Name("locals", ast.Load()), [], []))],
            decorator_list=[], returns=None, type_params=[],
        )
        module = ast.Module(body=[fn], type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, "<code-mode>", "exec"), self.globals)  # noqa: S102

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                local_vars = await asyncio.wait_for(self.globals["__cm_main__"](), EXEC_TIMEOUT_S)
            self.globals.update({k: v for k, v in (local_vars or {}).items() if not k.startswith("__")})
        except Exception:  # surfaced to the model so it can fix its code
            buf.write("\n" + traceback.format_exc(limit=3))
        out = buf.getvalue()
        if len(out) > MAX_OUTPUT_CHARS:
            out = out[:MAX_OUTPUT_CHARS] + f"\n...[truncated {len(out) - MAX_OUTPUT_CHARS} chars; print less]"
        return out or "(no output - use print() to see results)"


def build_code_tool(runner: CodeRunner) -> StructuredTool:
    async def execute_python(code: str) -> str:
        return await runner.run(code)

    state = ("Variables persist between calls." if runner.persist
             else "Each call starts fresh: variables do NOT persist between calls.")
    return StructuredTool.from_function(
        coroutine=execute_python,
        name="execute_python",
        description=(
            f"Execute async Python. Top-level `await` works. {state} "
            "Only printed output (and the value of a final bare expression) is returned to you."
        ),
    )


API_STYLES = ("compact", "full")
DISCOVERY_STYLES = ("upfront", "names")


def code_mode_prompt(namespace: str, server_label: str, tools: list[McpTool], *,
                     api: str = "compact", discovery: str = "upfront") -> str:
    """System-prompt addendum for code mode.

    api: `compact` (one-line stubs, top-level types) or `full` (nested types + per-parameter docs).
    discovery: `upfront` (every signature listed) or `names` (names only; parameters via describe()).
    """
    if api not in API_STYLES or discovery not in DISCOVERY_STYLES:
        raise ValueError(f"bad code-mode options api={api!r} discovery={discovery!r}")
    if discovery == "names":
        api_text = "\n".join(name_line(namespace, t) for t in tools)
        describe_rule = (f"- Only function names are listed below. Before calling a function, run "
                         f"`print(describe(\"<function>\"))` to get its input schema (you can describe several in one call).")
    else:
        render = signature_full if api == "full" else signature
        api_text = "\n\n".join(render(namespace, t) for t in tools)
        describe_rule = ("- For a function's full input schema, run `print(describe(\"<function>\"))` before you call a "
                         "function whose arguments you are unsure of.")
    return f"""You can use {server_label} through a Python API, by writing code for the `execute_python` tool.

Rules:
- Call the API as `await {namespace}.<function>(**kwargs)` (keyword arguments only). Results are parsed JSON (dict/list) or a string.
{describe_rule}
- Do filtering, pagination, joins and arithmetic IN CODE. Print only the small result you need, never whole raw API responses.
- Prefer one script that does several steps over many small calls.
- Allowed imports: {", ".join(sorted(ALLOWED_IMPORTS))}.

Available API ({len(tools)} functions):

{api_text}
"""
