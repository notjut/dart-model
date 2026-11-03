import json,pathlib,datetime,math,collections,os,numpy as np
from scipy.special import ndtr
R=pathlib.Path(__file__).resolve().parents[1];DATA=pathlib.Path(os.environ.get('DART_MODEL_INPUT',str(R/'dist/data.json')));OUTPUT=pathlib.Path(os.environ.get('DART_MODEL_OUTPUT',str(R/'dist/model.json')));d=json.loads(DATA.read_text());season_year=int(d['asOf'][:4]);games=sorted(d['games'],key=lambda g:(g['date'],g['id']));teams=d['teams'];history=collections.defaultdict(list);elo=collections.defaultdict(lambda:1500.);records=[];live=[];lastseason=None
names=['Elo difference','Net success-rate difference','Scoring margin difference','Scoring environment','Home field','Home/road scoring residual','Explosive-rate difference','Yards/game difference','Rest difference','Post-big-win difference','Look-ahead difference','Evening residual difference','Recent series residual']
if os.environ.get('DART_CONTEXT_CANDIDATE')=='1':names += ['Home/road offensive scoring difference','Home/road defensive scoring difference','After-win/loss scoring residual difference']
core=[0,1,2,3,4,6,7]+([13,14,15] if os.environ.get('DART_CONTEXT_CANDIDATE')=='1' else []);context=[5,8,9,10,11,12]
coach_path=DATA.parent/'coach-change-history.json'
coach_rows=json.loads(coach_path.read_text()).get('rows',[]) if coach_path.exists() else []
coach_games=collections.defaultdict(set)
for r in coach_rows:
 if r['changeType']=='dismissal':coach_games[r['gameId']].add(r['team'])
coach_idx=core+[16]
def avg(v,default=0):return sum(v)/len(v) if v else default
def profile(t,before):
 hs=[r for r in history[t] if r['date'][:10]<before[:10]];recent=hs[-12:];season=[r for r in hs if r['season']==int(before[:4])];p=sum(r['plays'] for r in season);dp=sum(r['dplays'] for r in season)
 sr=(sum(r['success'] for r in season)+40*.42)/(p+40);dsr=(sum(r['dsuccess'] for r in season)+40*.42)/(dp+40)
 def split(rows):return {'n':len(rows),'ppg':round(avg([r['pf'] for r in rows]),1) if rows else None,'allowed':round(avg([r['pa'] for r in rows]),1) if rows else None,'wins':sum(r['pf']>r['pa'] for r in rows)}
 home=[r for r in recent if r['loc']=='home'];away=[r for r in recent if r['loc']=='away'];night=[r for r in recent if r['night']];after=[r for r in season if r['afterBig']]
 return {'n':len(recent),'pf':avg([r['pf'] for r in recent],28),'pa':avg([r['pa'] for r in recent],28),'margin':avg([r['pf']-r['pa'] for r in recent]),'sr':sr,'dsr':dsr,'net':sr-dsr,'plays':p,'dplays':dp,'exp':(sum(r['explosive'] for r in season)+40*.07)/(p+40),'yards':avg([r['yards'] for r in season if r['yards'] is not None],370),'homeResid':sum(r['residual'] for r in home)/(len(home)+8),'awayResid':sum(r['residual'] for r in away)/(len(away)+8),'nightResid':sum(r['residual'] for r in night)/(len(night)+12),'last':hs[-1] if hs else None,'record':split(season),'home':split([r for r in season if r['loc']=='home']),'away':split([r for r in season if r['loc']=='away']),'night':split([r for r in season if r['night']]),'afterBig':split(after),'elo':elo[t],'homeOff':sum(r['pf']-avg([v['pf'] for v in recent],28) for r in home)/(len(home)+8),'awayOff':sum(r['pf']-avg([v['pf'] for v in recent],28) for r in away)/(len(away)+8),'homeDef':sum(r['pa']-avg([v['pa'] for v in recent],28) for r in home)/(len(home)+8),'awayDef':sum(r['pa']-avg([v['pa'] for v in recent],28) for r in away)/(len(away)+8),'afterResult':sum(r['residual'] for r in recent if hs and r.get('previousWon')==(hs[-1]['pf']>hs[-1]['pa']))/(sum(1 for r in recent if hs and r.get('previousWon')==(hs[-1]['pf']>hs[-1]['pa']))+12)}
