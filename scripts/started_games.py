"""Keep recent started games visible using frozen pregame picks, never new forecasts."""
import datetime as dt
import hashlib
import math
from zoneinfo import ZoneInfo
UTC = dt.timezone.utc
ET = ZoneInfo('America/New_York')

def moment(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))

def build(snapshots, data, details, run_id, now=None):
    now = now or dt.datetime.now(UTC)
    cutoff = now.astimezone(ET).date() - dt.timedelta(days=14)
    games = {g['id']: g for g in data['games'] if cutoff <= moment(g['date']).astimezone(ET).date() and moment(g['date']) <= now}
    saved = {}
    for snap in sorted(snapshots, key=lambda s: moment(s['generatedAt'])):
        for f in snap['forecasts']:
            g = games.get(f['id']); original = snap.get('games', {}).get(f['id'])
            if not g or not original or original.get('done'):
                continue
            kickoff = min(moment(g['date']), moment(original['date']))
            if moment(snap['generatedAt']) >= kickoff:
                continue
            if snap.get('type') != 'recovered_saved_forecast' and moment(snap.get('recordedAt', snap['generatedAt'])) >= kickoff:
                continue
            margin, total = f.get('coreMargin'), f.get('coreTotal')
            if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (margin, total)):
                continue
            q = snap.get('quotes', {}).get(f['id'], {})
            quote_ok = q.get('retrievedAt') and moment(q['retrievedAt']) < kickoff
            quote = {k: q.get(k) for k in ('homeSpread', 'overUnder', 'provider', 'retrievedAt')} if quote_ok else {}
            saved[g['id']] = {'forecastAt': snap['generatedAt'], 'recordedAt': snap.get('recordedAt'),
                'archiveType': snap.get('type'), 'homeMargin': margin, 'total': total, 'quote': quote,
                'drivers': f.get('coreContributions', []),
                'sourceArchive': 'forecast-archive/' + snap.get('asOf', snap['generatedAt'][:10]) + '-' + hashlib.sha256(snap['generatedAt'].encode()).hexdigest()[:16] + '.json'}
    rows = []
    for g in games.values():
        quote = details.get('games', {}).get(g['id'], {})
        rows.append({k: g.get(k) for k in ('id','date','home','away','neutral','venue','url','status','done')} | {
            'homeScore': g['hs'] if g['done'] else None, 'awayScore': g['as'] if g['done'] else None,
            'checkedAt': quote.get('retrievedAt', g.get('scheduleRetrievedAt')),
            'channels': quote.get('channels', []), 'savedPick': saved.get(g['id'])})
    return {'runId': run_id, 'generatedAt': now.isoformat(), 'games': sorted(rows, key=lambda g: g['date'], reverse=True),
            'method': 'Recent started games with the latest eligible saved pregame forecast. Status is a refresh snapshot, not a live score feed. No forecasts are rebuilt after kickoff.'}
