"""Refresh public ESPN schedules/results without rewriting frozen model inputs.
Outputs current-data.json, current-game-details.json and latest-results.json.
The original data.json/model.json are intentionally untouched: fresh outcomes
must never be represented as inputs to an already-issued forecast.
"""
import argparse, concurrent.futures, copy, datetime as dt, json, os, pathlib, time, urllib.request
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parents[1]
DIST=pathlib.Path(os.environ.get('DART_DATA_ROOT',str(ROOT/'dist' if (ROOT/'dist').is_dir() else ROOT)))
BASE='https://site.api.espn.com/apis/site/v2/sports/football/college-football/'
ACCEPTED={'Rush','Pass Reception','Pass Incompletion','Sack','Passing Touchdown','Rushing Touchdown','Interception','Pass Interception Return','Fumble Recovery (Own)','Fumble Recovery (Opponent)'}
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()
def get(url):
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'DART-Model/1.0 (public sports data refresh)'})
   with urllib.request.urlopen(req,timeout=24) as r:return json.load(r),None
  except Exception as e:
   error=type(e).__name__
   if attempt<2:time.sleep(attempt+1)
 return None,error
def stats(summary):
 out={}
 for side in summary.get('boxscore',{}).get('teams',[]):
  tid=side['team']['id'];raw={v['name']:v.get('displayValue') for v in side.get('statistics',[])}
  out[tid]={'yards':raw.get('totalYards'),'passYards':raw.get('netPassingYards'),'rushYards':raw.get('rushingYards'),'plays':0,'success':0,'explosive':0,'boxscore':raw}
 seen=set()
 for drive in summary.get('drives',{}).get('previous',[]):
  for p in drive.get('plays',[]):
   pid=p.get('id')
   if pid and pid in seen:continue
   if pid:seen.add(pid)
   start=p.get('start',{});tid=start.get('team',{}).get('id');down=start.get('down',0);distance=start.get('distance',0)
   if p.get('type',{}).get('text') not in ACCEPTED or p.get('isPenalty') or tid not in out or down not in [1,2,3,4] or distance<=0 or p.get('period',{}).get('number',1)>4:continue
   text=p.get('text','').lower()
   if 'kneel' in text or 'spike' in text:continue
   gain=p.get('statYardage',0);out[tid]['plays']+=1;out[tid]['success']+=int(gain>=distance*{1:.5,2:.7}.get(down,1) and not p.get('isTurnover',False));out[tid]['explosive']+=int(gain>=20)
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--as-of',default=dt.datetime.now(ZoneInfo('America/New_York')).date().isoformat());ap.add_argument('--workers',type=int,default=10);args=ap.parse_args();dt.date.fromisoformat(args.as_of)
 original=json.loads((DIST/'data.json').read_text());model=json.loads((DIST/'model.json').read_text());output=copy.deepcopy(original);teams=output['teams'];games={g['id']:g for g in output['games']};season=int(args.as_of[:4]);now=stamp();failures=[];fresh=ROOT/'.current-cache';fresh.mkdir(exist_ok=True)
 ids=[t for t in teams if teams[t]['conference']!='Non-FBS opponent'];refreshed_teams=[]
 def schedule(t):
  url=BASE+f'teams/{t}/schedule?season={season}';x,error=get(url);return t,url,x,error
 with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
  for t,url,x,error in pool.map(schedule,ids):
   if x is None:failures.append({'url':url,'error':error});continue
   if not x.get('events'):failures.append({'url':url,'error':'Empty schedule'});continue
   refreshed_teams.append(t)
   (fresh/f'schedule-{t}-{season}.json').write_text(json.dumps({'retrievedAt':now,'data':x}))
   for e in x.get('events',[]):
    c=e.get('competitions',[{}])[0];cs={z.get('homeAway'):z for z in c.get('competitors',[])}
    if not {'home','away'}<=cs.keys():continue
    h,a=cs['home'],cs['away'];status=c.get('status',e.get('status',{})).get('type',{})
    def score(z):
     v=z.get('score',0);return float(v.get('value',0)) if isinstance(v,dict) else float(v or 0)
    for z in [h,a]:
     tm=z['team'];tid=z['id']
     if tid not in teams:teams[tid]={'id':tid,'name':tm.get('location',tm.get('displayName')),'abbr':tm.get('abbreviation',''),'conference':'Non-FBS opponent','logo':''}
    prev=games.get(e['id'],{});g={**prev,'id':e['id'],'date':e['date'],'season':season,'home':h['id'],'away':a['id'],'hs':score(h),'as':score(a),'done':bool(status.get('completed')),'neutral':c.get('neutralSite',False),'venue':c.get('venue',{}).get('fullName','Venue TBA'),'timeValid':e.get('timeValid',c.get('timeValid',False)),'url':f'https://www.espn.com/college-football/game/_/gameId/{e["id"]}','scheduleRetrievedAt':now,'status':status.get('name')}
    # The refresh is capped at the supplied date; do not admit future final results.
    if g['date'][:10]>args.as_of:g['done']=False
    games[g['id']]=g
 print('Fresh schedules',len(ids)-sum('/schedule?' in f['url'] for f in failures),'failures',len(failures),flush=True)
 forecastIds={f['id'] for f in model['forecasts']};old={g['id']:g for g in original['games']};horizon=(dt.date.fromisoformat(args.as_of)+dt.timedelta(days=14)).isoformat();targets=[g for g in games.values() if g['id'] in forecastIds or (g['season']==season and (not g['done'] and args.as_of<=g['date'][:10]<=horizon or g['done'] and (not old.get(g['id'],{}).get('stats') or g['date'][:10]>=original['asOf'])))]
 details={};refreshed=[]
 def summary(g):
  url=BASE+'summary?event='+g['id'];x,error=get(url);return g,url,x,error
 with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
  for g,url,x,error in pool.map(summary,targets):
   if x is None:failures.append({'url':url,'error':error});continue
   retrieved=stamp();(fresh/f'summary-{g["id"]}.json').write_text(json.dumps({'retrievedAt':retrieved,'data':x}))
   if g['done']:
    g['stats']=stats(x);g['statsRetrievedAt']=retrieved;refreshed.append(g['id'])
   c=x.get('header',{}).get('competitions',[{}])[0];channels=[]
   for b in c.get('broadcasts',[]):
    if b.get('lang','en')!='en' or b.get('region','us')!='us':continue
    for n in b.get('names',[]) or [b.get('media',{}).get('shortName')]:
     if n and n not in channels:channels.append(n)
   row={'id':g['id'],'retrievedAt':retrieved,'date':c.get('date',g['date']),'completed':g['done'],'status':c.get('status',{}).get('type',{}).get('name',g.get('status')),'timeValid':c.get('timeValid',g['timeValid']),'channels':channels,'homeSpread':None,'provider':None,'marketStatus':'unavailable','url':g['url']}
   if not g['done']:
    for o in sorted(x.get('pickcenter',[]),key=lambda v:v.get('provider',{}).get('priority',99)):
     spread=o.get('spread');h=o.get('homeTeamOdds',{});a=o.get('awayTeamOdds',{})
     if not isinstance(spread,(int,float)):continue
     if spread==0:hs=0
     elif h.get('favorite') is True and a.get('favorite') is not True:hs=-abs(spread)
     elif a.get('favorite') is True and h.get('favorite') is not True:hs=abs(spread)
     else:continue
     row.update(homeSpread=hs,provider=o.get('provider',{}).get('name'),marketStatus='posted',overUnder=o.get('overUnder'));break
   else:row['marketStatus']='completed; no live pregame line'
   details[g['id']]=row
 output.update(asOf=args.as_of,retrievedAt=now,games=sorted(games.values(),key=lambda g:g['date']),failures=failures,refresh={'baseSnapshot':original['asOf'],'scheduleTeamsRequested':len(ids),'scheduleTeamsRefreshed':refreshed_teams,'summaryGamesRequested':len(targets),'summaryStatsRefreshed':len(refreshed),'modelRetrained':False,'note':'Current observations are separate from frozen forecasts. Previously loaded game statistics retain their original timestamp when not refreshed.'})
 (DIST/'current-data.json').write_text(json.dumps(output,separators=(',',':')))
 (DIST/'current-game-details.json').write_text(json.dumps({'retrievedAt':now,'games':details,'failures':failures,'source':'ESPN public summary; odds retrieval time is not bookmaker update time'},separators=(',',':')))
 recent=[g for g in games.values() if g['done'] and g['season']==season and original['asOf']<g['date'][:10]<=args.as_of]
 (DIST/'latest-results.json').write_text(json.dumps({'generatedAt':now,'asOf':args.as_of,'originalForecastAsOf':original['asOf'],'games':recent,'refreshedGameIds':refreshed,'coverage':output['refresh'],'failures':failures,'modelRetrained':False},separators=(',',':')))
 print(json.dumps({'currentGames':len(games),'newCompletedResults':len(recent),'statsRefreshed':len(refreshed),'currentDetails':len(details),'failures':len(failures)}),flush=True)
if __name__=='__main__':main()
