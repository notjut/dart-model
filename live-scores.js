/* Live scoreboard only; never rewrites model forecasts or archived picks. */
(function(root){
'use strict';
const interval=10*60*1000;
function parse(payload){
 if(!payload||!Array.isArray(payload.events))throw Error('Invalid scoreboard');
 return payload.events.flatMap(e=>{const c=e.competitions?.[0],teams=c?.competitors||[],h=teams.find(t=>t.homeAway==='home'),a=teams.find(t=>t.homeAway==='away'),s=c?.status||e.status,t=s?.type;
  if(!h?.team||!a?.team||!t||!Number.isFinite(Date.parse(e.date)))return [];
  const score=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(typeof x==='object'?x.value:x);return Number.isFinite(n)&&n>=0?n:null;};
  return [{id:String(e.id),date:e.date,home:String(h.team.id),away:String(a.team.id),homeName:h.team.displayName,awayName:a.team.displayName,homeAbbr:h.team.abbreviation,awayAbbr:a.team.abbreviation,homeLogo:h.team.logo||h.team.logos?.[0]?.href,awayLogo:a.team.logo||a.team.logos?.[0]?.href,homeScore:t.state==='pre'?null:score(h.score),awayScore:t.state==='pre'?null:score(a.score),state:t.state,status:t.name,detail:t.shortDetail||t.detail||'',done:!!t.completed,timeValid:c.timeValid!==false}];
 });
}
let games=[],retrievedAt=null,failed=false,busy=false,callback=()=>{},timer;
async function refresh(){if(busy)return;busy=true;
 try{const today=GamedayEngine.day(Date.now()),previous=new Date(today+'T12:00Z');previous.setUTCDate(previous.getUTCDate()-1);const dates=[today,previous.toISOString().slice(0,10)];
  const results=await Promise.allSettled(dates.map(async d=>{const ctl=new AbortController(),timeout=setTimeout(()=>ctl.abort(),15000);try{const r=await fetch('https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=80&limit=1000&dates='+d.replaceAll('-',''),{cache:'no-store',signal:ctl.signal});if(!r.ok)throw Error('Scoreboard unavailable');return parse(await r.json());}finally{clearTimeout(timeout);}}));
  const ok=results.filter(r=>r.status==='fulfilled');failed=ok.length!==dates.length;
  if(ok.length){const map=new Map(games.filter(g=>dates.includes(GamedayEngine.day(g.date))).map(g=>[g.id,g]));for(const r of ok)for(const g of r.value)map.set(g.id,g);games=[...map.values()];if(!failed)retrievedAt=Date.now();}
 }catch(e){failed=true;}finally{busy=false;callback();}
}
const api={parse,interval,get games(){return games},get failed(){return failed},get stale(){return failed||!retrievedAt||Date.now()-retrievedAt>interval+60000},get retrievedAt(){return retrievedAt},start(fn){callback=fn;if(timer)return;refresh();timer=setInterval(()=>{if(!document.hidden)refresh();},interval);document.addEventListener('visibilitychange',()=>{if(!document.hidden&&(!retrievedAt||Date.now()-retrievedAt>=interval))refresh();});}};
root.LiveScores=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
