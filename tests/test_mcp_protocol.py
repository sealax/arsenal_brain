import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def test_real_stdio_protocol_and_validation():
    params = StdioServerParameters(command=sys.executable,
                                   args=['-m', 'app.mcp_server'], cwd=str(ROOT / 'api'),
                                   env={'FOOTBALL_DATA_TOKEN': ''})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {'search_arsenal_knowledge', 'get_team_matches', 'get_league_table', 'get_team_profile'}
            tool = next(t for t in tools.tools if t.name == 'search_arsenal_knowledge')
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
            invalid_live = await session.call_tool('get_team_matches', {'days': 999})
            assert invalid_live.isError is True
            current = await session.call_tool('get_team_matches', {'team_id': 57})
            assert current.isError is False
            assert current.structuredContent['error_code'] == 'not_configured'


async def test_football_tools_over_mcp_with_synthetic_provider():
    """Real MCP session, mocked HTTP: proves wiring, not live football accuracy."""
    from datetime import datetime, timezone
    import httpx
    from mcp.shared.memory import create_connected_server_and_client_session
    from app.football import FootballClient
    from app.mcp_server import create_server

    def provider(request):
        path = request.url.path
        if path.endswith('/matches'):
            return httpx.Response(200, json={'matches': []})
        if path.endswith('/standings'):
            return httpx.Response(200, json={'competition': {'code': 'PL'},
                'season': {'startDate': '2026-08-01', 'endDate': '2027-05-30'},
                'standings': [{'type': 'TOTAL', 'table': []}]})
        return httpx.Response(200, json={'id': 57, 'name': 'Arsenal', 'squad': []})

    football = FootballClient('synthetic-token', transport=httpx.MockTransport(provider),
        now=lambda: datetime(2026, 10, 23, tzinfo=timezone.utc))
    async with create_connected_server_and_client_session(create_server(football=football)) as session:
        tools = await session.list_tools()
        for tool in tools.tools:
            assert tool.annotations.readOnlyHint
            assert tool.annotations.openWorldHint == (tool.name != 'search_arsenal_knowledge')
        for name, field in [('get_team_matches', 'matches'), ('get_league_table', 'standings'),
                            ('get_team_profile', 'name')]:
            result = await session.call_tool(name, {})
            assert not result.isError
            assert result.structuredContent['status'] == 'ok'
            assert field in result.structuredContent['data']
            assert 'synthetic-token' not in str(result)
