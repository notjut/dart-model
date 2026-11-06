"""Observed player production plus optional authenticated posted props. No synthetic odds."""
import concurrent.futures as cf
import datetime as dt
import json
import math
import os
from pathlib import Path
import statistics
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('DART_DATA_ROOT', ROOT))
CACHE = ROOT / '.current-cache'
MARKETS = {'player_pass_yds': ('passing', 'passingYards', 'Passing yards'), 'player_rush_yds': ('rushing', 'rushingYards', 'Rushing yards'), 'player_reception_yds': ('receiving', 'receivingYards', 'Receiving yards'), 'player_receptions': ('receiving', 'receptions', 'Receptions')}
def get(url):
    with urllib.request.urlopen(url, timeout=25) as r:
        return json.load(r)
def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None
def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()
def date(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
def norm(s):
    return ''.join(c for c in s.lower() if c.isalnum())
def summary(g):
    p = CACHE / ('summary-' + g['id'] + '.json')
    try:
        if p.exists():
            d = json.loads(p.read_text()).get('data', {})
            if d.get('boxscore', {}).get('players'):
                return g, d
        d = get('https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=' + g['id'])
        CACHE.mkdir(exist_ok=True)
        p.write_text(json.dumps({'retrievedAt': stamp(), 'data': d}))
        return g, d
    except Exception:
        return g, {}
def extract(g, d):
    rows = []
    for team in d.get('boxscore', {}).get('players', []):
        tid = str(team['team']['id'])
        for group in team.get('statistics', []):
            for market, (category, key, label) in MARKETS.items():
                if group.get('name') != category or key not in group.get('keys', []):
                    continue
                idx = group['keys'].index(key)
                for a in group.get('athletes', []):
                    try:
                        value = float(a['stats'][idx])
                    except (ValueError, IndexError, KeyError):
                        continue
                    rows.append({'playerId': a['athlete']['id'], 'player': a['athlete']['displayName'], 'team': tid, 'market': market, 'value': value, 'gameId': g['id'], 'date': g['date'], 'margin': (g['hs']-g['as']) * (1 if tid == g['home'] else -1)})
    return rows

def main():
    now = dt.datetime.now(dt.timezone.utc)
    data = json.loads((OUT/'data.json').read_text()); model = json.loads((OUT/'model.json').read_text())
    games = {g['id']: g for g in data['games']}
    forecasts = [f for f in model['forecasts'] if f['id'] in games and not games[f['id']]['done'] and date(games[f['id']]['date']) > now]
    teams = {games[f['id']][side] for f in forecasts for side in ('home','away')}
    prior = [g for g in data['games'] if g['done'] and date(g['date']) < now and g['season'] == now.year and (g['home'] in teams or g['away'] in teams)]
    rows=[]; failures=[]; aliases={}
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for g,d in pool.map(summary, prior):
            rows.extend(extract(g,d))
            if not d.get('boxscore',{}).get('players'): failures.append(g['id'])
            for t in d.get('boxscore',{}).get('players',[]):
                aliases[norm(t['team']['displayName'])]=str(t['team']['id'])
    result={'generatedAt':stamp(),'refreshRunId':model.get('refreshRunId'), 'inputRetrievedAt':model.get('inputRetrievedAt'), 'lineStatus':'not_connected', 'games':[], 'missingBoxscores':failures, 'method':'Observed appearances only; missing stat rows are not assumed zero. Matchup projection scales the average by opponent yards allowed relative to loaded league games, capped at 15%. Historical hit rates are not calibrated forecast probabilities. Game-script scenarios describe past final margins, not time spent leading. Player availability and role changes require review.'}
    grouped={}
    for r in rows: grouped.setdefault((r['team'],r['playerId'],r['market']),[]).append(r)
    for f in forecasts:
        g=games[f['id']]; players=[]
        for (tid,pid,market), history in grouped.items():
            if tid not in (g['home'],g['away']): continue
            h=sorted([r for r in history if date(r['date']) < date(g['date'])],key=lambda r:r['date'])[-10:]
            if len(h)<4: continue
            recent=sorted([x['date'] for x in prior if tid in (x['home'],x['away'])])[-2:]
            if not recent or h[-1]['date'] < recent[0]: continue
            opp=g['away'] if tid==g['home'] else g['home']
            key='rushYards' if market=='player_rush_yds' else 'passYards'
            league=[]; allowed=[]
            for old in prior:
                if date(old['date']) >= date(g['date']): continue
                for defense, offense in ((old['home'],old['away']),(old['away'],old['home'])):
                    val=number(old.get('stats',{}).get(offense,{}).get(key))
                    if val is not None:
                        league.append(val)
                        if defense==opp: allowed.append(val)
            factor=1.0
            if market!='player_receptions' and len(allowed)>=4 and league and statistics.mean(league)>0:
                factor=max(.85,min(1.15,statistics.mean(allowed)/statistics.mean(league)))
            average=statistics.mean(r['value'] for r in h)
            scenarios={}
            for label, predicate in [('Won by 8+',lambda x:x>7),('Close finish',lambda x:abs(x)<=7),('Lost by 8+',lambda x:x< -7)]:
                vals=[r['value'] for r in h if predicate(r['margin'])]
                scenarios[label]={'n':len(vals),'average':round(statistics.mean(vals),1) if vals else None}
            players.append({'id':pid,'name':h[-1]['player'],'team':tid,'market':market,'label':MARKETS[market][2],'average':round(average,1),'projection':round(average*factor,1),'matchupFactor':round(factor,3),'opponentSample':len(allowed),'samples':h,'scenarios':scenarios,'quotes':[]})
        players.sort(key=lambda p:(p['team'],p['market'],-p['projection']))
        result['games'].append({'id':g['id'],'date':g['date'],'home':g['home'],'away':g['away'],'reviewRequired':f.get('reviewRequired',False),'players':players})
    result['games'].sort(key=lambda g:g['date'])
    api=os.environ.get('ODDS_API_KEY')
    if api:
        try:
            base='https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/events'
            events=get(base+'?'+urllib.parse.urlencode({'apiKey':api}))
            result['lineStatus']='connected'
            for event in events:
                home=aliases.get(norm(event['home_team'])); away=aliases.get(norm(event['away_team']))
                match=next((g for g in result['games'] if g['home']==home and g['away']==away and abs((date(g['date'])-date(event['commence_time'])).total_seconds())<3600),None)
                if not match: continue
                query=urllib.parse.urlencode({'apiKey':api,'regions':'us','markets':','.join(MARKETS),'oddsFormat':'american'})
                response=get(base+'/'+event['id']+'/odds?'+query)
                for book in response.get('bookmakers',[]):
                    for market in book.get('markets',[]):
                        for outcome in market.get('outcomes',[]):
                            matches=[p for p in match['players'] if p['market']==market['key'] and norm(p['name'])==norm(outcome.get('description',''))]
                            if len(matches)!=1 or outcome.get('name') not in ('Over','Under') or not isinstance(outcome.get('point'),(int,float)): continue
                            matches[0]['quotes'].append({'book':book['title'],'bookKey':book['key'],'side':outcome['name'],'line':outcome['point'],'odds':outcome['price'],'updatedAt':market.get('last_update',book.get('last_update'))})
        except Exception:
            result['lineStatus']='provider_error'
            # Never expose authenticated request URLs or exception messages.
    (OUT/'sniper-props.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False))
    print('Sniper Sauce:',len(result['games']),'games;',sum(len(g['players']) for g in result['games']),'player markets; lines:',result['lineStatus'])
if __name__=='__main__': main()
