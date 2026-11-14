"""Supplement experimental Sims with real current-season team schedules."""
import concurrent.futures, datetime as dt, json, math, os
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
def build(data, fetch, now):
 season=int(data['asOf'][:4]); rows={}; failures=[]
 def one(item):
  tid,team=item
  if not str(tid).isdigit() or team.get('name')=='TBD':return tid,None
  d=fetch(tid,season)
  if str(d.get('team',{}).get('id'))!=str(tid) or int(d.get('season',{}).get('year',0))!=season:raise ValueError('Team/season mismatch')
  games=[];venues=set();seen=set()
  for e in d.get('events',[]):
   if e.get('id') in seen:continue
   seen.add(e.get('id'))
   c=(e.get('competitions') or [{}])[0]; competitors=c.get('competitors',[])
   us=next((x for x in competitors if str(x.get('id'))==str(tid)),None);them=next((x for x in competitors if str(x.get('id'))!=str(tid)),None)
   if not us or not them:continue
   if us.get('homeAway')=='home' and not c.get('neutralSite') and c.get('venue',{}).get('fullName'):venues.add(c['venue']['fullName'])
   if not c.get('status',{}).get('type',{}).get('completed'):continue
   try:
    date=dt.datetime.fromisoformat(e['date'].replace('Z','+00:00'))
    pf=float(us['score']['value']);pa=float(them['score']['value'])
    if date>now or not all(math.isfinite(x) and x>=0 for x in [pf,pa]):continue
   except (KeyError,ValueError,TypeError):continue
   games.append({'id':e['id'],'date':e['date'],'pf':pf,'pa':pa,'opponent':str(them['id']),'source':f"https://www.espn.com/college-football/game/_/gameId/{e['id']}"})
  return tid,{'games':games,'venues':sorted(venues),'n':len(games),'off':sum(g['pf'] for g in games)/len(games) if games else None,'def':sum(g['pa'] for g in games)/len(games) if games else None,'adjusted':False,'retrievedAt':now.isoformat()}
 # Fetch only teams missing a usable three-game season sample in the core feed.
 missing=[(t,v) for t,v in data['teams'].items() if sum(g.get('done',False) and g.get('season')==season and t in (g.get('home'),g.get('away')) and isinstance(g.get('hs'),(int,float)) and isinstance(g.get('as'),(int,float)) for g in data['games'])<3]
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
  jobs={pool.submit(one,item):item[0] for item in missing}
  for future in concurrent.futures.as_completed(jobs):
   try:
    tid,row=future.result()
    if row:rows[tid]=row
   except Exception:failures.append(jobs[future])
 return {'season':season,'retrievedAt':now.isoformat(),'source':'ESPN completed team schedules; raw scoring averages, not opponent-adjusted','teams':rows,'unavailable':sorted(failures)}
def fetch(tid,season):
 with urlopen(f'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{tid}/schedule?season={season}',timeout=15) as response:return json.load(response)
if __name__=='__main__':
 root=Path(os.environ.get('DART_DATA_ROOT',ROOT));data=json.loads((root/'data.json').read_text());result=build(data,fetch,dt.datetime.now(dt.timezone.utc));(root/'sims-data.json').write_text(json.dumps(result,separators=(',',':')));print('Sims supplemental teams',len(result['teams']),'unavailable',len(result['unavailable']))
