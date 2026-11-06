"""Prospective upset research: source-backed matchup inputs and a shadow model.

No narrative bonuses or changes to production core forecasts. Historical feature
reconstruction is development evidence, never an issued-pick record.
"""
import argparse
import concurrent.futures
import datetime as dt
import json
import math
import os
from pathlib import Path

import numpy as np
from refresh_core import get, BASE

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'upset-research-v2-opponent-baseline'
METRIC_VERSION = 1
MIN_TRAIN = 60
LABELS = ['Protection matchup', 'Run-game resistance', 'Touchdown drives']
PASS = {'Pass Reception', 'Pass Incompletion', 'Passing Touchdown', 'Sack',
        'Interception', 'Pass Interception Return'}
RUN = {'Rush', 'Rushing Touchdown'}


def date(s):
    if not isinstance(s, str):
        raise ValueError('Missing timestamp')
    parsed = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp needs a timezone')
    return parsed


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False))


def extract(summary, game, observed):
    """Count regulation dropbacks, runs and offensive drives; no text inference."""
    competition = (summary.get('header', {}).get('competitions') or [{}])[0]
    if str(summary.get('header', {}).get('id', game['id'])) != str(game['id']):
        return None
    if not competition.get('status', {}).get('type', {}).get('completed'):
        return None
    competitors = {str(x.get('id')) for x in competition.get('competitors', [])}
    if competitors != {str(game['home']), str(game['away'])}:
        return None
    rows = {t: dict(passPlays=0, sacks=0, runs=0, stuffed=0, drives=0, touchdowns=0)
            for t in [game['home'], game['away']]}
    seen_plays, seen_drives = set(), set()
    for drive in summary.get('drives', {}).get('previous', []):
        did = drive.get('id')
        if did and did in seen_drives:
            continue
        if did:
            seen_drives.add(did)
        offense = str(drive.get('team', {}).get('id', ''))
        drive_plays = []
        for p in drive.get('plays', []):
            pid = p.get('id')
            if pid and pid in seen_plays:
                continue
            if pid:
                seen_plays.add(pid)
            kind = p.get('type', {}).get('text')
            start = p.get('start', {})
            team = str(start.get('team', {}).get('id', ''))
            text = p.get('text', '').lower()
            if (kind not in PASS | RUN or p.get('isPenalty') or team not in rows
                    or start.get('down') not in (1, 2, 3, 4)
                    or p.get('period', {}).get('number', 1) > 4
                    or 'kneel' in text or 'spike' in text):
                continue
            row = rows[team]
            if kind in PASS:
                row['passPlays'] += 1
                row['sacks'] += int(kind == 'Sack')
            else:
                row['runs'] += 1
                row['stuffed'] += int(p.get('statYardage', 0) <= 0)
            if team == offense:
                drive_plays.append(p)
        # A kneel-only possession is not a scoring opportunity. TD requires an
        # offensive TD play; a pick-six at the end is not credited to the offense.
        if offense in rows and drive_plays:
            rows[offense]['drives'] += 1
            rows[offense]['touchdowns'] += int(any(
                p.get('type', {}).get('text') in {'Passing Touchdown', 'Rushing Touchdown'}
                and not p.get('isTurnover') for p in drive_plays))
    if not all(r['passPlays'] + r['runs'] >= 10 and r['drives'] >= 3 for r in rows.values()):
        return None
    return {'id': game['id'], 'date': game['date'], 'season': game['season'],
            'home': game['home'], 'away': game['away'], 'teams': rows,
            'schemaVersion': METRIC_VERSION, 'sourceUrl': BASE + 'summary?event=' + game['id'],
            'observedAt': observed, 'method': 'Regulation only; sacks are a pressure proxy; TDs per offensive drive, not red-zone efficiency.'}


def collect(data, existing, cache, workers=8):
    season = int(data['asOf'][:4])
    games = [g for g in data['games'] if g['done'] and g['season'] == season
             and g['date'][:10] <= data['asOf']]
    saved = (existing or {}).get('games', {})
    output, failures = {}, []

    def one(g):
        old = saved.get(g['id'])
        if (old and old.get('schemaVersion') == METRIC_VERSION
                and all(old.get(k) == g[k] for k in ['date', 'home', 'away', 'season'])):
            return g['id'], old, None
        cached = read(cache / ('summary-' + g['id'] + '.json'), {})
        if cached.get('retrievedAt') and (row := extract(cached.get('data', cached), g, cached['retrievedAt'])):
            return g['id'], row, None
        raw, error = get(BASE + 'summary?event=' + g['id'])
        row = extract(raw, g, stamp()) if raw else None
        return g['id'], row, error or (None if row else 'Incomplete or mismatched play-by-play')

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for index, (gid, row, error) in enumerate(pool.map(one, games), 1):
            if row:
                output[gid] = row
            else:
                failures.append({'id': gid, 'error': error})
            if index % 100 == 0:
                print(f'Play metrics: {index}/{len(games)} checked, {len(failures)} unavailable', flush=True)
    return {'schemaVersion': METRIC_VERSION, 'generatedAt': stamp(), 'asOf': data['asOf'],
            'games': output, 'coverage': {'completedGames': len(games), 'usableGames': len(output)},
            'failures': failures}


