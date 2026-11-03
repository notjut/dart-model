"""Refresh source-backed matchup context. Context never silently changes model odds.
Run --offline for deterministic rebuilds; --cache-dir selects historical summary cache.
"""
import argparse, collections, concurrent.futures, datetime as dt, json, os, pathlib, re, urllib.request
from zoneinfo import ZoneInfo
from coach_changes import confirmed_change
ROOT=pathlib.Path(__file__).resolve().parents[1]
COACH_EVENTS=json.loads((ROOT/'coach-change-events.json').read_text())['events']
DIST=pathlib.Path(os.environ.get('DART_DATA_ROOT',str(ROOT/'dist' if (ROOT/'dist').is_dir() else ROOT)))
BASE='https://site.api.espn.com/apis/site/v2/sports/football/college-football/'

def stamp(): return dt.datetime.now(dt.timezone.utc).isoformat()
def date(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def result(g,t):return g['hs']-g['as'] if g['home']==t else g['as']-g['hs']
def source(url,label='Game summary',observed=None):return {'label':label,'url':url,'observedAt':observed}
def item(title,text,url=None,observed=None,**extra):return dict(title=title,text=text,sourceUrl=url,observedAt=observed,**extra)
def section(summary,items,sources=None,status=None):return dict(status=status or ('available' if items else 'unverified'),summary=summary,items=items,sources=sources or [],modelUse='contextOnly')
def record(rows,t):
 n=len(rows); w=sum(result(g,t)>0 for g in rows); ties=sum(result(g,t)==0 for g in rows)
 return {'games':n,'wins':w,'losses':n-w-ties,'ties':ties,'pointsFor':round(sum(g['hs'] if g['home']==t else g['as'] for g in rows)/n,1) if n else None,'pointsAgainst':round(sum(g['as'] if g['home']==t else g['hs'] for g in rows)/n,1) if n else None,'gameIds':[g['id'] for g in rows]}
def record_text(r):return f"{r['wins']}–{r['losses']} across {r['games']} games; {r['pointsFor']} scored / {r['pointsAgainst']} allowed per game" if r['games'] else 'No qualifying games in the loaded history'
def night(g):return date(g['date']).astimezone(ZoneInfo('America/New_York')).hour>=19

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--offline',action='store_true');ap.add_argument('--data-file',default=None);ap.add_argument('--cache-dir',default=os.environ.get('DART_HISTORY_CACHE',str(ROOT/'.cache')));args=ap.parse_args()
 cache=pathlib.Path(args.cache_dir);fresh=ROOT/'.context-cache';fresh.mkdir(exist_ok=True)
 read=lambda f:json.loads((DIST/f).read_text())
 D,H,M,R=read(args.data_file or ('current-data.json' if (DIST/'current-data.json').exists() else 'data.json')),read('history.json'),read('model.json'),read('research-notes.json')
 G={g['id']:g for g in D['games']}; teams=D['teams']; now=stamp();errors=[]
 def get(kind,tid):
  url=BASE+(f'summary?event={tid}' if kind=='summary' else f'teams/{tid}/roster?season=2026')
  p=fresh/f'{kind}-{tid}.json'
  if not args.offline:
   try:
    req=urllib.request.Request(url,headers={'User-Agent':'DART-Model/1.0 (public college football context)'})
    x=json.load(urllib.request.urlopen(req,timeout=18));p.write_text(json.dumps({'retrievedAt':stamp(),'data':x}));return tid,x,now
   except Exception as e:errors.append({'resource':url,'error':type(e).__name__})
  if p.exists():
   z=json.loads(p.read_text());return tid,z['data'],z['retrievedAt']
  old=cache/(f'summary-{tid}.json' if kind=='summary' else f'roster-{tid}-2026.json')
  if old.exists():return tid,json.loads(old.read_text()),D['retrievedAt']
  return tid,{},None
 ids=sorted({t for f in M['forecasts'] for t in [G[f['id']]['home'],G[f['id']]['away']]})
 with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
  rosters={t:(x,ts) for t,x,ts in ex.map(lambda t:get('roster',t),ids)}
  upcoming={t:(x,ts) for t,x,ts in ex.map(lambda t:get('summary',t),[f['id'] for f in M['forecasts']])}
 # Cached completed games are historical inputs; no future summaries enter these aggregates.
 historical={};published_history=read('context-history-inputs.json') if (DIST/'context-history-inputs.json').exists() else {};by_team=collections.defaultdict(list)
 history_games={g['id']:g for g in H['games']}
 for g in D['games']:
  if g.get('done'):history_games[g['id']]=g
 for g in history_games.values():
  if g['date'][:10]>D['asOf']:continue
  for t in [g['home'],g['away']]:by_team[t].append(g)
 for rows in by_team.values():rows.sort(key=lambda g:g['date'])
 def summary(g):
  if g['id'] not in historical:
   p=ROOT/'.current-cache'/f"summary-{g['id']}.json"
   if p.exists():historical[g['id']]=json.loads(p.read_text())['data']
   else:
    p=cache/f"summary-{g['id']}.json";historical[g['id']]=json.loads(p.read_text()) if p.exists() else published_history.get(g['id'],{})
  return historical[g['id']]
 out={}
 for f in M['forecasts']:
  g=G[f['id']];x,live_at=upcoming[g['id']];sects={};team_out={};qb_items=[];inj_items=[];special=[];situ=[];coach_items=[]
  for side in ['away','home']:
   t=g[side];name=teams[t]['name'];opp=g['home' if side=='away' else 'away'];rows=[r for r in by_team[t] if r['date'][:10]<g['date'][:10]];season=[r for r in rows if r['season']==g['season']]
   home=[r for r in rows if r['home']==t and not r['neutral']];road=[r for r in rows if r['away']==t and not r['neutral']]
   afterw=[];afterl=[]
   for a,b in zip(rows,rows[1:]):
    if a['season']==b['season']:
     if result(a,t)>0:afterw.append(b)
     elif result(a,t)<0:afterl.append(b)
   splits={'home':record(home,t),'road':record(road,t),'nightET':record([r for r in rows if night(r)],t),'afterWin':record(afterw,t),'afterLoss':record(afterl,t),'homeVsRanked':None,'homeVsRankedAtNight':None}
   ranked_home=[];rank_sources=[];rank_covered=0
   for old in home:
    sx=summary(old);comp=sx.get('header',{}).get('competitions',[{}])[0];opponent=old['away']
    opponent_header=next((c for c in comp.get('competitors',[]) if str(c.get('id'))==opponent),None)
    if opponent_header is None:continue
    rank_covered+=1;rank=opponent_header.get('rank',opponent_header.get('curatedRank',{}).get('current'))
    if isinstance(rank,(int,float)) and 1<=rank<=25:
     ranked_home.append(old);rank_sources.append(dict(gameId=old['id'],opponent=opponent,rank=rank,url=old['url'],date=old['date']))
   splits['homeVsRanked']=record(ranked_home,t) if rank_covered else None
   splits['homeVsRankedAtNight']=record([r for r in ranked_home if night(r)],t) if rank_covered else None
   rank_note=f'ESPN event-header rank 1–25, not current roster rank. Game-summary coverage: {rank_covered}/{len(home)} loaded home games; unreported ranks do not establish an unranked opponent.'
   team_out[side]={'id':t,'name':name,'splits':splits,'historyThrough':D['asOf'],'rankedCoverage':rank_note,'rankedSources':rank_sources}
   for key,label in [('homeVsRanked','At home vs reported top25'),('homeVsRankedAtNight','At home vs reported top25 at night')]:
    if splits[key] is not None:situ.append(item(name+' · '+label,record_text(splits[key])+'. '+rank_note,rank_sources[-1]['url'] if rank_sources else f'https://www.espn.com/college-football/team/schedule/_/id/{t}',D['retrievedAt'],sources=[source(r['url'],'Event-header ranking '+str(r['rank']),D['retrievedAt']) for r in rank_sources]))
   for label,key in [('At home','home'),('On the road','road'),('Night kickoffs (7 p.m. ET or later)','nightET'),('After a win','afterWin'),('After a loss','afterLoss')]:situ.append(item(name+' · '+label,record_text(splits[key])+'. Loaded 2016–2026 history through '+D['asOf']+'.',f'https://www.espn.com/college-football/team/schedule/_/id/{t}',D['retrievedAt']))
   if season:
    last=season[-1];days=(date(g['date']).date()-date(last['date']).date()).days;situ.append(item(name+' · previous result / rest',f"{'Won' if result(last,t)>0 else 'Lost' if result(last,t)<0 else 'Tied'} by {abs(result(last,t)):g} against {teams.get(last['away'] if last['home']==t else last['home'],{}).get('name','opponent')} on {last['date'][:10]}; {days} calendar days between games.",last['url'],D['retrievedAt']))
   future=sorted([r for r in D['games'] if t in [r['home'],r['away']] and r['date']>g['date']],key=lambda r:r['date'])
   if future:
    nxt=future[0];on=nxt['away'] if nxt['home']==t else nxt['home'];situ.append(item(name+' · next on the schedule',f"{teams[on]['name']} on {nxt['date'][:10]}. This identifies schedule context, not proof a team is distracted.",nxt['url'],D['retrievedAt']))
   roster,rost_at=rosters[t]; athletes={str(a['id']):a for group in roster.get('athletes',[]) for a in group.get('items',[])}
   coaches=roster.get('coach',[]);coach_names=[' '.join([a.get('firstName',''),a.get('lastName','')]).strip() for a in coaches]
   change=confirmed_change(t,g['season'],D['asOf'],COACH_EVENTS)
   if change:coach_items.append(item(name+' · current coach',change['interimCoach']+' — interim head coach, announced '+change['date']+'. The school announcement takes priority over an older roster listing of '+change['outgoingCoach']+'.',change['sourceUrl'],change['verifiedAt']))
   elif coach_names:coach_items.append(item(name+' · current coach',', '.join(coach_names)+'. Coach-versus-opponent records require a dated tenure history; no unbeaten claim is inferred.',f'https://www.espn.com/college-football/team/roster/_/id/{t}',rost_at))
   for a in athletes.values():
    for injury in a.get('injuries',[]):
     status=injury.get('status') or injury.get('type',{}).get('description') or 'Status unspecified';details=injury.get('details',{});pos=a.get('position',{}).get('displayName','Position unspecified')
     inj_items.append(item(name+' · '+a.get('displayName','Player')+' · '+pos,str(status)+'. '+str(details.get('detail',''))+' Roster injury entry; not a confirmed game-specific starter absence.',f'https://www.espn.com/college-football/team/roster/_/id/{t}',rost_at,position=pos,team=t))
   for r in R.get('injuries',[]):
    if r['team']==t:
     inj_items.append(item(name+' · '+r['player']+' · '+r['position'],r['status']+'. '+r['text']+' Report dated '+r['reportDate']+'; older report, latest game availability must be reconfirmed.',r['sources'][0]['url'],r['reportDate'],position=r['position'],team=t,sources=r['sources'],stale=True))
   passers=collections.defaultdict(list);fgm=fga=xpm=xpa=punts=punt_yards=0;st_games=0;st_sources=[]
   for old in season:
    sx=summary(old)
    for bx in sx.get('boxscore',{}).get('players',[]):
     if bx.get('team',{}).get('id')!=t:continue
     had_st=False
     for stat in bx.get('statistics',[]):
      labels=stat.get('labels',[]);tot=dict(zip(labels,stat.get('totals',[])))
      if stat.get('name')=='passing':
       for a in stat.get('athletes',[]):
        aid=str(a.get('athlete',{}).get('id',''));vals=dict(zip(labels,a.get('stats',[])))
        try:att=int(vals.get('C/ATT','0/0').split('/')[-1])
        except ValueError:att=0
        if att>0:passers[aid].append({'game':old,'name':a.get('athlete',{}).get('displayName','Unknown passer'),'attempts':att,'explicitStart':a.get('starter') is True})
      if stat.get('name')=='kicking' and 'FG' in tot:
       try:
        fm,fa=map(int,tot['FG'].split('/'));xm,xa=map(int,tot.get('XP','0/0').split('/'));fgm+=fm;fga+=fa;xpm+=xm;xpa+=xa;had_st=True
       except ValueError:pass
      if stat.get('name')=='punting' and 'NO' in tot:
       try:punts+=int(tot['NO']);punt_yards+=int(tot.get('YDS',0));had_st=True
       except ValueError:pass
     if had_st:st_games+=1;st_sources.append(old['url'])
   candidates=sorted(passers.items(),key=lambda z:sum(v['attempts'] for v in z[1]),reverse=True)[:2]
   for aid,ps in candidates:
    a=athletes.get(aid,{});cl=a.get('experience',{}).get('displayValue','Class not verified');away_ps=[p for p in ps if p['game']['away']==t and not p['game']['neutral']];starts=sum(p['explicitStart'] for p in ps)
    qb_items.append(item(name+' · '+ps[-1]['name'],f"{cl}. {len(ps)} games with recorded pass attempts this season ({len(away_ps)} on the road); {sum(v['attempts'] for v in ps)} attempts in loaded box scores. "+(f'{starts} explicit starter flags. ' if starts else 'Box scores do not verify career starts. ')+"This is observed usage, not confirmation of this game's starter or a hostile-environment penalty.",ps[-1]['game']['url'],D['retrievedAt'],team=t,athleteId=aid,appearances=len(ps),roadAppearances=len(away_ps),classYear=cl,starterConfirmed=False,rosterObservedAt=rost_at,sources=[source(v['game']['url'],'Passing box score',D['retrievedAt']) for v in ps]+[source(f'https://www.espn.com/college-football/team/roster/_/id/{t}','Roster class',rost_at)]))
   if not candidates:qb_items.append(item(name+' · quarterback', 'No pregame QB usage record in the loaded box scores. Current starter and career-start count require a team announcement.',f'https://www.espn.com/college-football/team/roster/_/id/{t}',rost_at))
   special.append(item(name+' · kicking and punting',f"{fgm}/{fga} field goals; {xpm}/{xpa} extra points; "+(f'{punt_yards/punts:.1f} gross yards per punt over {punts} punts' if punts else 'punting sample unavailable')+f'. Coverage: {st_games} of {len(season)} season games through {D["asOf"]}. Gross punting is not net field-position value.',st_sources[-1] if st_sources else g['url'],D['retrievedAt'],team=t,fieldGoalsMade=fgm,fieldGoalsAttempted=fga,coverageGames=st_games,sources=[source(u,'Special teams box score',D['retrievedAt']) for u in st_sources]))
  series=[r for r in by_team[g['home']] if g['away'] in [r['home'],r['away']] and r['date'][:10]<g['date'][:10]]
  venue=[r for r in series if re.sub(r'[^a-z0-9]','',r['venue'].lower())==re.sub(r'[^a-z0-9]','',g['venue'].lower())]
  hist_items=[item('At '+g['venue'],teams[g['home']]['name']+': '+record_text(record(venue,g['home']))+'. Venue-name matching only; renamed stadiums may be missed.',g['url'],D['retrievedAt'])]
  if series:
   last=series[-1];hist_items.append(item('Last meeting',f"{last['date'][:10]}: {teams[g['home']]['name']} {last['hs'] if last['home']==g['home'] else last['as']:g}, {teams[g['away']]['name']} {last['as'] if last['away']==g['away'] else last['hs']:g}. A prior loss is context, not evidence of extra motivation.",last['url'],D['retrievedAt']))
  else:hist_items.append(item('Series coverage','No prior meeting found in loaded 2016–2026 results. This does not prove the schools have never met.',g['url'],D['retrievedAt']))
  sects['injuries']=section('Reported availability and offensive/defensive line watch. Absence of an entry does not mean a healthy roster.',inj_items,[source(f'https://www.espn.com/college-football/team/roster/_/id/{g[s]}','Roster availability',rosters[g[s]][1]) for s in ['home','away']],status='partial' if inj_items else 'unverified')
  sects['qb']=section('Observed QB experience, with starter confirmation kept separate.',qb_items,status='partial')
  sects['situations']=section('Home/road scoring, prior-result splits, rest and the next opponent. Night means kickoff at or after 7 p.m. Eastern. Ranked splits use top25 ranks reported on dated ESPN game headers and show source coverage.',situ,status='partial')
  sects['stadium']=section('Actual series results in the loaded history.',hist_items,status='available')
  sects['coaching']=section('Current coaching identity and historical matchup context. Motivation is not inferred from rivalry labels.',coach_items,status='partial')
  sects['specialTeams']=section('Kicking and punting from completed-game box scores.',special,status='partial')
  out[g['id']]={'id':g['id'],'asOf':now,'statisticsThrough':D['asOf'],'matchupDate':g['date'],'liveSourceRetrievedAt':live_at,'sections':sects,'teams':team_out,'modelUse':'contextOnly'}
 payload={'generatedAt':now,'snapshotAsOf':D['asOf'],'methodology':'Descriptive matchup context. Historical aggregates stop at saved statistics cutoff and before matchup date. Roster/news observations are current snapshots, not reconstructed pregame facts. Passing appearances do not establish starts. No automatic point or probability adjustment.','games':out,'fetchFailures':errors}
 # Retain only public boxscore facts needed for unattended rebuilds; never depend on a local raw-cache path.
 for gid,sx in historical.items():
  if not sx:continue
  h=sx.get('header',{});cs=h.get('competitions',[{}])[0];players=[]
  for b in sx.get('boxscore',{}).get('players',[]):
   stats=[]
   for st in b.get('statistics',[]):
    if st.get('name') not in ['passing','kicking','punting']:continue
    stats.append({'name':st['name'],'labels':st.get('labels',[]),'totals':st.get('totals',[]),'athletes':[{'athlete':{'id':a.get('athlete',{}).get('id'),'displayName':a.get('athlete',{}).get('displayName')},'stats':a.get('stats',[]),**({'starter':a['starter']} if 'starter' in a else {})} for a in st.get('athletes',[])]})
   players.append({'team':{'id':b.get('team',{}).get('id')},'statistics':stats})
  published_history[gid]={'header':{'id':h.get('id',gid),'competitions':[{'date':cs.get('date'),'competitors':[{'id':z.get('id'),**({'rank':z['rank']} if 'rank' in z else {}),**({'curatedRank':z['curatedRank']} if 'curatedRank' in z else {})} for z in cs.get('competitors',[])]}]},'boxscore':{'players':players}}
 (DIST/'context-history-inputs.json').write_text(json.dumps(published_history,separators=(',',':')))
 (DIST/'matchup-context.json').write_text(json.dumps(payload,separators=(',',':')))
 print(json.dumps({'games':len(out),'injuryGames':sum(bool(x['sections']['injuries']['items']) for x in out.values()),'fetchFailures':len(errors)}))
if __name__=='__main__':main()
