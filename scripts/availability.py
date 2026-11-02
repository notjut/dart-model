"""Refresh official public conference availability reports (no credentials).
The endpoint is the public report transport used by the embedded HD Intelligence
report on each linked conference website. Never call administrative endpoints.
Run after the schedule is refreshed. Match by BOTH teams and date; never carry
last week's injury list into another matchup. Status is availability, not diagnosis.
"""
import concurrent.futures, datetime as dt, json, os, pathlib, re, urllib.request
R=pathlib.Path(__file__).resolve().parents[1]
DATA=pathlib.Path(os.environ.get('DART_DATA_DIR',str(R/'dist' if (R/'dist').is_dir() else R)))
SOURCES={
 'SEC':'https://www.secsports.com/fbreports',
 'ACC':'https://theacc.com/sports/2025/8/28/availability-reporting-football.aspx',
 'B10':'https://bigten.org/sports/2026/9/10/FB_Availability_Reports.aspx',
 'B12':'https://big12sports.com/sports/2025/8/14/FBreporting.aspx',
 'American':'https://theamerican.org/sports/2026/8/6/football_player_availability.aspx'}
API='https://app.hdintelligence.com/api/get-publish-public'
# Season-scoped official bios, checked again on every refresh. These establish
# center experience, not an announced starter for an upcoming game.
CENTER_BIOS=[
 ('Alabama','Racin Delgatty',2026,'https://rolltide.com/sports/football/roster/racin-delgatty/17502','77 snaps at center'),
 ('Michigan','Jake Guarnera',2026,'https://mgoblue.com/sports/football/roster/jake-guarnera/27968','Started at center against Western Michigan')]
def enrich_centers(reports):
 checks=[]
 for team,name,season,url,phrase in CENTER_BIOS:
  checked=dt.datetime.now(dt.timezone.utc).isoformat()
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as response: html=response.read().decode()
   plain=' '.join(re.sub('<[^>]+>',' ',html).split())
   verified=phrase.lower() in plain.lower() and str(season) in plain
   checks.append({'name':name,'url':url,'checkedAt':checked,'verified':verified})
   if not verified:continue
   for r in reports:
    if not r['gameDate'].startswith(str(season)):continue
    for t in r['teams']:
     if norm(t['teamName'])!=norm(team):continue
     for p in t['players']:
      if norm(p['name'])==norm(name):
       p.update({'sourcePosition':p['position'],'unit':'Center','position':'C','roleVerified':True,'roleEvidence':{'summary':'Official season bio documents playing center; upcoming starting role is not confirmed.','url':url,'checkedAt':checked,'season':season}})
  except Exception as e:checks.append({'name':name,'url':url,'checkedAt':checked,'verified':False,'error':type(e).__name__})
 return checks
ALIASES={'pitt':'pittsburgh','uconn':'uconn','miami fl':'miami','ole miss':'ole miss','ucf':'ucf','appalachian state':'app state','miami oh':'miami oh','san jose state':'san jose state'}
def norm(s):
 import unicodedata
 s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
 s=re.sub(r'[^a-z0-9 ]','',s);s=' '.join(s.split());return ALIASES.get(s,s)
def unit(pos):
 if pos in ['C','OC']:return 'Center'
 if pos in ['OL','OT','OG','LT','LG','RG','RT','G','T']:return 'Offensive line'
 if pos in ['DL','DT','DE','NT','EDGE']:return 'Defensive line'
 if pos=='QB':return 'Quarterback'
 return 'Other'
def fetch(conf):
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 try:
  req=urllib.request.Request(API,data=json.dumps({'sport':'Football','organization':conf,'conference':conf}).encode(),headers={'Content-Type':'application/json','User-Agent':'DART research updater'})
  with urllib.request.urlopen(req,timeout=25) as response: payload=json.load(response)
  if not isinstance(payload,dict):raise ValueError('Unexpected report schema')
  return conf,payload,now,None
 except Exception as e:return conf,{},now,type(e).__name__+': '+str(e)
