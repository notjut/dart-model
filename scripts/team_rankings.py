"""Refresh current ESPN FPI, AP and CFP ranks without changing forecasts."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
FPI_URL = 'https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/seasons/{season}/powerindex?limit=200'
CFP_URL = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings'
SOURCES = {'fpi': 'https://www.espn.com/college-football/fpi',
           'ap': 'https://www.espn.com/college-football/rankings',
           'cfp': 'https://www.espn.com/college-football/rankings'}
TEAM_REF = re.compile(r'^https?://sports\.core\.api\.espn\.com/v2/sports/football/leagues/college-football/seasons/(\d{4})/teams/(\d+)(?:\?[^#]*)?$')


def stamp(value, now):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed > now + dt.timedelta(minutes=5):
        raise ValueError('Invalid ranking publication timestamp')
    return parsed


def integer(value, limit):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 1 <= value <= limit or int(value) != value:
        raise ValueError('Invalid published rank')
    return int(value)


def parse_fpi(payload, season, required, now):
    items = payload.get('items', [])
    count = payload.get('count')
    if payload.get('pageCount') != 1 or not items or count != len(items) or not 100 <= count <= 200:
        raise ValueError('FPI feed is incomplete')
    ranks, dates = {}, []
    for item in items:
        match = TEAM_REF.fullmatch(item.get('team', {}).get('$ref', ''))
        if item.get('season') != season or not match or int(match[1]) != season:
            raise ValueError('FPI team or season mismatch')
        team = match[2]
        values = [p['value'] for p in item.get('predictives', []) if p.get('name') == 'fpirank']
        if team in ranks or len(values) != 1:
            raise ValueError('Duplicate or missing FPI rank')
        ranks[team] = integer(values[0], count)
        dates.append(stamp(item['lastUpdated'], now))
    if len(set(ranks.values())) != count or required - ranks.keys():
        raise ValueError('FPI ranks are duplicated or a scheduled FBS team is missing')
    if len(set(dates)) != 1:
        raise ValueError('FPI teams are from different ranking releases')
    return {'ranks': ranks, 'publishedAt': dates[0].isoformat()}


def parse_poll(payload, season, required, now, kind):
    polls = [p for p in payload.get('rankings', []) if p.get('type') == kind and p.get('season', {}).get('year') == season]
    if len(polls) != 1:
        raise ValueError(f'Current-season {kind.upper()} poll unavailable; other polls cannot replace it')
    poll = polls[0]
    ranks = {}
    for row in poll.get('ranks', []):
        team = str(row.get('team', {}).get('id', ''))
        if not team.isdigit() or team in ranks or team not in required:
            raise ValueError(f'{kind.upper()} team is duplicated or unmapped')
        ranks[team] = integer(row['current'], 25)
    # AP can publish ties: competition ranking skips the following place.
    values = sorted(ranks.values())
    valid = (len(ranks) >= 25 and all(rank == values[i-1] or rank == i+1 for i, rank in enumerate(values))
             and values[0] == 1) if kind == 'ap' else (len(ranks) == 25 and values == list(range(1, 26)))
    if not valid:
        raise ValueError(f'{kind.upper()} Top 25 is incomplete or duplicated')
    return {'ranks': ranks, 'publishedAt': stamp(poll['date'], now).isoformat(),
            'week': poll.get('occurrence', {}).get('number')}


def parse_cfp(payload, season, required, now):
    return parse_poll(payload, season, required, now, 'cfp')


def parse_ap(payload, season, required, now):
    return parse_poll(payload, season, required, now, 'ap')


def fetch(url):
    request = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Darkhorse-Rankings/1.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(8_000_001)
    if len(body) > 8_000_000:
        raise ValueError('Ranking response exceeds size limit')
    return json.loads(body)


def refresh(data, run_id, previous=None, now=None, fetcher=fetch):
    now = now or dt.datetime.now(UTC)
    previous = previous or {}
    season = max(int(g['season']) for g in data['games'])
    required = {str(k) for k, t in data['teams'].items() if t['conference'] != 'Non-FBS opponent'}
    result = {'runId': run_id, 'season': season, 'generatedAt': now.isoformat(), 'warnings': []}
    responses = {}
    for kind, url, parser, max_days in [('fpi', FPI_URL.format(season=season), parse_fpi, 7), ('ap', CFP_URL, parse_ap, 14), ('cfp', CFP_URL, parse_cfp, 14)]:
        base = {'sourceUrl': SOURCES[kind], 'dataSourceUrl': url, 'checkedAt': now.isoformat()}
        try:
            if url not in responses:
                responses[url] = fetcher(url)
            parsed = parser(responses[url], season, required, now)
            old = now - stamp(parsed['publishedAt'], now) > dt.timedelta(days=max_days)
            result[kind] = {**base, **parsed, 'retrievedAt': now.isoformat(), 'status': 'stale' if old else 'current'}
            if old:
                result['warnings'].append({'source': kind, 'message': 'ESPN is serving an older ranking release; ranks are labeled as older.'})
        except Exception as error:
            # Retain a checked prior release only, with its original retrieval time.
            prior = previous.get(kind, {}) if previous.get('season') == season else {}
            usable = prior.get('status') in ('current', 'stale') and bool(prior.get('ranks'))
            result[kind] = {**(prior if usable else {'ranks': {}}), **base, 'status': 'stale' if usable else 'unavailable'}
            result['warnings'].append({'source': kind, 'message': 'Ranking refresh failed: ' + type(error).__name__})
    result['coverage'] = {k: {'status': result[k]['status'], 'teams': len(result[k]['ranks']),
                             'publishedAt': result[k].get('publishedAt'), 'retrievedAt': result[k].get('retrievedAt')}
                          for k in ('fpi', 'ap', 'cfp')}
    return result


def main():
    directory = Path(os.environ.get('DART_DATA_DIR', ROOT))
    data = json.loads((directory/'data.json').read_text())
    model = json.loads((directory/'model.json').read_text())
    previous_file = ROOT/'team-rankings.json'
    previous = json.loads(previous_file.read_text()) if previous_file.exists() else {}
    result = refresh(data, model['refreshRunId'], previous)
    (directory/'team-rankings.json').write_text(json.dumps(result, separators=(',', ':'), allow_nan=False))
    print(json.dumps(result['coverage']))


if __name__ == '__main__':
    main()
