"""Offline provider-contract tests: synthetic data, never live football evidence."""
from datetime import datetime, timezone

import httpx
import pytest

from app.football import ATTRIBUTION, FootballClient

NOW = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)


def client(payload=None, status=200, headers=None, handler=None, clock=None):
    return FootballClient('test-secret-not-real', transport=httpx.MockTransport(
        handler or (lambda request: httpx.Response(status, json=payload, headers=headers))),
        now=lambda: NOW, **({'clock': clock} if clock else {}))


def match(id=1, status='TIMED', date='2026-10-24T14:00:00Z', code='PL', score=None):
    return {'id': id, 'utcDate': date, 'status': status,
            'homeTeam': {'id': 57, 'name': 'Arsenal'},
            'awayTeam': {'id': 61, 'name': 'Chelsea'},
            'competition': {'code': code, 'name': 'Premier League'},
            'score': score or {'fullTime': {'home': None, 'away': None}},
            'lastUpdated': '2026-10-23T10:00:00Z'}


def test_missing_key_is_explicit_and_offline():
    def forbidden(_):
        pytest.fail('network called without a key')
    result = FootballClient('', transport=httpx.MockTransport(forbidden)).team()
    assert result.status == 'unavailable'
    assert result.error_code == 'not_configured'
    assert result.fetched_at_utc is None


def test_fixture_null_score_attribution_london_dst_and_fixed_request():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'matches': [match(), match(2, date='2026-10-26T14:00:00Z')]})
    result = client(handler=handler).matches()
    assert result.status == 'ok'
    assert result.attribution == ATTRIBUTION
    assert result.data['matches'][0]['score']['fullTime']['home'] is None
    assert result.data['matches'][0]['kickoff_london'].endswith('+01:00')
    assert result.data['matches'][1]['kickoff_london'].endswith('+00:00')
    assert requests[0].url.host == 'api.football-data.org'
    assert requests[0].url.path == '/v4/teams/57/matches'
    assert requests[0].headers['X-Auth-Token'] == 'test-secret-not-real'
    assert 'test-secret-not-real' not in result.model_dump_json()
    assert result.fetched_at_utc == NOW.isoformat()
    assert 'delayed' in result.score_freshness


def test_filter_results_order_limit_and_window():
    rows = [match(1, 'FINISHED', '2026-10-20T14:00:00Z'),
            match(2, 'FINISHED', '2026-10-22T14:00:00Z'),
            match(3, 'FINISHED', '2026-10-21T14:00:00Z', 'CL'),
            match(4, 'TIMED'), match(5, 'FINISHED', '2025-01-01T14:00:00Z')]
    result = client({'matches': rows}).matches(kind='results', competition='PL', limit=1)
    assert result.data['available_matches'] == 2
    assert [m['id'] for m in result.data['matches']] == [2]


def test_live_empty_is_not_proof_no_matches_and_does_not_return_finished():
    result = client({'matches': [match(status='FINISHED', date='2026-10-23T10:00:00Z')]}).matches(kind='live')
    assert result.status == 'ok'
    assert result.data['matches'] == []
    assert 'do not prove' in result.warnings[0]


@pytest.mark.parametrize(('status', 'code'), [(401, 'invalid_credentials'), (403, 'access_denied'),
    (404, 'not_found'), (429, 'rate_limited'), (500, 'provider_error'), (302, 'provider_error')])
def test_provider_failures_are_sanitized(status, code):
    result = client({'error': 'test-secret-not-real'}, status).team()
    assert result.error_code == code
    assert result.data == {}
    assert 'test-secret-not-real' not in result.model_dump_json()


def test_rate_limit_retry_cooldown_and_cache():
    tick = [0.0]
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'id': 57, 'name': 'Arsenal'})
    api = client(handler=handler, clock=lambda: tick[0])
    assert api.team().cache_age_seconds == 0
    tick[0] = 12
    assert api.team().cache_age_seconds == 12
    assert len(calls) == 1
    # Mutating a caller's response cannot poison the cached provider payload.
    first = api.team()
    first.data['name'] = 'changed'
    assert api.team().data['name'] == 'Arsenal'
    tick[0] = 61
    assert api.team().cache_age_seconds == 0
    assert len(calls) == 2
    for i in range(1, 8):
        api.team(i)
    assert api.team(99).error_code == 'rate_limited'
    assert len(calls) == 9  # one expired-window request plus eight this window


def test_provider_retry_after_prevents_repeated_requests():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={'Retry-After': '120'})
    api = client(handler=handler)
    assert api.team().retry_after_seconds == 120
    assert api.standings().error_code == 'rate_limited'
    assert len(calls) == 1


@pytest.mark.parametrize('payload', [None, [], {'matches': {}}, {'matches': [{}]},
    {'matches': [match(date='2026-10-24T14:00:00')]}])
def test_malformed_matches_are_not_empty_success(payload):
    result = client(payload).matches()
    assert result.status == 'unavailable'
    assert result.error_code == 'invalid_response'


def test_timeout_and_oversize_are_safe():
    def timeout(request):
        raise httpx.ReadTimeout('test-secret-not-real')
    assert client(handler=timeout).team().error_code == 'timeout'
    def huge(request):
        return httpx.Response(200, content=b' ' * 2_000_001)
    assert client(handler=huge).team().error_code == 'invalid_response'


def test_standings_preserve_season_and_total_only():
    payload = {'competition': {'code': 'PL'}, 'season': {'startDate': '2026-08-01', 'endDate': '2027-05-30'},
               'standings': [{'type': 'HOME', 'table': []}, {'type': 'TOTAL', 'table': [
                   {'position': 1, 'team': {'id': 57, 'name': 'Arsenal'}, 'points': 20}]}]}
    result = client(payload).standings()
    assert result.status == 'ok'
    assert len(result.data['standings']) == 1
    assert result.data['season']['startDate'] == '2026-08-01'
    assert client({'standings': []}).standings().error_code == 'invalid_response'


def test_team_missing_squad_remains_unknown():
    result = client({'id': 57, 'name': 'Arsenal'}).team()
    assert result.data['squad'] is None
    assert 'unavailable' in result.warnings[-1]
    assert client({'message': 'bad response'}).team().error_code == 'invalid_response'


@pytest.mark.parametrize('kwargs', [{'team_id': True}, {'team_id': -1}, {'days': 0},
    {'days': 91}, {'limit': 21}, {'competition': '../../secret'}, {'kind': 'anything'}])
def test_invalid_filters_never_reach_network(kwargs):
    with pytest.raises(ValueError):
        client().matches(**kwargs)


def test_wrong_team_and_missing_season_are_not_trusted():
    assert client({'id': 61, 'name': 'Chelsea'}).team().error_code == 'invalid_response'
    other_match = match()
    other_match['homeTeam']['id'] = 99
    assert client({'matches': [other_match]}).matches().error_code == 'invalid_response'
    assert client({'competition': {'code': 'PL'}, 'season': {}, 'standings': [
        {'type': 'TOTAL', 'table': []}]}).standings().error_code == 'invalid_response'


def test_past_upcoming_fixtures_are_excluded():
    result = client({'matches': [match(date='2026-10-23T10:00:00Z')]}).matches()
    assert result.data['matches'] == []
