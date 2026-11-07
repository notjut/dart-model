/* Display and ticket rules only. Forecast fitting and weights are unchanged. */
(function(root){
'use strict';
const day=value=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
const half=value=>Number.isFinite(value)?Math.round(value*2)/2:null;
const decimal=odds=>Number.isFinite(odds)&&Math.abs(odds)>=100?(odds>0?1+odds/100:1+100/-odds):null;
const key=l=>[l.id,l.market||'moneyline',l.market==='total'?l.side:l.team,l.line??''].join(':');
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
 if(legs.length>=12)return 'Your betslip holds up to 12 picks.';
 if(legs.some(l=>l.id===leg.id))return 'Use one pick per game. For same-game picks, open Sniper Sauce.';
 if(legs.some(l=>[l.home,l.away].some(t=>[leg.home,leg.away].includes(t))))return 'This ticket already includes one of these teams.';
 if(legs.some(l=>l.provider!==leg.provider))return 'Keep all legs at the same sportsbook.';
 return null;
}
function ticketMath(legs,stake){
 const d=legs.length?legs.reduce((n,l)=>n*(decimal(l.odds)||0),1):0;
 const valid=Number.isFinite(stake)&&stake>0&&stake<=1000000&&d>1;
 return {decimal:d,odds:american(d),return:valid?stake*d:null,profit:valid?stake*(d-1):null,average:legs.length&&legs.every(l=>Number.isFinite(l.p))?legs.reduce((n,l)=>n+l.p,0)/legs.length:null,all:legs.length&&legs.every(l=>Number.isFinite(l.p))?legs.reduce((n,l)=>n*l.p,1):null};
}
function suggest(pool,count=2,now=Date.now()){
 if(!Number.isInteger(count)||count<1||count>12)return [];
 const eligible=pool.filter(l=>available(l,now)&&l.p>.5&&l.p-1/decimal(l.odds)>0).sort((a,b)=>b.p-a.p);
 let best=[],bestSum=-1;
 // Branch-and-bound avoids enumerating every 12-leg combination. The upper bound
 // ignores conflicts, so pruning cannot discard a better valid combination.
 for(const provider of new Set(eligible.map(l=>l.provider))){
  const rows=eligible.filter(l=>l.provider===provider);
  function visit(start,legs,sum){
   const need=count-legs.length;if(!need){if(sum>bestSum){best=legs;bestSum=sum;}return;}
   if(rows.length-start<need)return;
   if(sum+rows.slice(start,start+need).reduce((n,l)=>n+l.p,0)<=bestSum+1e-12)return;
   for(let i=start;i<=rows.length-need;i++)if(!conflict(legs,rows[i]))visit(i+1,[...legs,rows[i]],sum+rows[i].p);
  }
  visit(0,[],0);
 }
 return best;
}
function toggle(legs,leg){
 const selected=legs.findIndex(l=>key(l)===key(leg));
 if(selected>=0)return {legs:legs.filter((_,i)=>i!==selected),removed:true};
 const remaining=legs.filter(l=>!(l.id===leg.id&&l.market===leg.market)),error=conflict(remaining,leg);
 return error?{legs,error}:{legs:[...remaining,leg],removed:false};
}
function restoreDraft(value){
 if(!value||!Array.isArray(value.legs))return {legs:[],stake:10};
 const valid=restore([{id:'draft',stake:value.stake,legs:value.legs}]);
 return valid.length?{legs:valid[0].legs,stake:valid[0].stake}:{legs:[],stake:10};
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
 return value.filter(t=>t&&typeof t.id==='string'&&Number.isFinite(t.stake)&&t.stake>0&&t.stake<=1e6&&Array.isArray(t.legs)&&t.legs.length>0&&t.legs.length<=12&&t.legs.every(l=>l&&typeof l.id==='string'&&typeof l.team==='string'&&decimal(l.odds)&&(l.p===null||Number.isFinite(l.p)&&l.p>=0&&l.p<=1)&&(['moneyline','spread','total'].includes(l.market))&&(l.market==='moneyline'||Number.isFinite(l.line))&&(l.market!=='total'||['over','under'].includes(l.side)))).slice(0,100);
}
const api={key,day,half,decimal,american,dates,available,conflict,ticketMath,suggest,toggle,restoreDraft,gradeLeg,settle,restore};
root.GamedayEngine=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
