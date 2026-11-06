"""Supplemental current-injury check; official reports remain authoritative.

Trial rows stay in memory. Only comparison outcomes for already-published
official players and aggregate diagnostics are saved. No scores, diagnoses,
new player injuries, starters, or numerical model adjustments are imported.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import datetime as dt
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from availability import norm

UTC = dt.timezone.utc
BASE = 'https://api.sportsdata.io/v3/cfb/'
SOURCE = 'https://sportsdata.io/developers/workflow-guide/ncaa-football'
STATUSES = {'out', 'doubtful', 'questionable', 'probable'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_rows(path, key):
    if path not in {'scores/json/InjuredPlayers', 'scores/json/Teams'}:
        raise ValueError('Unsupported supplemental endpoint')
    request = urllib.request.Request(BASE + path, headers={
        'Ocp-Apim-Subscription-Key': key.strip(), 'Accept': 'application/json',
        'User-Agent': 'Darkhorse-Injury-Check/1.0'})
    opener = urllib.request.build_opener(NoRedirect)
    for attempt in range(2):
        try:
            with opener.open(request, timeout=25) as response:
                raw = response.read(20_000_001)
                if len(raw) > 20_000_000:
                    return {'state': 'response_too_large'}, []
                rows = json.loads(raw)
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                return {'state': 'unexpected_response'}, []
            return {'state': 'returned_rows' if rows else 'empty_response', 'records': len(rows)}, rows
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            if status in {500, 502, 503, 504} and attempt == 0:
                continue
            return {'state': {401: 'key_or_subscription_denied', 403: 'access_denied',
                              429: 'quota_or_rate_limit'}.get(status, 'http_error'),
                    'httpStatus': status}, []
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 0:
                continue
            return {'state': 'network_error'}, []
        except (ValueError, TypeError):
            return {'state': 'invalid_json'}, []


def timestamp(value):
    try:
        value = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return value if value.tzinfo else None
    except ValueError:
        return None


def position_group(pos):
    pos = str(pos or '').upper()
    if pos in {'C', 'OC', 'OL', 'OT', 'OG', 'LT', 'LG', 'RG', 'RT', 'G', 'T'}:
        return 'OL'
    if pos in {'DL', 'DT', 'DE', 'NT', 'EDGE', 'EDG'}:
        return 'DL'
    return pos


def eligible(team, game, now):
    """Current feed only checks this game's recent official report, within 7 days."""
    if not team or team.get('status') != 'reported':
        return False
    if team.get('gameDate') != game.get('gameDate'):
        return False
    try:
        ahead = (dt.date.fromisoformat(game['gameDate']) - now.date()).days
    except (KeyError, ValueError, TypeError):
        return False
    published, retrieved = timestamp(team.get('publishedAt')), timestamp(team.get('retrievedAt'))
    return bool(0 <= ahead <= 7 and published and retrieved
                and dt.timedelta(0) <= now - published <= dt.timedelta(days=7)
                and dt.timedelta(0) <= now - retrieved <= dt.timedelta(hours=30))