def profile(team, game, metrics, cutoff):
    totals = {s: dict(passPlays=0, sacks=0, runs=0, stuffed=0, drives=0, touchdowns=0)
              for s in ['offense', 'defense']}
    sources = []
    for row in metrics['games'].values():
        if (row['season'] != game['season'] or row['date'][:10] >= game['date'][:10]
                or date(row['date']) >= cutoff or row['id'] == game['id']
                or team not in [row['home'], row['away']]):
            continue
        opponent = row['away'] if row['home'] == team else row['home']
        for side, tid in [('offense', team), ('defense', opponent)]:
            for key in totals[side]:
                totals[side][key] += row['teams'][tid][key]
        sources.append({k: row[k] for k in ['id', 'date', 'sourceUrl', 'observedAt']})
    ready = len(sources) >= 3 and all(r['passPlays'] >= 60 and r['runs'] >= 60 and r['drives'] >= 20 for r in totals.values())
    rates = {}
    for side, r in totals.items():
        rates[side] = {
            'sackRate': r['sacks'] / r['passPlays'] if r['passPlays'] else None,
            'stuffRate': r['stuffed'] / r['runs'] if r['runs'] else None,
            'rushShare': r['runs'] / (r['runs'] + r['passPlays']) if r['runs'] + r['passPlays'] else None,
            'tdDriveRate': r['touchdowns'] / r['drives'] if r['drives'] else None}
    return {'teamId': team, 'ready': ready, 'games': len(sources), 'counts': totals,
            **rates, 'sources': sources}


def features(game, metrics, cutoff):
    h, a = [profile(game[s], game, metrics, cutoff) for s in ['home', 'away']]
    if not h['ready'] or not a['ready']:
        return None, h, a
    ho, hd, ao, ad = h['offense'], h['defense'], a['offense'], a['defense']
    values = [10000 * (ao['sackRate'] * hd['sackRate'] - ho['sackRate'] * ad['sackRate']),
              100 * (ao['rushShare'] * hd['stuffRate'] - ho['rushShare'] * ad['stuffRate']),
              100 * (ho['tdDriveRate'] + ad['tdDriveRate'] - ao['tdDriveRate'] - hd['tdDriveRate'])]
    return values, h, a


def fit(rows):
    x = np.array([r['x'] for r in rows]); y = np.array([r['actual'] - r['baseline'] for r in rows])
    mean, scale = x.mean(0), x.std(0)
    scale[scale < 1e-8] = 1
    z = (x - mean) / scale
    # No intercept: this experiment tests new matchup information, not a new
    # global home-field offset. Fixed ridge penalty, no tuning on the casebook.
    beta = np.linalg.solve(z.T @ z + 30 * np.eye(len(LABELS)), z.T @ y)
    return mean, scale, beta


def adjustments(fitted, values):
    mean, scale, beta = fitted
    return ((np.array(values) - mean) / scale * beta).tolist()


def probability(margin, sd):
    return .5 * (1 + math.erf(margin / (sd * math.sqrt(2))))


def lineup(game, availability, observed):
    raw = availability.get('games', {}).get(game['id'], {})
    sides = {}
    for side in ['home', 'away']:
        row = raw.get(side) or {}
        try:
            checked = date(row['retrievedAt']); published = date(row['publishedAt'])
            valid = (raw.get('status') == 'reported' and row.get('status') == 'reported'
                     and row.get('teamId') == game[side] and row.get('gameDate') == game['date'][:10]
                     and row.get('opponent') == game['away' if side == 'home' else 'home']
                     and published <= checked <= observed < date(game['date'])
                     and (observed - checked).total_seconds() <= 48 * 3600)
        except (KeyError, ValueError, TypeError):
            valid = False
        concerns = [{k: p.get(k) for k in ['name', 'position', 'unit', 'status']}
                    for p in row.get('concerns', []) if p.get('unit') in ['Quarterback', 'Center', 'Offensive line']] if valid else []
        sides[side] = {'status': 'reported' if valid else 'unknown', 'concerns': concerns,
                       'sourceUrl': row.get('sourceUrl') if valid else None,
                       'observedAt': row.get('retrievedAt') if valid else None,
                       'publishedAt': row.get('publishedAt') if valid else None,
                       'startingRoles': 'unknown'}
    return sides


