/* Display and ticket rules only. Forecast fitting and weights are unchanged. */
(function(root){
'use strict';
const day=value=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
const half=value=>Number.isFinite(value)?Math.round(value*2)/2:null;
const decimal=odds=>Number.isFinite(odds)&&Math.abs(odds)>=100?(odds>0?1+odds/100:1+100/-odds):null;
const american=value=>value>1?(value>=2?'+'+Math.round((value-1)*100):String(-Math.round(100/(value-1)))):'—';
function dates(rows,now=Date.now()){
 const today=day(now),keys=[...new Set([today,...rows.map(g=>day(g.date))])].sort();
 return keys.filter(k=>k>=today).concat(keys.filter(k=>k<today).reverse());
}
function available(leg,now=Date.now()){
 if(!leg)return false;
 const age=now-Date.parse(leg.quoteAt),start=Date.parse(leg.date);
 return !!leg&&decimal(leg.odds)!==null&&Number.isFinite(start)&&start>now&&Number.isFinite(age)&&age>=0&&age<=72*3600000&&leg.timeValid===true&&!leg.reviewRequired;
}
function conflict(legs,leg){
 if(legs.length>=6)return 'Six legs is the limit.';
 if(legs.some(l=>l.id===leg.id))return 'Use one pick per game. For same-game picks, open Sniper Sauce.';
 if(legs.some(l=>[l.home,l.away].some(t=>[leg.home,leg.away].includes(t))))return 'This ticket already includes one of these teams.';
 if(legs.some(l=>l.provider!==leg.provider))return 'Keep all legs at the same sportsbook.';
 return null;
}
function ticketMath(legs,stake){
 const d=legs.length?legs.reduce((n,l)=>n*(decimal(l.odds)||0),1):0;
 const valid=Number.isFinite(stake)&&stake>0&&stake<=1000000&&d>1;
 return {decimal:d,odds:american(d),return:valid?stake*d:null,profit:valid?stake*(d-1):null,average:legs.length?legs.reduce((n,l)=>n+l.p,0)/legs.length:null,all:legs.length?legs.reduce((n,l)=>n*l.p,1):null};
}
function suggest(pool,count=2,now=Date.now()){
 // Average forecast chance ranks eligible different-game combinations; no invented historical rate.
 const eligible=pool.filter(l=>available(l,now)&&l.p>.5&&l.p-1/decimal(l.odds)>0).sort((a,b)=>b.p-a.p).slice(0,32);
 let best=[];
 function visit(start,legs){if(legs.length===count){if(ticketMath(legs,1).average>(ticketMath(best,1).average||0))best=legs;return;}
  for(let i=start;i<eligible.length;i++)if(!conflict(legs,eligible[i]))visit(i+1,[...legs,eligible[i]]);
 }
 visit(0,[]);return best;
}
function gradeLeg(leg,g){
 if(!g)return 'pending';
 if(/CANCELED|CANCELLED/.test(g.status||''))return 'void';
 if(!g.done)return 'pending';
 const hs=g.homeScore??g.hs,as=g.awayScore??g.as;
 if(!Number.isFinite(hs)||!Number.isFinite(as)||hs===as)return 'pending';
 if(leg.market==='moneyline')return (hs>as?g.home:g.away)===leg.team?'win':'loss';
 if(leg.market==='spread'){
  const margin=(leg.team===g.home?hs-as:as-hs)+leg.line;
  return Math.abs(margin)<1e-9?'push':margin>0?'win':'loss';
 }
 if(leg.market==='total'){
  const diff=hs+as-leg.line;return Math.abs(diff)<1e-9?'push':(diff>0)===(leg.side==='over')?'win':'loss';
 }
 return 'pending';
}
function settle(ticket,games){
 const legs=ticket.legs.map(l=>({...l,result:gradeLeg(l,games.find(g=>g.id===l.id))}));
 const result=legs.some(l=>l.result==='loss')?'loss':legs.some(l=>l.result==='pending')?'pending':legs.every(l=>['void','push'].includes(l.result))?'void':'win';
 const d=legs.filter(l=>l.result==='win').reduce((n,l)=>n*decimal(l.odds),1);
 const returned=result==='pending'?null:result==='loss'?0:ticket.stake*d;
 return {legs,result,returned,profit:returned===null?null:returned-ticket.stake};
}
function restore(value){
 if(!Array.isArray(value))return [];
 return value.filter(t=>t&&typeof t.id==='string'&&Number.isFinite(t.stake)&&t.stake>0&&t.stake<=1e6&&Array.isArray(t.legs)&&t.legs.length>0&&t.legs.length<=6&&t.legs.every(l=>l&&typeof l.id==='string'&&typeof l.team==='string'&&decimal(l.odds)&&Number.isFinite(l.p)&&l.p>=0&&l.p<=1&&l.market==='moneyline')).slice(0,100);
}
const api={day,half,decimal,american,dates,available,conflict,ticketMath,suggest,gradeLeg,settle,restore};
root.GamedayEngine=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
