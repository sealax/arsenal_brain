# Football integration validation — 23 October 2026

## Scope

Three new read-only MCP tools call football-data.org: team fixtures/results/in-play statuses, league standings and team profiles. Historical retrieval remains available. The direct MCP console exposes arguments and responses without a language model.

## Checks completed

- `python -m pytest -q`: **62 passed**. Includes synthetic HTTP responses for football contracts, genuine local MCP sessions for discovery and tool calls, and the existing retrieval/evidence tests.
- `python scripts/evaluate_retrieval.py`: **10/10 deterministic retrieval checks passed**. These are not football accuracy tests or new model conversations.
- `python scripts/verify_evidence.py ...`: all three original historical agent traces verified against their recorded client/server results and corpus spans.
- `python scripts/football_console.py fixtures` and `... table`: actual stdio MCP calls returned `status: unavailable`, `error_code: not_configured`, with no fabricated match/table data and no fetch timestamp. This is the expected result before configuring a token. The command exits 1 cleanly for unavailable data.
- `.env` is ignored by Git. Only a blank `.env.example` is tracked.

## Authenticated acceptance completed

After Christopher configured his own token locally:

- [Provider check](provider-check.json): actual MCP stdio calls for fixtures, results, standings and team profile all returned `status: ok`. The profile returned 25 squad entries. These were authenticated network requests, separate from synthetic tests.
- [Native agent run](agent-run.json): Codex called `get_team_matches` with a 60-day PL window and limit 2, then `get_league_table` for PL. Both native MCP events completed successfully with provider data. The model's answer includes fixture London times, the 2026/27 season, league position, points, attribution, fetch times and delay caveats.
- The agent run used clean source commit `f175dbe792542af3a67590a3c4778c9667f061b8`, model `gpt-6.1-sol`, and the existing Codex login. Provider responses were fetched on 23 October 2026 at approximately 13:11 UTC. The prompt explicitly required football tools; the model selected arguments. No completed shell, web-search or file-change events were accepted.
- Shareable exports were checked against the configured token before publication. Credentials are not included; raw client logs remain ignored locally.

## Limits of this evidence

Native client events establish that these calls and responses occurred; they do not independently attest the provider's football accuracy. Responses are dated snapshots and will become old. Test fixtures remain synthetic. This does not prove real-time score delivery, complete cup coverage, squad access for every account, or production use. The optional historical server trace is not a second independent football trace.

The provider's free plan advertises delayed scores and schedules. The application labels every football response accordingly. Paid subscriptions are not configured or purchased.

## AI assistance

Christopher requested and scoped the expansion. Codex implemented and tested it in this session. This is evidence of an AI-assisted implementation and its checked behaviour, not independent authorship.