def parse(payload,conf,retrieved,team_map):
 reports=[]
 for rid,r in payload.items():
  if not isinstance(r,dict) or not isinstance(r.get('games'),list):continue
  published=r.get('publishDate');game_date=r.get('footer',{}).get('date')
  if not published or not game_date:continue
  # Retain the provider's timezone, not a fabricated UTC conversion.
  stamp=f"{published} {r.get('postedTime','')} {r.get('conferenceTimeZone','')}".strip()
  teams=[]
  for t in r['games']:
   tid=team_map.get(norm(t.get('teamName',''))) or team_map.get(norm(t.get('teamDisplayName','')))
   if not tid:continue
   rows=[]
   for a in t.get('rows',[]):
    raw=a.get('name','').strip();m=re.match(r'^(\S+)\s+#(\d+)\s+(.+)$',raw)
    pos,num,name=(m.group(1),m.group(2),m.group(3)) if m else ('',None,raw)
    status=a.get('status')
    if not status or not name:continue
    rows.append({'name':name,'position':pos,'number':num,'unit':unit(pos),'status':status,'isConcern':status not in ['Available','Exempt'],'roleVerified':False})
   teams.append({'teamId':tid,'teamName':t.get('teamDisplayName') or t.get('teamName'),'status':'reported','reportDate':published,'reportPublished':stamp,'reportType':r.get('ReportType'),'gameDate':game_date,'retrievedAt':retrieved,'observedAt':stamp,'sourceUrl':SOURCES[conf],'summary':f"{len([p for p in rows if p['isConcern']])} players listed with an availability concern for {game_date}; {len([p for p in rows if p['isConcern'] and p['unit'] in ['Center','Offensive line','Defensive line']])} on the offensive or defensive line.",'players':rows,'concerns':[p for p in rows if p['isConcern']],'sources':[{'label':f'{conf} official availability report','url':SOURCES[conf]},{'label':'Conference report provider','url':f'https://app.hdintelligence.com/?conf={conf}&source={conf}&sport=Football&type=report'}],'note':'Official availability status; injury diagnosis and starting role are not implied. Generic OL listings do not establish who plays center.'})
  if len(teams)==2:
   teams[0]['opponent']=teams[1]['teamId'];teams[1]['opponent']=teams[0]['teamId']
   reports.append({'reportId':str(rid),'conference':conf,'gameDate':game_date,'reportDate':published,'reportPublished':stamp,'teams':teams})
 return reports

def main():
 d=json.loads((DATA/'data.json').read_text());m=json.loads((DATA/'model.json').read_text());byid={g['id']:g for g in d['games']};team_map={norm(v['name']):k for k,v in d['teams'].items()};reports=[];errors=[];checks=[]
 for conf,payload,when,error in concurrent.futures.ThreadPoolExecutor(5).map(fetch,SOURCES):
  parsed=parse(payload,conf,when,team_map);reports.extend(parsed);checks.append({'conference':conf,'retrievedAt':when,'reports':len(parsed),'source':SOURCES[conf],'error':error})
  if error:errors.append({'conference':conf,'error':error})
 role_checks=enrich_centers(reports)
 teams={};games={}
 for report in sorted(reports,key=lambda r:r['reportPublished']):
  for t in report['teams']:teams[t['teamId']]=t
 for f in m['forecasts']:
  g=byid[f['id']];pair={g['home'],g['away']};found=[r for r in reports if {t['teamId'] for t in r['teams']}==pair and r['gameDate']==g['date'][:10]]
  if found:
   report=max(found,key=lambda r:r['reportPublished']);sides={t['teamId']:t for t in report['teams']};games[g['id']]={'status':'reported','gameDate':report['gameDate'],'home':sides[g['home']],'away':sides[g['away']]}
  else:
   games[g['id']]={'status':'not_reported','gameDate':g['date'][:10],'home':None,'away':None,'note':'No matching official report retrieved for these teams on this game date. This does not mean everyone is healthy. Nonconference games and conferences without a connected public report may be absent.'}
 out={'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'source':'Official conference public reports via their embedded report provider','checks':checks,'roleChecks':role_checks,'teams':teams,'games':games,'coverage':{'matchups':len(games),'reportedMatchups':sum(v['status']=='reported' for v in games.values()),'teams':len(teams),'concerns':sum(len(t['concerns']) for t in teams.values()),'centersFlagged':sum(p['unit']=='Center' for t in teams.values() for p in t['concerns'])},'failures':errors,'modelUse':'Context only. No injury point penalty has been fitted; never convert a count of unavailable players into points.'}
 dest=DATA/'availability.json';tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(out,separators=(',',':')));tmp.replace(dest);print(json.dumps(out['coverage']));print(json.dumps(errors))
if __name__=='__main__':main()
