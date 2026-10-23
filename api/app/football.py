"""Bounded, read-only football-data.org adapter. Never returns credentials or raw errors."""
from __future__ import annotations

import copy
import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

BASE_URL = 'https://api.football-data.org/v4'
ATTRIBUTION = 'Football data provided by the Football-Data.org API'


class FootballResult(BaseModel):
    status: Literal['ok', 'unavailable']
    provider: str = 'football-data.org'
    attribution: str = ATTRIBUTION
    source_url: str
    fetched_at_utc: str | None = None
    served_at_utc: str
    cache_age_seconds: float | None = None
    score_freshness: str = 'Scores and schedules may be delayed; this is not a real-time score guarantee.'
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    retry_after_seconds: int | None = None


class Team(BaseModel):
    id: int | None
    name: str | None


class Match(BaseModel):
    id: int
    utcDate: datetime
    status: str
    homeTeam: Team
    awayTeam: Team
    competition: dict[str, Any]
    score: dict[str, Any]
    lastUpdated: str | None = None
    model_config = ConfigDict(extra='ignore')


class FootballClient:
    """One process-local 60s cache and 8-request/minute budget shared by all tools.

    A fixed host, no redirects, a response-size cap and sanitized errors keep a
    model's inputs away from arbitrary URLs, credentials and provider error text.
    """

    def __init__(self, token: str | None = None, *, transport=None,
                 now: Callable[[], datetime] | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self._token = token if token is not None else os.getenv('FOOTBALL_DATA_TOKEN', '')
        self._transport = transport
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._clock = clock
        self._cache: dict[str, tuple[float, dict, str]] = {}
        self._requests: deque[float] = deque()
        self._lock = threading.Lock()
        self._cooldown = 0.0

    def _get(self, path: str, params: dict | None = None) -> FootballResult:
        url = str(httpx.URL(BASE_URL + path, params=params))
        result = FootballResult(status='unavailable', source_url=url,
                                served_at_utc=self._now().isoformat())
        if not self._token.strip():
            result.error_code = 'not_configured'
            result.warnings = ['Set FOOTBALL_DATA_TOKEN in the ignored repository-root .env file, then restart the MCP server.']
            return result
        key = url
        with self._lock:
            tick = self._clock()
            # Expire, rather than presenting stale data as newly fetched.
            self._cache = {k: v for k, v in self._cache.items() if tick - v[0] < 60}
            if key in self._cache:
                cached_tick, payload, fetched = self._cache[key]
                return result.model_copy(update={'status': 'ok', 'data': copy.deepcopy(payload),
                    'fetched_at_utc': fetched, 'cache_age_seconds': round(tick - cached_tick, 3)})
            while self._requests and tick - self._requests[0] >= 60:
                self._requests.popleft()
            wait = max(self._cooldown - tick,
                       60 - (tick - self._requests[0]) if len(self._requests) >= 8 else 0)
            if wait > 0:
                result.error_code = 'rate_limited'
                result.retry_after_seconds = max(1, int(wait) + 1)
                return result
            self._requests.append(tick)
            try:
                with httpx.Client(timeout=httpx.Timeout(12, connect=5), follow_redirects=False,
                                  transport=self._transport) as client:
                    with client.stream('GET', url, headers={'X-Auth-Token': self._token}) as response:
                        if response.status_code != 200:
                            result.error_code = {401: 'invalid_credentials', 403: 'access_denied',
                                404: 'not_found', 429: 'rate_limited'}.get(response.status_code, 'provider_error')
                            if response.status_code == 429:
                                try:
                                    retry = int(response.headers.get('Retry-After', '60'))
                                except ValueError:
                                    retry = 60
                                result.retry_after_seconds = max(1, min(retry, 3600))
                                self._cooldown = self._clock() + result.retry_after_seconds
                            result.warnings = ['Provider access failed. Check account permissions and competition coverage; no fallback data was substituted.']
                            return result
                        raw = bytearray()
                        for part in response.iter_bytes():
                            raw.extend(part)
                            if len(raw) > 2_000_000:
                                raise ValueError('response too large')
                        payload = json.loads(raw)
                        if not isinstance(payload, dict):
                            raise ValueError('expected object')
            except httpx.TimeoutException:
                result.error_code = 'timeout'
                return result
            except httpx.HTTPError:
                result.error_code = 'network_error'
                return result
            except (ValueError, UnicodeError):
                result.error_code = 'invalid_response'
                return result
            fetched = self._now().isoformat()
            self._cache[key] = (self._clock(), payload, fetched)
            return result.model_copy(update={'status': 'ok', 'data': copy.deepcopy(payload),
                                             'fetched_at_utc': fetched, 'served_at_utc': self._now().isoformat(),
                                             'cache_age_seconds': 0.0})

    @staticmethod
    def _invalid(result: FootballResult) -> FootballResult:
        result.status, result.error_code, result.data = 'unavailable', 'invalid_response', {}
        result.warnings = ['Provider returned an incomplete or unexpected response. Do not infer missing facts.']
        return result

    def matches(self, team_id: int = 57, kind: str = 'fixtures', days: int = 30,
                limit: int = 10, competition: str = 'ALL') -> FootballResult:
        if type(team_id) is not int or not 1 <= team_id <= 100000:
            raise ValueError('team_id must be 1..100000')
        if kind not in ('fixtures', 'results', 'live') or competition not in ('ALL', 'PL', 'CL', 'FAC', 'EL'):
            raise ValueError('unsupported match filter')
        if type(days) is not int or not 1 <= days <= 90 or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError('days must be 1..90 and limit 1..20')
        today = self._now().date()
        start = today - timedelta(days=days) if kind == 'results' else today
        end = today + timedelta(days=days) if kind == 'fixtures' else today + timedelta(days=1)
        result = self._get(f'/teams/{team_id}/matches',
                           {'dateFrom': start.isoformat(), 'dateTo': end.isoformat(), 'limit': 500})
        if result.status != 'ok':
            return result
        try:
            rows = result.data['matches']
            if not isinstance(rows, list):
                raise ValueError()
            parsed = [Match.model_validate(row) for row in rows]
            if any(team_id not in (m.homeTeam.id, m.awayTeam.id) for m in parsed):
                raise ValueError('unexpected team in matches')
            states = {'fixtures': {'SCHEDULED', 'TIMED', 'POSTPONED'},
                      'results': {'FINISHED', 'AWARDED'},
                      'live': {'IN_PLAY', 'PAUSED', 'EXTRA_TIME', 'PENALTY_SHOOTOUT'}}[kind]
            selected = [m for m in parsed if m.status in states
                        and (competition == 'ALL' or m.competition.get('code') == competition)
                        and start <= m.utcDate.date() <= end
                        and (kind != 'fixtures' or m.status == 'POSTPONED' or m.utcDate >= self._now())]
            if any(m.utcDate.tzinfo is None for m in parsed):
                raise ValueError('timezone missing')
            selected.sort(key=lambda m: m.utcDate, reverse=kind == 'results')
            result.data = {'team_id': team_id, 'kind': kind, 'competition_filter': competition,
                'date_from': start.isoformat(), 'date_to': end.isoformat(),
                'available_matches': len(selected), 'matches': [dict(
                    id=m.id, competition=m.competition.get('name'), competition_code=m.competition.get('code'),
                    kickoff_utc=m.utcDate.astimezone(timezone.utc).isoformat(),
                    kickoff_london=m.utcDate.astimezone(ZoneInfo('Europe/London')).isoformat(),
                    status=m.status, home=m.homeTeam.model_dump(), away=m.awayTeam.model_dump(),
                    score=m.score, provider_last_updated=m.lastUpdated) for m in selected[:limit]]}
            result.warnings = ['Results cover only this date window and competitions permitted by your subscription. Empty matches do not prove there are no matches elsewhere.']
            if len(rows) >= 500:
                result.warnings.append('Provider row limit reached; this window may be incomplete.')
            if any(m.status == 'POSTPONED' for m in selected):
                result.warnings.append('Postponed kickoff times are provisional.')
            return result
        except (KeyError, TypeError, ValueError, ValidationError):
            return self._invalid(result)

    def standings(self, competition: str = 'PL') -> FootballResult:
        if competition not in ('PL', 'CL', 'EL', 'PD', 'BL1', 'SA', 'FL1'):
            raise ValueError('unsupported competition')
        result = self._get(f'/competitions/{competition}/standings')
        if result.status != 'ok':
            return result
        try:
            payload = result.data
            tables = payload['standings']
            if not isinstance(tables, list) or not isinstance(payload['season'], dict):
                raise ValueError()
            if payload['competition']['code'] != competition:
                raise ValueError('unexpected competition')
            for date_field in ('startDate', 'endDate'):
                datetime.strptime(payload['season'][date_field], '%Y-%m-%d')
            totals = [s for s in tables if s['type'] == 'TOTAL']
            for group in totals:
                for row in group['table']:
                    if not isinstance(row['points'], int) or not isinstance(row['team']['name'], str):
                        raise ValueError()
            if not totals:
                raise ValueError()
            result.data = {'competition': payload['competition'], 'season': payload['season'],
                           'standings': totals}
            result.warnings = ['Check the returned season dates and matchday before describing this as the current season. Tables may lag play.']
            return result
        except (KeyError, TypeError, ValueError):
            return self._invalid(result)

    def team(self, team_id: int = 57) -> FootballResult:
        if type(team_id) is not int or not 1 <= team_id <= 100000:
            raise ValueError('team_id must be 1..100000')
        result = self._get(f'/teams/{team_id}')
        if result.status != 'ok':
            return result
        try:
            payload = result.data
            team = Team.model_validate(payload)
            if payload.get('squad') is not None and not isinstance(payload['squad'], list):
                raise ValueError('unexpected squad')
            if team.id != team_id or not team.name:
                raise ValueError('unexpected team')
            result.data = {k: payload.get(k) for k in ('id', 'name', 'shortName', 'tla', 'website',
                'founded', 'clubColors', 'venue', 'coach', 'runningCompetitions', 'squad', 'lastUpdated')}
            result.warnings = ['Team and squad fields reflect provider coverage and may be incomplete or delayed. Do not infer the captain from squad order.']
            if not payload.get('squad'):
                result.warnings.append('Squad data is unavailable or empty; access may require a different subscription.')
            return result
        except (TypeError, ValueError, ValidationError):
            return self._invalid(result)
