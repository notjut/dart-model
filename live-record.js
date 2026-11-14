/* Provisional standings of frozen pregame picks. Never settles tickets. */
(function(root){
'use strict';
const keys=['winner','spread','total'],labels={winner:'MONEYLINE',spread:'SPREAD',total:'OVER / UNDER'};
const finite=Number.isFinite,eq=x=>Math.abs(x)<1e-9;
const day=v=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(v));
function week(v){const d=new Date(day(v)+'T12:00Z');d.setUTCDate(d.getUTCDay()===0?d.getUTCDate()-6:d.getUTCDate()-(d.getUTCDay()-1));return d.toISOString().slice(0,10);}
function grade(edge){return eq(edge)?'even':edge>0?'win':'loss';}
function elapsed(g){const p=g.period,c=g.clock;if(!Number.isInteger(p)||p<1||p>4||!finite(c)||c<0||c>900)return null;return (p-1)*900+900-c;}
function assess(g,now=Date.now()){
 const base={id:g.id,date:g.date,home:g.home,away:g.away,phase:'pending',winner:null,spread:null,total:null,reason:'Not started',picks:{}};
 if(!finite(Date.parse(g.date))||Date.parse(g.date)>now)return base;
 if(/POSTPONED|CANCEL|SUSPEND|DELAYED/.test(g.status||''))return {...base,reason:/POSTPONED/.test(g.status)?'Postponed':'Not currently playing'};
 const p=g.savedPick;if(!p||!finite(Date.parse(p.forecastAt))||Date.parse(p.forecastAt)>=Date.parse(g.date))return {...base,reason:'No saved pregame pick'};
 const h=g.homeScore??g.hs,a=g.awayScore??g.as;
 if(!finite(h)||!finite(a)||h<0||a<0)return {...base,reason:'Score unavailable'};
 const final=!!g.done,live=g.state==='in';if(!final&&!live)return {...base,reason:'Awaiting live score'};
 const row={...base,phase:final?'final':'live',homeScore:h,awayScore:a,reason:final?'Final':g.detail||'Live',picks:{}};
 if(finite(p.homeMargin)&&!eq(p.homeMargin)){row.picks.winner={team:p.homeMargin>0?g.home:g.away};row.winner=grade((h-a)*Math.sign(p.homeMargin));}
 const q=p.quote,validQuote=q&&finite(Date.parse(q.retrievedAt))&&Date.parse(q.retrievedAt)<Date.parse(g.date);
 if(validQuote&&finite(p.homeMargin)&&finite(q.homeSpread)&&!eq(p.homeMargin+q.homeSpread)){
  const direction=Math.sign(p.homeMargin+q.homeSpread);row.picks.spread={team:direction>0?g.home:g.away,line:direction*q.homeSpread};row.spread=grade(((h-a)+q.homeSpread)*direction);
 }
 if(validQuote&&finite(p.total)&&finite(q.overUnder)&&!eq(p.total-q.overUnder)){
  const over=p.total>q.overUnder;row.picks.total={side:over?'Over':'Under',line:q.overUnder};const actual=h+a;row.actualTotal=actual;
  if(final){row.total=grade((actual-q.overUnder)*(over?1:-1));}
  else if(actual>q.overUnder){row.total=over?'win':'loss';row.totalMethod='Total already exceeded';}
  else{const seconds=elapsed(g);if(seconds!==null&&seconds>=180){row.paceTotal=actual*3600/seconds;row.total=grade((row.paceTotal-q.overUnder)*(over?1:-1));row.totalMethod='60-minute scoring pace';}else row.totalMethod=g.period>4?'Awaiting overtime scoring':'Too early / clock unavailable';}
 }
 return row;
}
function summarize(games,now=Date.now()){
 const start=week(now),seen=new Set(),rows=[];
 for(const g of games){if(!g?.id||seen.has(g.id)||!finite(Date.parse(g.date))||week(g.date)!==start)continue;seen.add(g.id);rows.push(assess(g,now));}
 const counts={};for(const k of keys){const c={final:{win:0,loss:0,even:0},live:{win:0,loss:0,even:0},pending:0};for(const r of rows){if((r.phase==='final'||r.phase==='live')&&r[k])c[r.phase][r[k]]++;else c.pending++;}counts[k]=c;}
 return {start,rows,counts};
}
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const record=c=>`${c.win}–${c.loss}`;
function render(mount,games,teams,{now=Date.now(),stale=false,retrievedAt=null}={}){
 const data=summarize(games,now),end=new Date(data.start+'T12:00Z');end.setUTCDate(end.getUTCDate()+6);
 const short=d=>new Date(d).toLocaleDateString('en-US',{month:'short',day:'numeric',timeZone:'UTC'}),name=id=>teams[id]?.abbr||teams[id]?.name||id;
 const open=mount.querySelector('details')?.open||false;
 const text=(r,k)=>{const result=r[k];if(!result)return k==='total'&&r.totalMethod?r.totalMethod:r.picks[k]?'Waiting':'No saved pick / line';return r.phase==='final'?{win:'WIN',loss:'LOSS',even:'PUSH'}[result]:{win:k==='total'?'ON PACE':k==='spread'?'COVERING':'LEADING',loss:k==='total'?'OFF PACE':k==='spread'?'NOT COVERING':'TRAILING',even:'EVEN'}[result];};
 const pick=(r,k)=>{const p=r.picks[k];return !p?'—':k==='winner'?name(p.team):k==='spread'?`${name(p.team)} ${p.line>0?'+':''}${p.line}`:`${p.side} ${p.line}`;};
 const receipts=data.rows.filter(r=>r.phase!=='pending').sort((a,b)=>(a.phase==='live'?0:1)-(b.phase==='live'?0:1)||b.date.localeCompare(a.date));
 mount.innerHTML=`<div class="wr-heading"><div><span class="eyebrow">THIS WEEK · ${short(data.start+'T12:00Z')}–${short(end)}</span><h2>Live pick record <span>///</span></h2></div><span class="wr-status">${stale?'SCORES DELAYED':receipts.some(r=>r.phase==='live')?'LIVE STANDINGS':'WEEKLY STANDINGS'}${retrievedAt?' · '+esc(new Date(retrievedAt).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'}))+' ET':''}</span></div><div class="wr-metrics">${keys.map(k=>{const c=data.counts[k],total={win:c.final.win+c.live.win,loss:c.final.loss+c.live.loss},even=c.final.even+c.live.even;return `<div class="wr-metric"><span>${labels[k]}</span><strong>${record(total)}</strong><p>Final <b>${record(c.final)}</b> · Live${k==='total'?' pace':''} <b>${record(c.live)}</b></p><small>${even?even+' '+(k==='winner'?'tied':'even / pushed')+' · ':''}${c.pending} waiting / ungraded</small></div>`;}).join('')}</div><p class="wr-note">Finals + live standings. Live games can flip; O/U uses scoring pace, not a settled result.</p><details ${open?'open':''}><summary>See this week’s picks <span>${receipts.length} scored games</span></summary><p class="wr-note">Week runs Monday–Sunday, Eastern. ML follows the current leader. Spread compares the current margin with our saved line. O/U pace = points scored ÷ game minutes played × 60, starting after 3 minutes. Overtime has no pace estimate. Ties and pushes stay outside W–L. Missing pregame picks or lines never count as wins.</p><div class="wr-receipts">${receipts.length?receipts.map(r=>`<article class="wr-game"><div><b>${esc(name(r.away))} ${r.awayScore} · ${esc(name(r.home))} ${r.homeScore}</b><small>${esc(r.reason)}</small></div><div class="wr-game-markets">${keys.map(k=>`<div><span>${labels[k]} · ${esc(pick(r,k))}</span><b class="wr-${r[k]||'pending'}">${esc(text(r,k))}</b>${k==='total'&&r.phase==='live'?`<small>${finite(r.paceTotal)?'Pace '+(Math.round(r.paceTotal*2)/2):esc(r.totalMethod||'')}</small>`:''}</div>`).join('')}</div></article>`).join(''):'<p>No scored games with saved picks yet this week.</p>'}</div></details>`;
 return data;
}
root.DarkhorseLiveRecord={assess,summarize,elapsed,week,render};if(typeof module!=='undefined')module.exports=root.DarkhorseLiveRecord;
})(globalThis);
