# Current football tools

Arsenal Brain now exposes four read-only MCP tools: historical search plus fixtures/results, league tables and team profiles. Football tools make bounded requests to football-data.org v4; historical retrieval still works offline.

## Connect your account

1. Register at [football-data.org](https://www.football-data.org/client/register) and obtain your token. The free tier provides delayed scores, fixtures and league tables. In-play live scores and additional data depend on the subscription; this integration does not purchase or upgrade anything.
2. From the repository root, create the local configuration if it does not already exist: `cp -n .env.example .env`. Open `.env` in an editor and put the token after `FOOTBALL_DATA_TOKEN=`. Do not paste it into chat, screenshots or git. The root `.env` is ignored; it is separate from the old FastAPI configuration in `api/.env`.
3. Install `requirements-test.txt` in the existing `.venv`, or use `requirements-demo.lock` to reproduce its dependencies.
4. Restart any running MCP client so the server loads the new environment. Existing environment variables take precedence over `.env`.

## See the calls yourself

From the repository root:

```sh
.venv/bin/python scripts/football_console.py
```

Choose `fixtures`, `results`, `live`, `table` or `team`. This is a direct MCP console, not an AI conversation: it shows the tool name, arguments and structured response without an additional model login. The default match filter is Premier League. For a single call:

```sh
.venv/bin/python scripts/football_console.py fixtures
.venv/bin/python scripts/football_console.py results
.venv/bin/python scripts/football_console.py table
.venv/bin/python scripts/football_console.py team
.venv/bin/python scripts/football_console.py fixtures --competition ALL
.venv/bin/python scripts/football_console.py fixtures --competition CL
```

`ALL` includes only competitions the account can access, not every Arsenal match. FA Cup (`FAC`), Champions League (`CL`) and Europa League (`EL`) filters are also accepted. Empty results do not prove no matches exist outside the returned window or subscription.

For an agent conversation, use the MCP client configuration in [AGENT_DEMO.md](AGENT_DEMO.md#connect-manually), restart the client and ask: “Use get_team_matches for Arsenal's next Premier League fixtures, then get_league_table. Cite the provider, fetch time, season and delay warnings.” The model chooses the calls. It must not infer current facts from the historical document. Calls use your football-data account; model responses use your normal model allowance.

## Contract and limitations

- `get_team_matches`: default team ID 57 (Arsenal); fixtures look forward 30 days, results look back 30 days; `days` 1–90, `limit` 1–20. `live` checks today's in-play statuses and still warns about delayed data. Kickoffs are UTC and Europe/London, including daylight-saving transitions. Unknown scores remain null; postponed matches are labelled provisional. Completed results sort newest first.
- `get_league_table`: defaults to `PL`, returns TOTAL tables and explicit provider season dates. Other supported codes are CL, EL, PD, BL1, SA and FL1; knockout competitions may have no table. The provider's default season is not automatically proof it is today's season.
- `get_team_profile`: team, coach and squad fields where available. Missing or empty squad data is unknown and may require a different plan. A squad list does not identify the captain.
- Each result includes attribution, a source URL without credentials, fetch time, served time, cache age and delay warnings. Fetch time describes retrieval, not when a football fact changed. Provider `lastUpdated` is preserved where supplied.
- Cached raw responses expire after 60 seconds, with no stale fallback. An 8-request/minute process-local budget reduces the chance of exceeding the free allowance. Multiple server processes or other apps using the same key still share the provider's account quota. Provider 429 responses respect a bounded Retry-After cooldown.
- Only a fixed HTTPS API host is reachable through these tools. Requests have bounded timeouts and a 2 MB response cap, do not follow redirects, and do not expose raw provider error messages or authorization headers. Failures are explicit (`not_configured`, `invalid_credentials`, `access_denied`, `rate_limited`, `timeout`, etc.). Read-only tool hints are backed by GET-only implementation.
- The existing optional `ARSENAL_TOOL_TRACE` records historical searches only. Football responses can be inspected in the console or your MCP client's events. Do not describe mocked provider tests as live-data or agent-run evidence.

Football data provided by the Football-Data.org API. Display that attribution when showing football answers. No club graphics are bundled.

## Verification

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate_retrieval.py
.venv/bin/python scripts/verify_evidence.py evidence/2026-10-23/founding.json evidence/2026-10-23/missing.json evidence/2026-10-23/unsupported-match.json
```

See the [dated validation record](../evidence/football-integration/VALIDATION.md) for completed checks and outstanding live acceptance.

Tests use synthetic provider responses and real local MCP protocol calls. They need no provider secret and make no external football requests. A successful authenticated provider run is a separate acceptance step after configuring the token. The original historical agent evidence remains tied to its original commits.

This extension was generated and tested with Codex at Christopher's request. It does not establish unaided authorship or production use.

## Provider references

- [Pricing and plan limits](https://www.football-data.org/pricing)
- [Team and match resource](https://docs.football-data.org/general/v4/team.html)
- [Competition resource](https://docs.football-data.org/general/v4/competition.html)
- [Policies, defaults and null values](https://docs.football-data.org/general/v4/policies.html)
- [Attribution and terms](https://www.football-data.org/about)