def check(availability, key, run_id, now=None, fetch=request_rows):
    now = now or dt.datetime.now(UTC)
    out = deepcopy(availability)
    # Do not carry a previous successful check through a failed refresh.
    for game in out.get('games', {}).values():
        for side in ['home', 'away']:
            team = game.get(side)
            if team:
                team.pop('supplementalCheck', None)
                for player in team.get('players', []) + team.get('concerns', []):
                    player.pop('supplementalCheck', None)
    for team in out.get('teams', {}).values():
        team.pop('supplementalCheck', None)
        for player in team.get('players', []) + team.get('concerns', []):
            player.pop('supplementalCheck', None)
    report = {'provider': 'SportsDataIO', 'mode': 'supplemental_trial_check',
              'runId': run_id, 'checkedAt': now.isoformat(), 'sourceUrl': SOURCE,
              'status': 'not_configured', 'checks': [], 'counts': {},
              'scoreAdjustmentsApplied': False,
              'note': 'Official reports control every displayed player status. Matching wording is not proof of game-day availability. Trial-only injuries and diagnoses are not published. Starting lineups are not provided.'}
    out['supplementalCheck'] = report
    if not key.strip():
        return out
    state, injured = fetch('scores/json/InjuredPlayers', key)
    report['checks'].append({'endpoint': 'current_injuries', **state})
    report['status'] = 'unavailable'
    if state['state'] != 'returned_rows':
        return out
    state, teams = fetch('scores/json/Teams', key)
    report['checks'].append({'endpoint': 'team_mapping', **state})
    if state['state'] != 'returned_rows':
        return out

    # Ambiguous school IDs, player names or duplicated IDs are never guessed.
    school_ids = defaultdict(set)
    id_schools = defaultdict(set)
    for team in teams:
        school = norm(str(team.get('School') or ''))
        tid = team.get('TeamID')
        if school and tid is not None:
            school_ids[school].add(tid)
            id_schools[tid].add(school)
    player_ids = Counter(r.get('PlayerID') for r in injured if r.get('PlayerID') is not None)
    candidates = defaultdict(list)
    for row in injured:
        player = norm(' '.join(str(row.get(k) or '') for k in ['FirstName', 'LastName']))
        if player:
            candidates[(row.get('TeamID'), player)].append(row)
    totals = Counter()
    units = {u: Counter() for u in ['Quarterback', 'Center', 'Offensive line', 'Defensive line', 'Other']}
    for game in out.get('games', {}).values():
        for side in ['home', 'away']:
            team = game.get(side)
            if not eligible(team, game, now):
                continue
            school = norm(str(team.get('teamName') or ''))
            tids = school_ids.get(school, set())
            if len(tids) != 1:
                totals['teamsNotMatched'] += 1
                continue
            tid = next(iter(tids))
            if len(id_schools[tid]) != 1:
                totals['teamsNotMatched'] += 1
                continue
            totals['teamReportsChecked'] += 1
            counts = Counter()
            names = Counter(norm(p.get('name', '')) for p in team.get('players', []))
            decisions = {}
            for player in team.get('players', []):
                name = norm(player.get('name', ''))
                matches = candidates.get((tid, name), [])
                outcome = 'not_listed'
                if names[name] != 1 or len(matches) > 1:
                    outcome = 'ambiguous_match'
                elif matches:
                    row = matches[0]
                    pgroup, rgroup = position_group(player.get('position')), position_group(row.get('Position'))
                    status = str(row.get('InjuryStatus') or '').strip().lower()
                    official_status = str(player.get('status') or '').strip().lower()
                    if player_ids[row.get('PlayerID')] != 1 or (pgroup and rgroup and pgroup != rgroup):
                        outcome = 'ambiguous_match'
                    elif status not in STATUSES or official_status not in STATUSES | {'available', 'exempt'}:
                        outcome = 'not_comparable'
                    else:
                        outcome = 'same_status' if status == official_status else 'status_differs'
                decisions[name] = {'status': outcome, 'checkedAt': now.isoformat()}
                counts[outcome] += 1
                units.get(player.get('unit'), units['Other'])[outcome] += 1
            for player in team.get('players', []) + team.get('concerns', []):
                if norm(player.get('name', '')) in decisions:
                    player['supplementalCheck'] = decisions[norm(player['name'])]
            team['supplementalCheck'] = {'status': 'checked', 'checkedAt': now.isoformat(), 'counts': dict(counts)}
            totals.update(counts)
            saved = out.get('teams', {}).get(team.get('teamId'))
            if saved and saved.get('gameDate') == team.get('gameDate'):
                out['teams'][team['teamId']] = deepcopy(team)
    report.update(status='checked', counts=dict(totals), priorityUnits={k: dict(v) for k, v in units.items()})
    return out


def main():
    root = Path(__file__).resolve().parents[1]
    data_dir = Path(os.environ.get('DART_DATA_DIR', str(root)))
    availability = json.loads((data_dir / 'availability.json').read_text())
    model = json.loads((data_dir / 'model.json').read_text())
    key = os.environ.get('SPORTSDATAIO_API_KEY') or os.environ.get('SPORTSDATAIOAPIKEY', '')
    out = check(availability, key, model['refreshRunId'])
    summary = out['supplementalCheck']
    if summary['status'] != 'checked':
        out.setdefault('failures', []).append({'source': 'SportsDataIO supplemental check', 'error': summary['status'], 'checks': summary['checks']})
    destination = data_dir / 'availability.json'
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(out, separators=(',', ':'), allow_nan=False))
    temporary.replace(destination)
    print(json.dumps(summary, allow_nan=False))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            output.write('## Supplemental injury check\n\nOfficial reports remain authoritative. No injury score adjustments.\n\n```json\n' + json.dumps(summary, indent=2) + '\n```\n')


if __name__ == '__main__':
    main()
