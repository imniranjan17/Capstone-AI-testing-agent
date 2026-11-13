"""Step 5: MCP branch — spawns the test-case MCP server over stdio and runs every tool."""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.schemas import Category, Finding, Severity


async def _run_all(html: str, tools: list[str] | None) -> list[dict]:
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"])
    results = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = [t.name for t in (await session.list_tools()).tools]
            for name in names:
                if tools and name not in tools:
                    continue
                res = await session.call_tool(name, {"html": html})
                results.append(json.loads(res.content[0].text))
    return results


def results_to_findings(results: list[dict]) -> list[Finding]:
    out = []
    for r in results:
        if r.get("passed"):
            continue
        for d in r.get("details", []) or ["test failed"]:
            out.append(Finding(source="mcp", category=Category.functional, severity=Severity.high,
                               rule_id=f"mcp-{r['test']}", message=d, evidence=r["test"]))
    return out


def run_mcp_tests(html: str, tools: list[str] | None = None, timeout: float = 60.0) -> list[Finding]:
    try:
        results = asyncio.run(asyncio.wait_for(_run_all(html, tools), timeout))
    except Exception as e:  # branch must not crash the pipeline
        return [Finding(source="mcp", category=Category.functional, severity=Severity.low,
                        rule_id="mcp-unavailable", message=f"MCP test server failed: {e.__class__.__name__}: {e}")]
    return results_to_findings(results)
