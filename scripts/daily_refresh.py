"""Build a checked release in isolation; publish only after every core check passes."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False))


def date(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def validate_sources(data, previous):
    refreshed = set(data['refresh']['scheduleTeamsRefreshed'])
    required = {k for k, t in previous['teams'].items() if t['conference'] != 'Non-FBS opponent'}
    missing = required - refreshed
    if missing:
        raise ValueError(f'Unrefreshed team schedules: {sorted(missing)}')
    if any('/summary?' in f['url'] for f in data['failures']):
        raise ValueError('A required game summary failed; retain the previous published release')
    games = data['games']
    if len({g['id'] for g in games}) != len(games):
        raise ValueError('Duplicate game IDs')
    old = {g['id']: g for g in previous['games']}
    for g in games:
        if g['done'] and (g['hs'] == g['as'] or min(g['hs'], g['as']) < 0):
            raise ValueError(f'Invalid completed score: {g["id"]}')
        if old.get(g['id'], {}).get('done') and not g['done']:
            raise ValueError(f'Completed result regressed: {g["id"]}')
        if g['done'] and not old.get(g['id'], {}).get('done'):
            if not g.get('stats') or not any(s.get('plays', 0) for s in g['stats'].values()):
                raise ValueError(f'New result has no usable play data: {g["id"]}')


def validate_forecasts(data, model, now):
    games = {g['id']: g for g in data['games']}
    if model['asOf'] != data['asOf'] or model['inputRetrievedAt'] != data['retrievedAt']:
        raise ValueError('Model and data snapshot do not match')
    seen = set()
    for f in model['forecasts']:
        g = games[f['id']]
        if f['id'] in seen or g['done'] or date(g['date']) <= now:
            raise ValueError(f'Forecast is duplicated, completed, or already started: {f["id"]}')
        seen.add(f['id'])
        if not all(math.isfinite(f[k]) for k in ['coreMargin', 'coreTotal', 'coreSd', 'margin', 'total', 'sd']):
            raise ValueError('Nonfinite forecast')
        if min(f['coreSd'], f['sd']) <= 0:
            raise ValueError('Invalid forecast uncertainty')


def snapshot(data, model, quotes, recorded_at, recovered=False):
    ids = {f['id'] for f in model['forecasts']}
    return {'generatedAt': model['generatedAt'], 'recordedAt': recorded_at,
            'type': 'recovered_saved_forecast' if recovered else 'prospective_snapshot',
            'asOf': model.get('asOf', data['asOf']), 'forecasts': model['forecasts'],
            'games': {g['id']: g for g in data['games'] if g['id'] in ids},
            'quotes': {k: v for k, v in quotes.get('games', {}).items() if k in ids}}


def grade(edge, actual):
    if abs(edge) < 1e-9:
        return 'no_pick'
    if abs(actual) < 1e-9:
        return 'push'
    return 'win' if (edge > 0) == (actual > 0) else 'loss'


def pick_explanation(f, g, picked, data):
    """Explain saved model inputs separately from observed game outcomes."""
    labels = {
        'Elo difference': 'overall team strength',
        'Net success-rate difference': 'sustaining drives and forcing stops',
        'Scoring margin difference': 'earlier scoring margins',
        'Scoring environment': 'the scoring patterns of the two teams',
        'Home field': 'home field',
        'Explosive-rate difference': 'big-play production',
        'Yards/game difference': 'offensive yardage',
    }
    if not picked:
        return {'pregame': 'The main forecast did not select a winner.', 'recap': [], 'drivers': []}
    sign = 1 if picked == g['home'] else -1
    team_name = lambda t: data.get('teams', {}).get(t, {}).get('name', t)
    opponent = g['away'] if sign == 1 else g['home']
    drivers = sorted([{'factor': labels.get(c['name'], c['name']),
                       'pointsTowardPick': round(sign * c['points'], 2)}
                      for c in f.get('coreContributions', [])],
                     key=lambda c: c['pointsTowardPick'], reverse=True)
    support = [c for c in drivers if c['pointsTowardPick'] >= .2][:2]
    reasons = ' and '.join(c['factor'] for c in support)
    margin = abs(f['coreMargin'])
    lean = 'This was a very small lean' if margin < 1 else 'This was a close call' if margin < 3 else 'The saved forecast favored this team'
    pregame = f'{lean}: {team_name(picked)} by {margin:.1f} points.'
    pregame += f' The strongest supporting inputs were {reasons}.' if support else ' The starting value and combined inputs produced the pick; no strong individual advantage was saved.'
    baseline = sign * f.get('coreIntercept', 0)
    if baseline > max([c['pointsTowardPick'] for c in support] or [0]):
        pregame += ' The model’s starting value also contributed more than any single supporting team statistic.'
    stats = g.get('stats') or {}
    a, b = stats.get(picked, {}), stats.get(opponent, {})
    def number(side, key):
        try:
            return float(side.get('boxscore', {}).get(key, side.get(key)))
        except (ValueError, TypeError):
            return None
    recap = []
    ta, tb = number(a, 'turnovers'), number(b, 'turnovers')
    if ta is not None and tb is not None and ta < tb:
        recap.append(f'{team_name(picked)} gave the ball away {int(ta)} times; {team_name(opponent)} did so {int(tb)} times.')
    ya, yb = number(a, 'totalYards'), number(b, 'totalYards')
    if ya is not None and yb is not None and ya > yb:
        recap.append(f'{team_name(picked)} gained {int(ya)} yards to {team_name(opponent)}’s {int(yb)}.')
    try:
        ca, aa = map(int, a['boxscore']['thirdDownEff'].split('-'))
        cb, ab = map(int, b['boxscore']['thirdDownEff'].split('-'))
        if aa and ab and ca / aa > cb / ab:
            recap.append(f'{team_name(picked)} converted {ca} of {aa} third downs; {team_name(opponent)} converted {cb} of {ab}.')
    except (KeyError, ValueError, ZeroDivisionError):
        pass
    recap = recap[:2]
    if ya is not None and yb is not None and ya < yb:
        recap.append(f'{team_name(picked)} was outgained {int(yb)}–{int(ya)}, so the win was not a clean sweep of the underlying stats.')
    if not recap:
        recap.append('The final score confirms the outcome. The saved box score does not provide enough evidence for a more specific game recap.')
    return {'pregame': pregame, 'recap': recap, 'drivers': drivers,
            'baselineTowardPick': round(baseline, 2), 'scope': 'Pregame reasons use only the saved main-model forecast. Game recap uses the final box score; it does not prove causation.'}


def grade_snapshots(snapshots, data):
    selected = {}
    completed = {g['id']: g for g in data['games'] if g['done']}
    for snap in sorted(snapshots, key=lambda x: x['generatedAt']):
        for f in snap['forecasts']:
            g = completed.get(f['id'])
            original = snap['games'].get(f['id'])
            if not g or not original:
                continue
            kickoff = min(date(original['date']), date(g['date']))
            if date(snap['generatedAt']) >= kickoff:
                continue
            if original.get('done'):
                continue
            q = snap['quotes'].get(f['id'], {})
            # Do not attach a closing or postgame line to an earlier prediction.
            quote_ok = q.get('retrievedAt') and date(q['retrievedAt']) < kickoff
            spread = q.get('homeSpread') if quote_ok else None
            total = q.get('overUnder') if quote_ok else None
            actual = g['hs'] - g['as']
            picked = g['home'] if f['coreMargin'] > 0 else g['away'] if f['coreMargin'] < 0 else None
            picked_underdog = bool(picked and spread not in (None, 0) and f['coreMargin'] * spread > 0)
            explanation = pick_explanation(f, g, picked, data) if picked_underdog else None
            sd = f.get('coreSd')
            probability = .5 * (1 + math.erf(abs(f['coreMargin']) / (sd * math.sqrt(2)))) if sd and sd > 0 else None
            selected[g['id']] = {
                'id': g['id'], 'date': g['date'], 'home': g['home'], 'away': g['away'],
                'homeScore': g['hs'], 'awayScore': g['as'], 'forecastAt': snap['generatedAt'],
                'archiveType': snap['type'], 'predictedHomeMargin': f['coreMargin'],
                'predictedTotal': f['coreTotal'], 'homeSpread': spread, 'overUnder': total,
                'quoteRetrievedAt': q.get('retrievedAt') if quote_ok else None,
                'winner': grade(f['coreMargin'], actual),
                'spread': grade(f['coreMargin'] + spread, actual + spread) if spread is not None else 'unavailable',
                'total': grade(f['coreTotal'] - total, g['hs'] + g['as'] - total) if total is not None else 'unavailable',
                'homeUnderdog': spread > 0 if spread is not None else None,
                'upset': grade(-spread, actual) == 'loss' if spread not in (None, 0) else None,
                'pickedTeam': picked, 'pickedUnderdog': picked_underdog,
                'pickWinProbability': probability, 'neutral': g.get('neutral', False),
                'upsetPickResult': grade(f['coreMargin'], actual) if picked_underdog else 'not_picked',
                'explanation': explanation, 'sourceUrl': g.get('url'), 'quoteProvider': q.get('provider') if quote_ok else None,
                'sourceArchive': 'forecast-archive/' + snap.get('asOf', snap['generatedAt'][:10]) + '-' + hashlib.sha256(snap['generatedAt'].encode()).hexdigest()[:16] + '.json',
            }
    rows = sorted(selected.values(), key=lambda r: r['date'], reverse=True)
    counts = {k: {s: sum(r[k] == s for r in rows) for s in ['win', 'loss', 'push', 'no_pick', 'unavailable']}
              for k in ['winner', 'spread', 'total']}
    counts['upset'] = {s: sum(r['upsetPickResult'] == s for r in rows) for s in ['win', 'loss', 'push']}
    return {'generatedAt': dt.datetime.now(UTC).isoformat(), 'games': rows, 'records': counts,
            'method': 'Latest saved forecast before kickoff, paired with a line retrieved before kickoff. Recovered legacy snapshots are identified. No reconstructed predictions are counted as issued picks.'}


def make_odds(work, model, data):
    games = {g['id']: g for g in data['games']}
    rows = {}
    for f in model['forecasts']:
        g = games[f['id']]
        p = ROOT / '.current-cache' / f'summary-{g["id"]}.json'
        if not p.exists():
            continue
        cached = read(p)
        x = cached['data']
        comp = x.get('header', {}).get('competitions', [{}])[0]
        offers = sorted(x.get('pickcenter', []), key=lambda x: x.get('provider', {}).get('priority', 99))
        offer = next((o for o in offers if all(isinstance(o.get(s+'TeamOdds', {}).get('moneyLine'), (int, float)) for s in ['home', 'away'])), None)
        if offer:
            rows[g['id']] = {'id': g['id'], 'date': g['date'], 'state': comp.get('status', {}).get('type', {}).get('state'),
                            'timeValid': g['timeValid'], 'retrievedAt': cached['retrievedAt'], 'url': g['url'],
                            'provider': offer.get('provider', {}).get('name'), 'channels': [],
                            'homeMoneyline': offer['homeTeamOdds']['moneyLine'], 'awayMoneyline': offer['awayTeamOdds']['moneyLine']}
    return {'retrievedAt': data['retrievedAt'], 'modelAsOf': data['asOf'], 'games': rows}


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--as-of', default=dt.datetime.now(ZoneInfo('America/New_York')).date().isoformat())
    args = parser.parse_args()
    today = dt.datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    if args.as_of != today:
        raise ValueError('Production refresh must use the current Eastern date; historical replays need a separate path')
    now = dt.datetime.now(UTC)
    run_id = now.strftime('%Y%m%dT%H%M%SZ')
    work = ROOT / '.refresh-work' / run_id
    work.mkdir(parents=True)
    seeds = ['data.json', 'model.json', 'game-details.json', 'history.json', 'research-notes.json', 'context-history-inputs.json']
    for name in seeds:
        shutil.copy2(ROOT/name, work/name)
    old_data, old_model, old_quotes = (read(work/n) for n in seeds[:3])
    env = dict(os.environ, DART_DATA_ROOT=str(work), DART_DATA_DIR=str(work),
               DART_MODEL_INPUT=str(work/'data.json'), DART_MODEL_OUTPUT=str(work/'model.json'),
               DART_HISTORY_CACHE=str(ROOT/'.current-cache'))

    def execute(script, *arguments):
        print('RUN', script, flush=True)
        subprocess.run([sys.executable, str(ROOT/'scripts'/script), *arguments], env=env, cwd=ROOT, check=True, timeout=1800)

    execute('refresh_core.py', '--as-of', args.as_of)
    data = read(work/'current-data.json')
    validate_sources(data, old_data)
    write(work/'data.json', data)
    shutil.copy2(work/'current-game-details.json', work/'game-details.json')
    execute('coach_changes.py')
    execute('model.py')
    model = read(work/'model.json')
    validate_forecasts(data, model, dt.datetime.now(UTC))
    # Keep the original benchmark immutable; current replay metrics are separate.
    replay = {k: model[k] for k in ['core', 'full', 'testedGames', 'testStart', 'testEnd']}
    for key in ['core', 'full', 'heldout', 'calibration', 'testedGames', 'testStart', 'testEnd']:
        model[key] = old_model[key]
    model['evaluationFrozenThrough'] = old_model.get('evaluationFrozenThrough', old_model['testEnd'])
    model['latestReplay'] = replay
    model['refreshRunId'] = run_id
    write(work/'model.json', model)
    execute('matchup_context.py', '--data-file', 'data.json')
    execute('availability.py')
    execute('sportsdataio_check.py')
    execute('matchup_environment.py')
    availability = read(work/'availability.json')
    for f in model['forecasts']:
        row = availability['games'].get(f['id'], {})
        qb = [p for side in ['home', 'away'] for p in (row.get(side) or {}).get('concerns', []) if p['unit'] == 'Quarterback']
        f['availabilityStatus'] = row.get('status', 'not_reported')
        f['reviewRequired'] = bool(qb)
        f['lineupWatch'] = [p['name'] + ': ' + p['status'] for p in qb]
    write(work/'model.json', model)
    write(work/'parlay-odds.json', make_odds(work, model, data))
    execute('sniper_props.py')
    # Preserve all completed games in the history browser.
    history = read(work/'history.json')
    merged = {g['id']: g for g in history['games']}
    merged.update({g['id']: g for g in data['games'] if g['done']})
    history['games'] = sorted(merged.values(), key=lambda g: g['date'])
    history['asOf'] = args.as_of
    write(work/'history.json', history)
    archive = ROOT/'forecast-archive'
    snaps = [read(p) for p in archive.glob('*.json')]
    recovered = snapshot(old_data, old_model, old_quotes, now.isoformat(), recovered=True)
    if not any(s['generatedAt'] == recovered['generatedAt'] for s in snaps):
        snaps.append(recovered)
    current = snapshot(data, model, read(work/'game-details.json'), dt.datetime.now(UTC).isoformat())
    snaps.append(current)
    write(work/'daily-results.json', grade_snapshots(snaps, data))
    context = read(work/'matchup-context.json')
    status = {'runId': run_id, 'status': 'validated', 'dataAsOf': data['asOf'],
              'lastSuccessfulRefresh': dt.datetime.now(UTC).isoformat(), 'staleAfterHours': 30,
              'scheduleTeams': len(data['refresh']['scheduleTeamsRefreshed']), 'forecastGames': len(model['forecasts']),
              'availability': availability['coverage'], 'supplementalInjuryCheck': availability['supplementalCheck'], 'coachChangeTrial': model.get('coachChangeTrial'), 'sourceWarnings': availability['failures'] + context['fetchFailures'] + read(work/'coach-change-history.json')['fetchFailures'],
              'modelLimit': 'Player availability, QB starts and weather are displayed as evidence; their numerical effects have not been fitted. Reported QB concerns exclude a game from automated tickets.'}
    write(work/'refresh-status.json', status)
    validate_forecasts(data, model, dt.datetime.now(UTC))
    # No repository data is replaced until the release passes the checks above.
    publish = ['data.json', 'model.json', 'game-details.json', 'history.json', 'current-data.json',
               'current-game-details.json', 'latest-results.json', 'matchup-context.json', 'availability.json',
               'matchup-environment.json', 'coach-change-history.json', 'context-history-inputs.json', 'parlay-odds.json', 'sniper-props.json', 'daily-results.json', 'refresh-status.json']
    for name in publish:
        read(work/name)  # Every output must exist and parse.
    for snap in [recovered, current]:
        key = hashlib.sha256(snap['generatedAt'].encode()).hexdigest()[:16]
        destination = archive/(snap['asOf']+'-'+key+'.json')
        if not destination.exists():
            write(destination, snap)
    for name in publish:
        shutil.copy2(work/name, ROOT/name)
    print(json.dumps(status, indent=2), flush=True)


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        write(ROOT/'refresh-failure.json', {'failedAt': dt.datetime.now(UTC).isoformat(), 'error': str(error)})
        raise