def night(g):
 if not g.get('timeValid'):return False
 dt=datetime.datetime.fromisoformat(g['date'].replace('Z','+00:00'))
 from zoneinfo import ZoneInfo
 return dt.astimezone(ZoneInfo('America/New_York')).hour>=19

def features(g):
 h,a=g['home'],g['away'];hp,ap=profile(h,g['date']),profile(a,g['date'])
 def rest(p):return min(21,(datetime.date.fromisoformat(g['date'][:10])-datetime.date.fromisoformat(p['last']['date'][:10])).days) if p['last'] else 7
 def look(t,opp):
  nxt=next((x for x in games if x['date'][:10]>g['date'][:10] and x['season']==g['season'] and t in [x['home'],x['away']]),None)
  if not nxt:return 0
  gap=(datetime.date.fromisoformat(nxt['date'][:10])-datetime.date.fromisoformat(g['date'][:10])).days
  o=nxt['away'] if nxt['home']==t else nxt['home'];return int(gap<=14 and elo[o]>elo[opp]+100)
 past=[r for r in history[h] if r['opp']==a and r['date'][:10]<g['date'][:10]]
 f=[(elo[h]-elo[a])/100,(hp['net']-ap['net'])*100,hp['margin']-ap['margin'],(hp['pf']+hp['pa']+ap['pf']+ap['pa'])/2,int(not g['neutral']),0 if g['neutral'] else hp['homeResid']-ap['awayResid'],100*(hp['exp']-ap['exp']),hp['yards']-ap['yards'],rest(hp)-rest(ap),int(bool(hp['last'] and hp['last']['bigWin']))-int(bool(ap['last'] and ap['last']['bigWin'])),look(h,a)-look(a,h),(hp['nightResid']-ap['nightResid']) if night(g) else 0,sum(r['residual'] for r in past)/(len(past)+16)]
 f += [0 if g['neutral'] else hp['homeOff']-ap['awayOff'],0 if g['neutral'] else hp['homeDef']-ap['awayDef'],hp['afterResult']-ap['afterResult']]
 f.append(int(h in coach_games[g['id']])-int(a in coach_games[g['id']]))
 return f,hp,ap,past

def update(g):
 h,a=g['home'],g['away'];hm=g['hs']-g['as'];expected=(elo[h]-elo[a])/25+(0 if g['neutral'] else 2.5);oldh,olda=elo[h],elo[a]
 prob=1/(1+10**(-((oldh-olda)+(0 if g['neutral'] else 65))/400));delta=24*((1 if hm>0 else 0)-prob);elo[h]+=delta;elo[a]-=delta
 for t,o,pf,pa,oppE in [(h,a,g['hs'],g['as'],olda),(a,h,g['as'],g['hs'],oldh)]:
  s=g.get('stats',{}).get(t,{});ds=g.get('stats',{}).get(o,{});prev=history[t][-1] if history[t] else None
  try:y=float(s.get('yards'))
  except (TypeError,ValueError):y=None
  history[t].append({'date':g['date'],'season':g['season'],'opp':o,'pf':pf,'pa':pa,'loc':'neutral' if g['neutral'] else ('home' if t==h else 'away'),'night':night(g),'plays':s.get('plays',0),'success':s.get('success',0),'dplays':ds.get('plays',0),'dsuccess':ds.get('success',0),'explosive':s.get('explosive',0),'yards':y,'bigWin':pf>pa and oppE>=1600,'previousWon':None if not prev else prev['pf']>prev['pa'],'afterBig':bool(prev and prev['bigWin']),'residual':(pf-pa)-(expected if t==h else -expected)})
