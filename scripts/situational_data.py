"""Generic, source-backed game situations for private research tools.
No betting strategy, password or model-weight changes belong in this collector.
"""
import csv,datetime as dt,gzip,io,json,math,os
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
UTC=dt.timezone.utc
BASE='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/'
def number(v):
 try:
  n=float(v);return n if math.isfinite(n) else None
 except (ValueError,TypeError):return None
def stamp(v):return dt.datetime.fromisoformat(v.replace('Z','+00:00'))
def truth(v):return str(v).lower()=='true'
def read(path,default):
 try:return json.loads(path.read_text())
 except (OSError,ValueError):return default
def fetch_csv(tag,name):
 url=BASE+tag+'/'+name
 with urlopen(Request(url,headers={'User-Agent':'Darkhorse situational research'}),timeout=35) as r:raw=r.read()
 if name.endswith('.gz'):raw=gzip.decompress(raw)
 rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
 if len(rows)<100:raise ValueError('Incomplete situational source')
 return rows,url

def build(schedules,betting,metadata,data,quotes,started,now,run_id):
 markets={str(r['game_id']):r for r in betting};teams={}
 for r in metadata:
  if not r.get('team_id'):continue
  teams[str(r['team_id'])]={'name':r.get('school') or r.get('location') or r.get('display_name'),'abbr':r.get('abbreviation'),'venueId':r.get('venue_id'),'latitude':number(r.get('latitude')),'longitude':number(r.get('longitude')),'timezone':r.get('timezone'),'logo':r.get('team_logo'),'fbs':truth(r.get('is_fbs'))}
 games={}
 for r in schedules:
  if r.get('season_type')!='regular' or not truth(r.get('fbs_participant')):continue
  gid=str(r['game_id']);q=markets.get(gid,{});line=number(q.get('home_team_spread')) if truth(q.get('game_spread_available')) and q.get('odds_source')!='default' else None
  complete=truth(r.get('completed')) and r.get('status')=='STATUS_FINAL'
  games[gid]={'id':gid,'season':int(r['season']),'date':r['start_date'],'home':str(r['home_id']),'away':str(r['away_id']),'homeScore':number(r.get('home_points')) if complete else None,'awayScore':number(r.get('away_points')) if complete else None,'done':complete,'status':r.get('status'),'neutral':truth(r.get('neutral_site')),'venueId':r.get('venue_id'),'venue':r.get('venue'),'fbs':truth(r.get('fbs_game')),'homeSpread':line,'spreadBasis':'archived sportsbook close' if line is not None else None,'quote':None}
 # Fresh site scores and schedule status take precedence; odds retain explicit provenance.
 for g in data.get('games',[]):
  gid=str(g['id']);r=games.get(gid)
  if not r:continue
  if g.get('done') and stamp(g['date'])<now and number(g.get('hs')) is not None and number(g.get('as')) is not None:r.update(done=True,status='STATUS_FINAL',homeScore=g['hs'],awayScore=g['as'])
  if any(s in str(g.get('status','')) for s in ['POSTPON','CANCEL','SUSPEND']):r.update(done=False,status=g['status'])
  if g.get('timeValid') is False:r['timeValid']=False
 frozen={str(g['id']):g.get('savedPick',{}).get('quote') for g in started.get('games',[])}
 for gid,r in games.items():
  q=quotes.get('games',{}).get(gid);saved=frozen.get(gid)
  candidates=[]
  if q and number(q.get('homeSpread')) is not None and q.get('state')=='pre' and q.get('retrievedAt'):
   try:
    if stamp(q['retrievedAt'])<=now and stamp(q['retrievedAt'])<stamp(r['date']):candidates.append({'homeSpread':q['homeSpread'],'provider':q.get('provider'),'retrievedAt':q['retrievedAt'],'homeOdds':q.get('homeSpreadOdds'),'awayOdds':q.get('awaySpreadOdds')})
   except (ValueError,TypeError):pass
  if saved and number(saved.get('homeSpread')) is not None and saved.get('retrievedAt'):
   try:
    if stamp(saved['retrievedAt'])<=now and stamp(saved['retrievedAt'])<stamp(r['date']):candidates.append(dict(saved))
   except (ValueError,TypeError):pass
  if candidates:
   q=max(candidates,key=lambda q:q['retrievedAt']);r['quote']=q
   if not r['done'] or r['homeSpread'] is None:r.update(homeSpread=q['homeSpread'],spreadBasis='saved pregame quote')
 # Generic recent form for both sides; no private rule is evaluated here.
 histories={}
 for r in games.values():
  if r['done'] and stamp(r['date'])<now:
   for side in ['home','away']:histories.setdefault(r[side],[]).append(r)
 for t in histories:histories[t].sort(key=lambda g:g['date'])
 snapshots=[]
 for g in games.values():
  q=g['quote']
  if g['done'] or not g['fbs'] or not q or g.get('timeValid') is False or any(x in str(g['status']) for x in ['POSTPON','CANCEL','SUSPEND']):continue
  seconds=(stamp(g['date'])-now).total_seconds()
  if not 0<seconds<=72*3600:continue
  # Freeze the whole situation before kickoff for all eligible games, not chosen winners.
  if now-stamp(q['retrievedAt'])>dt.timedelta(hours=30):continue
  recent={side:[v for v in histories.get(g[side],[]) if stamp(v['date'])<stamp(g['date'])][-5:] for side in ['home','away']}
  snapshots.append({'gameId':g['id'],'capturedAt':now.isoformat(),'kickoff':g['date'],'game':dict(g),'teams':{s:teams.get(g[s],{}) for s in ['home','away']},'recent':recent,'quote':dict(q)})
 return {'schemaVersion':1,'status':'ready','runId':run_id,'generatedAt':now.isoformat(),'season':now.year,'teams':teams,'games':sorted(games.values(),key=lambda g:g['date']),'snapshots':snapshots}

