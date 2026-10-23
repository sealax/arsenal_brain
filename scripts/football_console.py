"""Inspect the football MCP tools directly, without a language model or extra login."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = {'fixtures': ('get_team_matches', {'kind': 'fixtures'}),
           'results': ('get_team_matches', {'kind': 'results'}),
           'live': ('get_team_matches', {'kind': 'live'}),
           'table': ('get_league_table', {}), 'team': ('get_team_profile', {})}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=ACTIONS, nargs='?')
    parser.add_argument('--competition', choices=['ALL', 'PL', 'CL', 'FAC', 'EL'], default='PL',
                        help='Match filter only; table is Premier League. ALL includes all covered competitions.')
    args = parser.parse_args()
    params = StdioServerParameters(command=sys.executable, args=['-m', 'app.mcp_server'],
                                   cwd=str(ROOT / 'api'))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            while True:
                action = args.action or input('\nChoose fixtures / results / live / table / team / quit: ').strip().lower()
                if action in ('quit', 'q', 'exit'):
                    return
                if action not in ACTIONS:
                    print('Choose one of the listed actions.')
                    continue
                tool, defaults = ACTIONS[action]
                arguments = dict(defaults)
                if tool == 'get_team_matches':
                    arguments['competition'] = args.competition
                print(f'\nMCP call: {tool}({json.dumps(arguments)})')
                result = await session.call_tool(tool, arguments)
                print(json.dumps(result.structuredContent or [c.model_dump() for c in result.content],
                                 indent=2, ensure_ascii=False))
                if args.action:
                    if result.isError or (result.structuredContent or {}).get('status') != 'ok':
                        return 1
                    return


if __name__ == '__main__':
    try:
        raise SystemExit(asyncio.run(main()) or 0)
    except (KeyboardInterrupt, EOFError):
        pass