# Freeze every prediction date before applying that day's outcomes.
for date,group in __import__('itertools').groupby(games,key=lambda g:g['date'][:10]):
 group=list(group)
 season=group[0]['season']
 if season!=lastseason:
  if lastseason is not None:
   for t in elo:elo[t]=1500+.75*(elo[t]-1500)
  lastseason=season
 if date>d['asOf']:continue
 for g in group:
  if g['done'] and g['season']==season_year:
   f,hp,ap,past=features(g)
   if hp['n']>=3 and ap['n']>=3 and hp['plays']>=80 and ap['plays']>=80:records.append({'g':g,'x':f,'y':[g['hs']-g['as'],g['hs']+g['as']]})
 for g in group:
  if g['done']:update(g)

def fit(rs,idx):
 X=np.array([[r['x'][j] for j in idx] for r in rs]);Y=np.array([r['y'] for r in rs]);mu=X.mean(0);sd=X.std(0);sd[sd<1e-8]=1;Z=np.c_[np.ones(len(X)),(X-mu)/sd];pen=np.eye(Z.shape[1])*30;pen[0,0]=0;b=np.linalg.solve(Z.T@Z+pen,Z.T@Y);err=Y-Z@b;return mu,sd,b,max(10,float(np.std(err[:,0])))
def predict(m,x,idx):
 mu,sd,b,s=m;z=np.r_[1,(np.array(x)[idx]-mu)/sd];return z@b,z[:,None]*b
held=[]
for date,grp in __import__('itertools').groupby(records,key=lambda r:r['g']['date'][:10]):
 prev=[r for r in records if r['g']['date'][:10]<date]
 if len(prev)<100:continue
 cm=fit(prev,core);fm=fit(prev,list(range(len(names))));ccm=fit(prev,coach_idx)
 for r in grp:
  ccp,_=predict(ccm,r['x'],coach_idx);cp,_=predict(cm,r['x'],core);fp,_=predict(fm,r['x'],list(range(len(names))));s=fm[3];p=float(ndtr(fp[0]/s));held.append({'id':r['g']['id'],'date':date,'actual':r['y'],'core':cp.tolist(),'full':fp.tolist(),'prob':p,'sd':s,'coreSd':cm[3],'coachCandidate':ccp.tolist(),'coachSd':ccm[3],'coachChange':bool(coach_games[r['g']['id']])})
if len(records)<100:raise ValueError('Insufficient training data: '+str(len(records)))
full=fit(records,list(range(len(names))));baseline=fit(records,core);coach_fit=fit(records,coach_idx)
forecastSd=max(10,float(np.sqrt(np.mean([(r['full'][0]-r['actual'][0])**2 for r in held])))) if len(held)>=30 else full[3]
# Current-data matchup forecasts for scheduled games only, not retrospective backfilled claims.
cut=d['asOf'];upcoming=[g for g in games if not g['done'] and g['season']==season_year and cut<=g['date'][:10]<=(datetime.date.fromisoformat(cut)+datetime.timedelta(days=14)).isoformat()]
for g in upcoming:
 f,hp,ap,past=features(g)
 if hp['n']<3 or ap['n']<3:continue
 if datetime.datetime.fromisoformat(g['date'].replace('Z','+00:00'))<=datetime.datetime.now(datetime.timezone.utc):continue
 coach_pred,coach_parts=predict(coach_fit,f,coach_idx);pred,parts=predict(full,f,list(range(len(names))));base,coreParts=predict(baseline,f,core);margin=float(pred[0]);total=max(abs(margin)+2,float(pred[1]));s=forecastSd
 live.append({'id':g['id'],'homeScore':round((total+margin)/2),'awayScore':round((total-margin)/2),'margin':margin,'total':total,'homeWin':float(ndtr(margin/s)),'sd':s,'coreMargin':float(base[0]),'coreTotal':float(base[1]),'coreSd':max(10,float(np.sqrt(np.mean([(r['core'][0]-r['actual'][0])**2 for r in held])))) if len(held)>=30 else baseline[3],'coreContributions':[{'name':names[i],'points':round(float(coreParts[j+1,0]),2)} for j,i in enumerate(core)],'coreIntercept':float(coreParts[0,0]),'contributions':[{'name':names[i],'points':round(float(parts[i+1,0]),2)} for i in range(len(names))],'intercept':float(parts[0,0]),'homeProfile':hp,'awayProfile':ap,'series':past,'features':f,'limited':hp['plays']<80 or ap['plays']<80,'coachChangeEvents':[r for r in coach_rows if r['gameId']==g['id']],'coachChangeCandidate':{'active':bool(coach_games[g['id']]),'homeMargin':float(coach_pred[0]),'indicatorContribution':float(coach_parts[-1,0]),'appliedToMain':False}})
 for latest in live[-1:]:
  if latest['homeScore']==latest['awayScore']:
   latest['homeScore' if latest['margin']>=0 else 'awayScore']+=1