def merge_archive(previous,snapshots):
 old={s['gameId']:s for s in previous.get('snapshots',[]) if s.get('gameId')}
 for s in snapshots:
  # First complete saved situation is retained; exact quote and context never change.
  old.setdefault(s['gameId'],s)
 return {'schemaVersion':1,'snapshots':sorted(old.values(),key=lambda s:s['kickoff'])}

def main():
 work=Path(os.environ.get('DART_DATA_DIR',str(ROOT)));now=dt.datetime.now(UTC);data=read(work/'data.json',{});model=read(work/'model.json',{});year=now.year
 try:
  s,su=fetch_csv('cfb_schedules',f'cfb_schedules_{year}.csv.gz');b,bu=fetch_csv('espn_cfb_betting',f'betting_{year}.csv');t,tu=fetch_csv('espn_cfb_teams',f'cfb_teams_{year}.csv')
  if not {'game_id','home_id','away_id','home_division'}<=set(s[0]) or not {'game_spread_available','home_team_spread'}<=set(b[0]):raise ValueError('Unexpected situational schema')
  out=build(s,b,t,data,read(work/'parlay-odds.json',{}),read(work/'started-games.json',{}),now,model.get('refreshRunId'))
  out['sources']=[su,bu,tu]
  if len(out['games'])<500 or sum(v['fbs'] for v in out['teams'].values())<120:raise ValueError('Incomplete research coverage')
  archive=merge_archive(read(ROOT/'research-snapshots.json',{}),out.pop('snapshots'))
 except Exception as e:
  out=read(ROOT/'system-data.json',{'schemaVersion':1,'games':[],'teams':{}});out=dict(out,status='delayed',attemptedAt=now.isoformat(),error=type(e).__name__)
  archive=read(ROOT/'research-snapshots.json',{'schemaVersion':1,'snapshots':[]})
 (work/'system-data.json').write_text(json.dumps(out,separators=(',',':')))
 (work/'research-snapshots.json').write_text(json.dumps(archive,separators=(',',':')))
 print('Situational research:',out['status'],'games',len(out['games']),'saved situations',len(archive['snapshots']),flush=True)
if __name__=='__main__':main()