def apply(data, model, metrics, availability, now=None):
    """Fit only against expanding-date baseline errors; never use current injuries
    in historical rows. The saved old core/full evaluation stays untouched.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    byid = {g['id']: g for g in data['games']}
    records = []
    for r in model.get('heldout', []):
        g = byid.get(r['id'])
        if not g or not g['done'] or date(g['date']) >= now:
            continue
        values, _, _ = features(g, metrics, date(g['date']))
        if values is not None:
            records.append({'id': r['id'], 'date': g['date'], 'x': values,
                            'baseline': r['core'][0], 'actual': r['actual'][0], 'sd': r['coreSd']})
    replay = []
    for day in sorted({r['date'][:10] for r in records}):
        earlier = [r for r in records if r['date'][:10] < day]
        if len(earlier) < MIN_TRAIN:
            continue
        fitted = fit(earlier)
        for r in records:
            if r['date'][:10] == day:
                replay.append({**{k: r[k] for k in ['id', 'date', 'baseline', 'actual', 'sd']},
                               'candidate': r['baseline'] + sum(adjustments(fitted, r['x']))})
    fitted = fit(records) if len(records) >= MIN_TRAIN else None
    ready = 0
    for f in model['forecasts']:
        g = byid[f['id']]
        values, h, a = features(g, metrics, min(now, date(model['inputRetrievedAt'])))
        covered = fitted is not None and values is not None and now < date(g['date']) and not g['done']
        parts = adjustments(fitted, values) if covered else []
        margin = f['coreMargin'] + sum(parts) if covered else None
        teams = data['teams']; name = lambda t: teams.get(t, {}).get('name', t)
        lineups = lineup(g, availability, now)
        missing = ['Confirmed starting QB, replacement experience and starting offensive-line roles are not yet connected.']
        if not h['ready'] or not a['ready']:
            missing.append('Insufficient play-by-play sample for a matchup adjustment.')
        if fitted is None:
            missing.append(f'Need {MIN_TRAIN} usable earlier-game residuals; have {len(records)}.')
        for side in ['home', 'away']:
            if lineups[side]['status'] == 'unknown':
                missing.append(f'{name(g[side])}: no fresh, verified availability report for this game.')
        facts = []
        for own, opponent in [(h, a), (a, h)]:
            if own['ready'] and opponent['ready']:
                facts += [
                    f"{name(own['teamId'])} allowed sacks on {own['offense']['sackRate']:.1%} of counted dropbacks; {name(opponent['teamId'])} sacked opponents on {opponent['defense']['sackRate']:.1%}.",
                    f"{name(own['teamId'])} ran on {own['offense']['rushShare']:.1%} of counted plays; {name(opponent['teamId'])} stopped {opponent['defense']['stuffRate']:.1%} of opponents’ runs for no gain or a loss.",
                    f"{name(own['teamId'])} scored a touchdown on {own['offense']['tdDriveRate']:.1%} of counted drives; {name(opponent['teamId'])} allowed touchdowns on {opponent['defense']['tdDriveRate']:.1%}." ]
        research = {'version': VERSION, 'generatedAt': now.isoformat(), 'status': 'testing' if covered else 'insufficient_data',
                    'appliedToMain': False, 'baselineHomeMargin': f['coreMargin'],
                    'candidateHomeMargin': margin, 'candidateSd': f['coreSd'] if covered else None,
                    'candidateHomeWin': probability(margin, f['coreSd']) if covered else None,
                    'contributions': [{'name': label, 'homeMarginPoints': value} for label, value in zip(LABELS, parts)],
                    'profiles': {'home': h, 'away': a}, 'lineup': lineups, 'facts': facts, 'missing': missing,
                    'reviewRequired': any(s['status'] == 'unknown' or s['concerns'] for s in lineups.values()),
                    'limit': 'Experimental matchup adjustment. Starting-role changes have no fitted numerical effect. Sack and run rates are not independently opponent-adjusted; the baseline already includes team strength. TDs per drive are not red-zone efficiency. Rest, rivalry, travel and crowd narratives add no automatic points.'}
        f['upsetResearch'] = research
        ready += int(covered)
    summary = {'version': VERSION, 'status': 'testing', 'appliedToMain': False,
               'trainingRows': len(records), 'forecastGames': len(model['forecasts']), 'coveredForecasts': ready,
               'metricCoverage': metrics['coverage'], 'historicalReplay': {
                   'games': len(replay), 'type': 'development_replay',
                   'baselineMarginMAE': sum(abs(r['baseline'] - r['actual']) for r in replay) / len(replay) if replay else None,
                   'candidateMarginMAE': sum(abs(r['candidate'] - r['actual']) for r in replay) / len(replay) if replay else None,
                   'note': 'Earlier-date residual training; same games for both models. Reconstructed inputs were retrieved later. Casebook games may be included; this is development evidence, not independent proof or issued picks.'},
               'method': 'Ridge penalty 30 on three standardized matchup features, fitted to expanding-date core-margin residuals. Minimum 60 earlier residuals. Core uncertainty retained; no manual injury penalty. No automatic promotion.'}
    model['upsetResearchTrial'] = summary
    return summary


def grade_trial(snapshots, data):
    """Only actually recorded pre-kickoff candidate/base pairs count."""
    completed = {g['id']: g for g in data['games'] if g['done']}
    chosen = {}
    for snap in sorted(snapshots, key=lambda s: s.get('recordedAt', '')):
        if snap.get('type') != 'prospective_snapshot':
            continue
        for f in snap['forecasts']:
            r = f.get('upsetResearch') or {}; g = completed.get(f['id']); original = snap['games'].get(f['id'])
            if r.get('version') != VERSION or r.get('status') != 'testing' or not g or not original or original.get('done'):
                continue
            try:
                cutoff = min(date(original['date']), date(g['date']))
                if not date(r['generatedAt']) <= date(snap['recordedAt']) < cutoff or date(snap['generatedAt']) >= cutoff:
                    continue
                baseline, candidate, sd = f['coreMargin'], r['candidateHomeMargin'], r['candidateSd']
                if not all(math.isfinite(v) for v in [baseline, candidate, sd]) or sd <= 0:
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            actual = g['hs'] - g['as']; target = int(actual > 0)
            q = snap.get('quotes', {}).get(f['id'], {})
            try:
                spread = q.get('homeSpread') if date(q['retrievedAt']) <= date(snap['recordedAt']) < cutoff else None
            except (KeyError, TypeError, ValueError):
                spread = None
            row = {'id': g['id'], 'date': g['date'], 'recordedAt': snap['recordedAt'],
                   'version': VERSION, 'actualHomeMargin': actual, 'homeSpread': spread}
            for label, margin in [('baseline', baseline), ('candidate', candidate)]:
                upset = isinstance(spread, (int, float)) and spread != 0 and margin * spread > 0
                row[label] = {'homeMargin': margin, 'absoluteError': abs(margin - actual),
                              'brier': (probability(margin, sd) - target) ** 2,
                              'winner': 'no_pick' if margin == 0 else 'win' if (margin > 0) == (actual > 0) else 'loss',
                              'pickedUnderdog': upset}
            chosen[g['id']] = row
    rows = list(chosen.values()); summary = {}
    for label in ['baseline', 'candidate']:
        summary[label] = {'games': len(rows),
                         'marginMAE': sum(r[label]['absoluteError'] for r in rows) / len(rows) if rows else None,
                         'brier': sum(r[label]['brier'] for r in rows) / len(rows) if rows else None,
                         'winnerRecord': {s: sum(r[label]['winner'] == s for r in rows) for s in ['win', 'loss', 'no_pick']},
                         'upsetRecord': {s: sum(r[label]['pickedUnderdog'] and r[label]['winner'] == s for r in rows) for s in ['win', 'loss']}}
    return {'version': VERSION, 'generatedAt': stamp(), 'games': sorted(rows, key=lambda r: r['date'], reverse=True),
            'summary': summary, 'method': 'Latest prospectively recorded pre-kickoff pair per game. Includes losses and games with no adjustment. Recovered files and reconstructed historical trials excluded. No profit claim.'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--collect', action='store_true'); args = parser.parse_args()
    root = Path(os.environ.get('DART_DATA_ROOT', str(ROOT)))
    data = read(root / 'data.json')
    if args.collect:
        cache = Path(os.environ.get('DART_HISTORY_CACHE', str(ROOT / '.current-cache')))
        metrics = collect(data, read(root / 'upset-metric-history.json', {}), cache)
        write(root / 'upset-metric-history.json', metrics); print(json.dumps(metrics['coverage']), flush=True)
    else:
        model = read(root / 'model.json')
        summary = apply(data, model, read(root / 'upset-metric-history.json'), read(root / 'availability.json', {}))
        write(root / 'model.json', model); print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