def metrics(which):
 errs=[abs(r[which][0]-r['actual'][0]) for r in held];te=[abs(r[which][1]-r['actual'][1]) for r in held];ps=[float(ndtr(r[which][0]/r['coreSd' if which=='core' else 'sd'])) for r in held]
 return {'marginMAE':avg(errs),'totalMAE':avg(te),'accuracy':avg([int((r[which][0]>0)==(r['actual'][0]>0)) for r in held]),'brier':avg([(p-int(r['actual'][0]>0))**2 for p,r in zip(ps,held)]),'coverage80':avg([int(abs(r[which][0]-r['actual'][0])<=1.282*r['coreSd' if which=='core' else 'sd']) for r in held])}
cal=[]
for lo in [0,.2,.4,.6,.8]:
 rows=[r for r in held if lo<=r['prob']<lo+.2+1e-10];cal.append({'band':f'{round(lo*100)}–{round((lo+.2)*100)}%','n':len(rows),'predicted':avg([r['prob'] for r in rows]),'actual':avg([int(r['actual'][0]>0) for r in rows])})
out={'trainedGames':len(records),'testedGames':len(held),'testStart':held[0]['date'] if held else None,'testEnd':held[-1]['date'] if held else None,'core':metrics('core'),'full':metrics('full'),'calibration':cal,'heldout':held,'forecasts':live,'features':names,'sd':full[3],'model':'Standardized ridge regression, penalty 30, expanding-date holdout; margin and total targets. Equal weights. Elo prior from 2025. No market inputs.'}
coach_held=[r for r in held if r['coachChange']]
coach_n=sum(bool(coach_games[r['g']['id']]) for r in records)
out['coachChangeTrial']={'trainingGamesWithChange':coach_n,'testedGamesWithChange':len(coach_held),'baselineMarginMAE':avg([abs(r['core'][0]-r['actual'][0]) for r in coach_held]) if coach_held else None,'candidateMarginMAE':avg([abs(r['coachCandidate'][0]-r['actual'][0]) for r in coach_held]) if coach_held else None,'mainModelApplied':False,'status':'testing','note':'First-game-after-dismissal indicator tested with earlier-game training only. Small, incomplete event sample; not independently validated. No automatic score bonus or main-model promotion.'}
out['asOf']=d['asOf'];out['generatedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();out['inputRetrievedAt']=d.get('retrievedAt');out['inputFile']=DATA.name
OUTPUT.write_text(json.dumps(out,separators=(',',':')));print(json.dumps({k:out[k] for k in ['trainedGames','testedGames','core','full']},indent=2));print('Forecasts',len(live))
