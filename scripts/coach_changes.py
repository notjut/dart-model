"""Source-backed first-game-after-dismissal records; never invent a motivation bonus."""
import argparse,concurrent.futures,datetime as dt,json,math,os
from pathlib import Path
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo('America/New_York')
BASE='https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event='
def day(value):return dt.datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ET).date().isoformat()
def confirmed_change(team,season,as_of,events):
 candidates=[e for e in events if e['team']==team and e['season']==season and e.get('immediate') and e['date']<=as_of]
 return max(candidates,key=lambda e:e['date']) if candidates else None

def first_game(event,games):
 if not event.get('immediate'):return None
 candidates=[g for g in games if event['team'] in (g['home'],g['away']) and g['season']==event['season'] and day(g['date'])>event['date']]
 return min(candidates,key=lambda g:g['date']) if candidates else None

def archived_line(payload,game):
 competition=payload.get('header',{}).get('competitions',[{}])[0]
 if str(payload.get('header',{}).get('id',''))!=str(game['id']) or competition.get('status',{}).get('type',{}).get('completed') is not True:return None
 teams={str(c.get('id')):c.get('homeAway') for c in competition.get('competitors',[])}
 if teams.get(game['home'])!='home' or teams.get(game['away'])!='away':return None
 for q in sorted(payload.get('pickcenter',[]),key=lambda q:q.get('provider',{}).get('priority',99)):
  provider=q.get('provider',{}).get('name','')
  if provider.lower() in ('numberfire','teamrankings','espn fpi'):continue
  h,a=q.get('homeTeamOdds',{}),q.get('awayTeamOdds',{})
  if str(h.get('teamId',game['home']))!=game['home'] or str(a.get('teamId',game['away']))!=game['away']:continue
  spread=q.get('spread')
  if not isinstance(spread,(int,float)) or not math.isfinite(spread):continue
  if spread==0:line=0
  elif h.get('favorite') is True and a.get('favorite') is not True:line=-abs(spread)
  elif a.get('favorite') is True and h.get('favorite') is not True:line=abs(spread)
  else:continue
  return {'homeSpread':line,'provider':provider,'sourceUrl':game.get('url',BASE+game['id']),'retrievedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'basis':'Archived postgame odds; exact closing time not verified. Descriptive history, not a saved pregame betting record.'}
 return None

def record(rows):
 completed=[r for r in rows if r['completed']]
 return {'games':len(completed),'wins':sum(r['won'] is True for r in completed),'losses':sum(r['won'] is False for r in completed),'ties':sum(r['margin']==0 for r in completed),'atsWins':sum(r['ats']=='win' for r in completed),'atsLosses':sum(r['ats']=='loss' for r in completed),'atsPushes':sum(r['ats']=='push' for r in completed),'missingLines':sum(r['ats']=='unavailable' for r in completed),'averageMargin':round(sum(r['margin'] for r in completed)/len(completed),1) if completed else None,'averageVsSpread':round(sum(r['margin']+r['teamSpread'] for r in completed if r['teamSpread'] is not None)/sum(r['teamSpread'] is not None for r in completed),1) if any(r['teamSpread'] is not None for r in completed) else None,'gameIds':[r['gameId'] for r in completed]}

def cohorts(rows):
 strict=[r for r in rows if r['changeType']=='dismissal']
 fbs=[r for r in strict if r['fbsOpponent']]
 return {'all':record(strict),'fbs':record(fbs),'home':record([r for r in fbs if r['location']=='home']),'road':record([r for r in fbs if r['location']=='away']),'underdogs':record([r for r in fbs if r['teamSpread'] is not None and r['teamSpread']>0]),'homeUnderdogs':record([r for r in fbs if r['location']=='home' and r['teamSpread'] is not None and r['teamSpread']>0]),'roadUnderdogs':record([r for r in fbs if r['location']=='away' and r['teamSpread'] is not None and r['teamSpread']>0]),'withinSevenDays':record([r for r in fbs if r['daysAfterChange']<=7]),'afterLongerBreak':record([r for r in fbs if r['daysAfterChange']>7]),'mutualDepartures':record([r for r in rows if r['changeType']=='mutual_departure'])}

def build(data,history,registry,quotes):
 all_games={g['id']:dict(g,done=True) for g in history['games']}
 all_games.update({g['id']:g for g in data['games']})
 rows=[];unmatched=[]
 for e in registry['events']:
  if e['date']>data['asOf']:continue
  g=first_game(e,all_games.values())
  if not g:unmatched.append(e['id']);continue
  side='home' if g['home']==e['team'] else 'away';opp=g['away' if side=='home' else 'home'];t=data['teams'].get(opp,{});q=quotes.get(g['id']);complete=bool(g.get('done') and day(g['date'])<=data['asOf'])
  margin=(g['hs']-g['as'])*(1 if side=='home' else -1) if complete else None
  line=q['homeSpread']*(1 if side=='home' else -1) if q else None
  ats='unavailable' if not complete or line is None else 'win' if margin+line>0 else 'loss' if margin+line<0 else 'push'
  rows.append(dict(e,gameId=g['id'],gameDate=g['date'],gameLocalDate=day(g['date']),gameUrl=g.get('url'),opponent=opp,opponentName=t.get('name') or g.get('awayName' if side=='home' else 'homeName') or opp,fbsOpponent=bool(t and t.get('conference')!='Non-FBS opponent'),location='neutral' if g.get('neutral') else side.replace('home','home').replace('away','away'),daysAfterChange=(dt.date.fromisoformat(day(g['date']))-dt.date.fromisoformat(e['date'])).days,completed=complete,scoreFor=g['hs' if side=='home' else 'as'] if complete else None,scoreAgainst=g['as' if side=='home' else 'hs'] if complete else None,margin=margin,won=(margin>0 if margin else None) if complete else None,teamSpread=line,ats=ats,quote=q))
 # Only earlier completed games may explain a current forecast.
 matches={}
 for r in rows:
  if not r['completed'] and r['gameDate'][:10]>=data['asOf']:
   prior=[v for v in rows if v['completed'] and day(v['gameDate'])<day(r['gameDate'])]
   matches.setdefault(r['gameId'],{'events':[],'history':cohorts(prior)})['events'].append(r)
 return {'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'asOf':data['asOf'],'coverage':registry['coverage'],'eventsVerified':len(registry['events']),'rows':rows,'unmatchedEvents':unmatched,'cohorts':cohorts(rows),'games':matches,'modelUse':'A first-game dismissal indicator is tested as a candidate feature. No fixed motivation bonus and no validated change to the main score.','quotes':quotes}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--offline',action='store_true');args=ap.parse_args()
 data_dir=Path(os.environ.get('DART_DATA_DIR',str(ROOT)))
 data=json.loads((data_dir/'data.json').read_text());history=json.loads((data_dir/'history.json').read_text());registry=json.loads((ROOT/'coach-change-events.json').read_text())
 previous=ROOT/'coach-change-history.json';quotes=json.loads(previous.read_text()).get('quotes',{}) if previous.exists() else {};errors=[]
 games={g['id']:dict(g,done=True) for g in history['games']};games.update({g['id']:g for g in data['games']})
 targets={g['id']:g for e in registry['events'] if e['date']<=data['asOf'] for g in [first_game(e,games.values())] if g and g.get('done') and day(g['date'])<=data['asOf'] and g['id'] not in quotes}
 def fetch(g):
  try:
   with urlopen(Request(BASE+g['id'],headers={'User-Agent':'Darkhorse historical research'}),timeout=20) as res:q=archived_line(json.load(res),g)
   return g['id'],q,None
  except Exception as ex:return g['id'],None,type(ex).__name__
 if not args.offline:
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
   for gid,q,error in pool.map(fetch,targets.values()):
    if q:quotes[gid]=q
    if error:errors.append({'gameId':gid,'error':error})
 out=build(data,history,registry,quotes);out['fetchFailures']=errors
 (data_dir/'coach-change-history.json').write_text(json.dumps(out,separators=(',',':')))
 print(json.dumps({'events':out['eventsVerified'],'rows':len(out['rows']),'cohorts':out['cohorts'],'active':list(out['games']),'failures':errors},indent=2))
if __name__=='__main__':main()
