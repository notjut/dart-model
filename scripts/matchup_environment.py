"""Refresh matchup weather, approximate travel and identified coaching context.
Public sources only. These are descriptive evidence, never invented point bonuses.
"""
import concurrent.futures as cf, datetime as dt, hashlib, json, math, os, pathlib, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
from coach_changes import confirmed_change
R=pathlib.Path(__file__).resolve().parents[1]
COACH_EVENTS=json.loads((R/'coach-change-events.json').read_text())['events']
DATA=pathlib.Path(os.environ.get('DART_DATA_ROOT', str(R/'dist' if (R/'dist').exists() else R)))
C=R/'.environment-cache';C.mkdir(exist_ok=True)
LEGACY=pathlib.Path(os.environ.get('DART_HISTORY_CACHE','/workspace/sites/saturday-edge/.cache'))
NOW=dt.datetime.now(dt.timezone.utc);STAMP=NOW.isoformat()
BASE='https://site.api.espn.com/apis/site/v2/sports/football/college-football/'
D=json.loads((DATA/'data.json').read_text());M=json.loads((DATA/'model.json').read_text());G={g['id']:g for g in D['games']};TARGET=[G[f['id']] for f in M['forecasts']]
def get(url,ttl=3600):
 # Reuse this refresh run's verified ESPN responses across collectors.
 if '/roster?' in url:
  team=url.split('/teams/')[1].split('/')[0]; shared=R/'.context-cache'/f'roster-{team}.json'
  if shared.exists():
   try:
    cached=json.loads(shared.read_text()); observed=cached['retrievedAt']
    if NOW.timestamp()-dt.datetime.fromisoformat(observed).timestamp()<ttl:
     return {'url':url,'observedAt':observed,'data':cached['data']}
   except (ValueError,KeyError,OSError):pass
 p=C/(hashlib.sha256(url.encode()).hexdigest()+'.json')
 if p.exists() and NOW.timestamp()-p.stat().st_mtime<ttl:
  try:return json.loads(p.read_text())
  except (ValueError,OSError):pass
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'DART football research/1.0'})
  with urllib.request.urlopen(req,timeout=18) as resp:data=json.load(resp)
  result={'url':url,'observedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'data':data}
  p.write_text(json.dumps(result));return result
 except Exception as e:return {'url':url,'observedAt':STAMP,'data':{},'error':type(e).__name__}
def parallel(fn,seq):
 with cf.ThreadPoolExecutor(max_workers=12) as pool:return dict(pool.map(fn,seq))
def item(title,text,url,observed=STAMP):return dict(title=title,text=text,sourceUrl=url,observedAt=observed)
def section(status,summary,items):return dict(status=status,summary=summary,items=items,sources=[{'label':i['title'],'url':i['sourceUrl'],'observedAt':i['observedAt']} for i in items],contextOnly=True)
def date(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def citykey(v):
 a=v.get('address',{});return (a.get('city',''),a.get('state',''),a.get('country','USA'))
def geocode(k):
 city,state,country=k
 if not city or not state or country not in ['USA','United States','US']:return k,None
 u='https://geocoding-api.open-meteo.com/v1/search?'+urllib.parse.urlencode({'name':f'{city}, {state}','count':20,'countryCode':'US','language':'en','format':'json'})
 r=get(u,30*86400);results=r['data'].get('results',[])
 # Require exact city name and US result; state qualifier is enforced by API.
 exact=[v for v in results if v.get('country_code')=='US' and v.get('name','').casefold()==city.casefold()]
 if not exact:return k,None
 v=max(exact,key=lambda v:v.get('population',0));return k,dict(v,sourceUrl=u,observedAt=r['observedAt'])
def miles(a,b):
 lat1,lat2=map(math.radians,[a['latitude'],b['latitude']]);dl=math.radians(b['longitude']-a['longitude']);da=lat2-lat1
 return 3958.8*2*math.asin(min(1,math.sqrt(math.sin(da/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dl/2)**2)))
def main():
 print('Loading current game environments',flush=True)
 summaries=parallel(lambda g:(g['id'],get(BASE+'summary?event='+g['id'])),TARGET)
 for g in TARGET:
  competition=(summaries[g['id']]['data'].get('header',{}).get('competitions') or [{}])[0]
  if competition.get('date'):g['date']=competition['date']
  if 'timeValid' in competition:g['timeValid']=competition['timeValid']
 tids=sorted({g[s] for g in TARGET for s in ['home','away']})
 origins={}
 for t in tids:
  p=LEGACY/f'schedule-{t}-{NOW.year}.json'
  sched=json.loads(p.read_text()) if p.exists() else get(BASE+f'teams/{t}/schedule?season={NOW.year}')['data']
  if 'data' in sched:sched=sched['data']
  home=[]
  for e in sched.get('events',[]):
   for c in e.get('competitions',[]):
    if not c.get('neutralSite') and any(z.get('id')==t and z.get('homeAway')=='home' for z in c.get('competitors',[])) and c.get('venue',{}).get('address'):home.append(c['venue'])
  if home:
   from collections import Counter
   most=Counter(v.get('fullName','') for v in home).most_common(1)[0][0];origins[t]=next(v for v in home if v.get('fullName')==most)
 venues={gid:r['data'].get('gameInfo',{}).get('venue',{}) for gid,r in summaries.items()}
 keys=set(citykey(v) for v in list(venues.values())+list(origins.values()));geo=parallel(geocode,keys)
 print('Geocoded',sum(v is not None for v in geo.values()),'of',len(keys),'cities',flush=True)
 venue_ids={v['id'] for v in venues.values() if v.get('id')}
 roofs=parallel(lambda vid:(vid,get('https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/venues/'+vid,7*86400)),venue_ids)
 coaches=parallel(lambda t:(t,get(BASE+f'teams/{t}/roster?season={NOW.year}',6*3600)),tids)
 # One weather call per city, not per game. Keep UTC timestamps to avoid DST ambiguity.
 def wx(k):
  v=geo[k]
  if not v:return k,None
  q={'latitude':v['latitude'],'longitude':v['longitude'],'hourly':'temperature_2m,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m','temperature_unit':'fahrenheit','wind_speed_unit':'mph','precipitation_unit':'inch','timezone':'UTC','forecast_days':16}
  return k,get('https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode(q),3600)
 futurekeys={citykey(venues[g['id']]) for g in TARGET if date(g['date'])>NOW and date(g['date'])<NOW+dt.timedelta(days=16)}
 weather=parallel(wx,futurekeys);out={}
 for g in TARGET:
  gid=g['id'];r=summaries[gid];v=venues[gid];loc=geo.get(citykey(v));kick=date(g['date']);source=g['url'];roof=roofs.get(v.get('id'),{}).get('data',{}).get('indoor');witems=[];vals={};travelmetrics={};coachmetrics={}
  if v.get('fullName'):witems.append(item(v['fullName'],f"Venue city: {', '.join(citykey(v)[:2])}. "+('ESPN identifies an indoor venue; game-day roof configuration is not independently verified.' if roof is True else 'ESPN identifies an outdoor venue.' if roof is False else 'Roof status not verified.'),r['url'],r['observedAt']))
  forecast=weather.get(citykey(v));wd=forecast['data'] if forecast else {};hour=wd.get('hourly',{});times=hour.get('time',[])
  if roof is True:ws='indoor';summary='Indoor-designated venue; roof configuration unverified, so outdoor weather is not treated as on-field conditions.'
  elif kick<=NOW:ws='past-game';summary='Kickoff has passed; no current weather is presented as a pregame forecast.'
  elif not g.get('timeValid',False):ws='unverified';summary='Kickoff time is unconfirmed; hourly weather withheld.'
  elif times:
   stamps=[date(t+'+00:00') for t in times];idx=min(range(len(stamps)),key=lambda i:abs((stamps[i]-kick).total_seconds()))
   if abs((stamps[idx]-kick).total_seconds())<=3600:
    fields=[('temperature_2m','temperature'),('wind_speed_10m','wind'),('wind_gusts_10m','gusts'),('precipitation_probability','rain/snow chance'),('precipitation','hourly precipitation')];vals={k:hour[k][idx] for k,_ in fields if k in hour and hour[k][idx] is not None};units=wd.get('hourly_units',{})
    txt=', '.join(f'{label} {vals[k]} {units.get(k,"")}' for k,label in fields if k in vals)
    witems.append(item('Kickoff-area forecast',txt+'. Forecast hour '+stamps[idx].isoformat()+'. City-center grid, not a stadium sensor.',forecast['url'],forecast['observedAt']))
    risk=[]
    if vals.get('wind_speed_10m',0)>=15 or vals.get('wind_gusts_10m',0)>=25:risk.append('Wind warrants checking deep passing and kicking conditions')
    if vals.get('precipitation_probability',0)>=60:risk.append('Elevated precipitation probability warrants checking ball security and footing')
    if risk:witems.append(item('Weather watch', '; '.join(risk)+'. These screening thresholds do not change the score prediction.',forecast['url'],forecast['observedAt']))
    ws='forecast';summary='Hourly weather matched to kickoff; refresh before using it.'
   else:ws='outside-window';summary='Kickoff falls outside the available forecast hours.'
  else:ws='unavailable';summary='No verified hourly forecast returned for this venue city.'
  travels=[]
  for side in ['away','home']:
   tid=g[side];name=D['teams'][tid]['name'];origin=geo.get(citykey(origins.get(tid,{})))
   if not origin or not loc:travels.append(item(name+' travel','Distance unavailable: origin or destination city could not be matched unambiguously.',source));continue
   distance=round(miles(origin,loc));travelmetrics[side]={'teamId':tid,'straightLineMiles':distance,'originCity':origin['name'],'venueCity':loc['name'],'originSourceUrl':origin['sourceUrl'],'originObservedAt':origin['observedAt'],'destinationSourceUrl':loc['sourceUrl'],'approximate':True};txt=f'Approximately {distance:,} straight-line miles from {origin["name"]} to {loc["name"]}; city-center estimate, not actual travel distance.'
   if origin.get('timezone') and loc.get('timezone'):
    oz=kick.astimezone(ZoneInfo(origin['timezone']));vz=kick.astimezone(ZoneInfo(loc['timezone']));shift=(vz.utcoffset()-oz.utcoffset()).total_seconds()/3600
    travelmetrics[side].update({'originTimezone':origin['timezone'],'venueTimezone':loc['timezone'],'timezoneShiftHours':shift,'kickoffHomeTime':oz.isoformat(),'kickoffVenueTime':vz.isoformat()})
    txt+=f' Kickoff is {oz.strftime("%I:%M %p %Z").lstrip("0")} in the team’s home time zone and {vz.strftime("%I:%M %p %Z").lstrip("0")} at the venue; clock difference {shift:+g} hours.'
   txt+=' Arrival date, flight routing and acclimation are not verified.'
   travels.append(item(name+' travel',txt,loc['sourceUrl'],loc['observedAt']))
  coaching=[]
  for side in ['away','home']:
   tid=g[side];name=D['teams'][tid]['name'];cr=coaches[tid];cs=cr['data'].get('coach',[])
   if isinstance(cs,dict):cs=[cs]
   names=[' '.join(filter(None,[c.get('firstName'),c.get('lastName')])) for c in cs]
   names=[n for n in names if n];coachmetrics[side]={'teamId':tid,'names':names,'ids':[c.get('id') for c in cs if c.get('id')]}
   change=confirmed_change(tid,g['season'],D['asOf'],COACH_EVENTS)
   if change:
    coachmetrics[side]={'teamId':tid,'names':[change['interimCoach']],'ids':[],'announcementDate':change['date'],'sourceUrl':change['sourceUrl']}
    coaching.append(item(name+' coaching','School-announced interim coach: '+change['interimCoach']+' ('+change['date']+'). This replaces the previous coach identity; no automatic motivation bonus is assigned.',change['sourceUrl'],change['verifiedAt']))
   else:coaching.append(item(name+' coaching',('Roster-listed coach: '+', '.join(names)+'. ' if names else 'No coach identity returned by the current roster source. ')+'Coach-versus-school records and claimed motivational advantages require dated coaching history; no bonus is assigned.',cr['url'],cr['observedAt']))
  out[gid]={'id':gid,'sections':{'weather':section(ws,summary,witems),'travel':section('calculated' if loc else 'partial','Approximate distance and body-clock time, not evidence of fatigue.',travels),'coaching':section('identified' if any(v['names'] for v in coachmetrics.values()) else 'unavailable','Current identities; no unsupported coaching or motivation bonus.',coaching)}}
  out[gid]['sections']['weather']['metrics']={'indoorDesignated':roof,'hourly':vals,'units':wd.get('hourly_units',{}) if vals else {},'kickoff':g['date']}
  out[gid]['sections']['travel']['metrics']=travelmetrics
  out[gid]['sections']['coaching']['metrics']=coachmetrics
  for tm in travelmetrics.values():
   out[gid]['sections']['travel']['sources'].append({'label':tm['originCity']+' origin location','url':tm['originSourceUrl'],'observedAt':tm['originObservedAt']})
 payload={'generatedAt':STAMP,'games':out,'coverage':{'games':len(out),'weatherForecasts':sum(x['sections']['weather']['status']=='forecast' for x in out.values()),'travelCalculated':sum(x['sections']['travel']['status']=='calculated' for x in out.values()),'coachesIdentified':sum(x['sections']['coaching']['status']=='identified' for x in out.values())},'methodology':{'numericalImpact':'Context only; not fitted as a score adjustment.','travel':'Haversine city-center distance from most frequent non-neutral home venue in team schedule. Not route mileage or itinerary.','weather':'Open-Meteo hourly forecast for geocoded venue city; nearest UTC hour within 60 minutes. Future confirmed kickoffs only. Units supplied by API.','coaches':'Dated school coaching announcements where verified, otherwise current ESPN roster identities. Firing history is a verified sample, not proof of a coaching advantage.','sources':['https://open-meteo.com/en/docs','https://open-meteo.com/en/docs/geocoding-api']}}
 (DATA/'matchup-environment.json').write_text(json.dumps(payload,separators=(',',':')));print(json.dumps(payload['coverage']),flush=True)
if __name__=='__main__':main()
