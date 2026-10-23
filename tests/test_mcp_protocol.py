import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def test_real_stdio_protocol_and_validation():
    params = StdioServerParameters(command=sys.executable,
                                   args=['-m', 'app.mcp_server'], cwd=str(ROOT / 'api'))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == 1
            tool = tools.tools[0]
            assert tool.name == 'search_arsenal_knowledge'
            assert tool.annotations.readOnlyHint is True
            assert tool.inputSchema['properties']['top_k']['maximum'] == 5
            assert tool.outputSchema is not None
            result = await session.call_tool(tool.name, {'question': 'When was Arsenal founded?'})
            assert result.isError is False
            assert result.structuredContent['backend'] == 'local_lexical'
            assert any('1886' in s['text'] for s in result.structuredContent['sources'])
            unknown = await session.call_tool(tool.name, {'question': 'Who is the current captain in 2026?'})
            assert unknown.structuredContent['status'] == 'no_match'
            invalid = await session.call_tool(tool.name, {'question': 'Founding', 'top_k': 100})
            assert invalid.isError is True
