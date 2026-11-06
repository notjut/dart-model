/* Sniper Sauce: observed player production and verified bookmaker snapshots. */
(function(root){
'use strict';
const fresh=(q,now=Date.now())=>Number.isFinite(Date.parse(q.updatedAt)) && now-Date.parse(q.updatedAt)>=0 && now-Date.parse(q.updatedAt)<=6*3600000;
const win=(value,q)=>q.side==='Over'?value>q.line:value<q.line;
function rate(p,q){const values=p.samples.map(s=>s.value*p.matchupFactor);return {wins:values.filter(v=>win(v,q)).length,pushes:values.filter(v=>v===q.line).length,n:values.length};}
function dataStale(data,runId,now=Date.now()){
 const age=now-Date.parse(data.inputRetrievedAt);
 return data.refreshRunId!==runId || !Number.isFinite(age) || age<0 || age>30*3600000;
}
function feedStatus(data,stale=false){
 if(stale)return {title:'Player data needs a refresh',message:'This player snapshot no longer matches a fresh forecast. SGP suggestions will resume after a successful update.'};
 const code=data.providerError?.code;
 if(data.lineStatus==='provider_error'){
  if(code==='OUT_OF_USAGE_CREDITS')return {title:'Prop-feed credits exhausted',message:'The Odds API has run out of usage credits. The site cannot retrieve new player-prop lines until credits renew or are replenished. Player averages and projections still work.'};
  if(['INVALID_KEY','DEACTIVATED_KEY','MISSING_KEY'].includes(code))return {title:'Prop-feed access failed',message:'The Odds API rejected the configured key. The site owner needs to check that API account and its saved key. Player averages and projections still work.'};
  if(code==='EXCEEDED_FREQ_LIMIT')return {title:'Prop feed temporarily rate-limited',message:'The Odds API asked us to slow down. The next scheduled refresh will try again; only unexpired saved quotes can be used.'};
  return {title:'Prop feed could not refresh',message:'The connected provider returned an error. The next scheduled refresh will try again. Each game below shows whether it has usable quotes.'};
 }
 if(data.lineStatus==='connected')return {title:'Prop feed connected',message:'A connection does not mean every game has posted props. Each SGP needs current lines from the same sportsbook and enough shared player history. Quotes expire after six hours.'};
 return {title:'Player-prop feed not connected',message:'Player averages and projections are loaded. The site owner needs to connect The Odds API before sportsbook lines and SGP suggestions are available.'};
}
function assess(g,now=Date.now()){
 const blocked=(code,message)=>({code,message,ticket:null});
 if(!Number.isFinite(Date.parse(g.date))||Date.parse(g.date)<=now)return blocked('started','Kickoff has passed. Pregame SGP suggestions are closed.');
 if(g.reviewRequired)return blocked('review','This matchup needs a lineup review before an SGP can be suggested.');
 const quotes=g.players.flatMap(p=>p.quotes);
 if(!quotes.length)return blocked('no_quotes','No posted player-prop lines are available for this matchup yet. A projection alone cannot build an SGP.');
 if(!quotes.some(q=>fresh(q,now)))return blocked('expired','The saved prop lines have expired. We need quotes updated within the last six hours.');
 const withHistory=g.players.filter(p=>p.samples.length>=6&&p.quotes.some(q=>fresh(q,now)));
 if(new Set(withHistory.map(p=>p.id)).size<2)return blocked('history','We need current lines and at least six recorded games for two different players.');
 const candidates=g.players.flatMap(p=>p.quotes.filter(q=>fresh(q,now)).map(q=>({p,q,r:rate(p,q)}))).filter(x=>x.r.n>=6&&x.r.wins/x.r.n>=.6);
 if(new Set(candidates.map(x=>x.p.id)).size<2)return blocked('threshold','Fewer than two players meet the screen: each leg must have beaten its current line in at least 60% of six or more adjusted past performances. No SGP qualifies right now.');
 let best=null;
 let paired=false;
 for(let i=0;i<candidates.length;i++)for(let j=i+1;j<candidates.length;j++){
  const a=candidates[i],b=candidates[j];
  if(a.p.id===b.p.id||a.p.team!==b.p.team||a.q.bookKey!==b.q.bookKey)continue;
  paired=true;
  const pairs=a.p.samples.flatMap(x=>{const y=b.p.samples.find(y=>y.gameId===x.gameId);return y?[[x.value*a.p.matchupFactor,y.value*b.p.matchupFactor]]:[]});
  if(pairs.length<6)continue;
  const hits=pairs.filter(([x,y])=>win(x,a.q)&&win(y,b.q)).length;
  if(!best||hits/pairs.length>best.hits/best.n)best={legs:[a,b],hits,n:pairs.length};
 }
 if(best)return {code:'ready',message:'A two-leg research slip qualifies. Check player availability and the combined price at your sportsbook.',ticket:best};
 if(!paired)return blocked('pairing','The qualifying legs do not pair at the same sportsbook for two different players on the same team. This builder currently supports teammate pairs only.');
 return blocked('shared_history','The qualifying players have fewer than six shared recorded games. There is not enough joint history to suggest this pair.');
}
function formulate(g,now=Date.now()){return assess(g,now).ticket;}
function readiness(g,data,runId,now=Date.now()){
 const stale=dataStale(data,runId,now);
 if(stale)return {code:'stale',message:feedStatus(data,true).message,ticket:null};
 const result=assess(g,now);
 if(['no_quotes','expired'].includes(result.code)&&data.lineStatus==='provider_error')result.message=feedStatus(data).message+' No usable lines are available for this matchup.';
 if(result.code==='no_quotes'&&data.lineStatus==='not_connected')result.message=feedStatus(data).message;
 return result;
}
root.SniperEngine={fresh,rate,formulate,assess,dataStale,feedStatus,readiness};
if(typeof module!=='undefined')module.exports=root.SniperEngine;
if(typeof document==='undefined')return;
const section=document.createElement('section');section.id='sniper';section.className='tab';section.hidden=true;
section.innerHTML='<article class="sniper-hero"><span class="eyebrow">THE DARKHORSE PROP DESK</span><h2>SNIPER <em>SAUCE</em><span class="sniper-cross">⌖</span></h2><p>Find the player. See the number. Understand the angle.</p><div id="sniper-status" role="status">Loading player production…</div></article><label class="sniper-search">Find a matchup<input id="sniper-search" type="search" placeholder="Search a team…"></label><div id="sniper-games"></div>';
document.querySelector('main footer').before(section);
const nav=document.querySelector('#mainNavigation');const button=document.createElement('button');button.dataset.tab='sniper';button.textContent='Sniper Sauce';button.onclick=()=>tab('sniper');nav.insertBefore(button,nav.children[2]);
 document.getElementById('sniper-search').addEventListener('input',e=>section.querySelectorAll('.sniper-game').forEach(g=>g.hidden=!g.querySelector('summary').textContent.toLowerCase().includes(e.target.value.toLowerCase())));
const odds=x=>(x>0?'+':'')+x;
function render(data){
 const stale=dataStale(data,M.refreshRunId),status=feedStatus(data,stale);
 const currentQuotes=data.games.reduce((n,g)=>n+g.players.reduce((n,p)=>n+p.quotes.filter(q=>fresh(q)).length,0),0);
 document.getElementById('sniper-status').innerHTML=`<b>${esc(status.title)}</b><p>${esc(status.message)}</p><small>${stale?'0':currentQuotes} usable prop quotes · Feed checked ${esc(new Date(data.generatedAt).toLocaleString())} · ${(data.missingBoxscores||[]).length} source boxscores unavailable</small>`;
 function gameBody(g){const check=readiness(g,data,M.refreshRunId);return `<div class="sniper-toolbar"><p>Projected stat = recent average, adjusted for the opposing defense. <strong>Availability is not confirmed.</strong></p><button class="sniper-build" data-game="${esc(g.id)}" aria-describedby="sniper-reason-${esc(g.id)}" ${check.ticket?'':'disabled'}>${check.ticket?'⌖ Formulate SGP':'SGP unavailable'}</button></div><p class="sniper-readiness ${check.ticket?'is-ready':''}" id="sniper-reason-${esc(g.id)}"><strong>${check.ticket?'Ready to build':'Why no SGP?'}</strong> ${esc(check.message)}</p><div class="sniper-ticket" id="sniper-ticket-${esc(g.id)}" aria-live="polite"></div>${g.players.length?`<div class="sniper-table"><table><thead><tr><th>Player / prop</th><th>Posted line</th><th>Projected stat</th><th>Estimated hit rate*</th><th>Why this number?</th></tr></thead><tbody>${g.players.map(p=>{
 const quotes=stale?[]:p.quotes.filter(q=>fresh(q));
 return `<tr><td><strong>${esc(p.name)}</strong><small>${esc(name(p.team))} · ${esc(p.label)}</small></td><td>${quotes.length?quotes.map(q=>`<div>${esc(q.side)} ${q.line} <b>${odds(q.odds)}</b><small>${esc(q.book)} · ${esc(new Date(q.updatedAt).toLocaleTimeString())}</small></div>`).join(''):'<span class="sniper-muted">Awaiting current line</span>'}</td><td class="sniper-number">${p.projection}<small>Average ${p.average}</small></td><td>${quotes.length?quotes.map(q=>{const r=rate(p,q);return `<div><b>${Math.round(100*r.wins/r.n)}%</b><small>${esc(q.side)} ${q.line}: ${r.wins}/${r.n} · ${r.pushes} pushes</small></div>`}).join(''):'—'}</td><td><details><summary>See the breakdown</summary><p>${esc(p.name)} averaged ${p.average} across ${p.samples.length} recorded stat appearances. ${p.matchupFactor===1?'No matchup adjustment applied.':`The opponent adjustment changes that by ${Math.round((p.matchupFactor-1)*100)}%, using ${p.opponentSample} games of yards allowed.`}</p><b>How game outcomes changed production</b>${Object.entries(p.scenarios).map(([label,s])=>`<p>${esc(label)}: ${s.n?`${s.average} average (${s.n} games)`:'No recorded sample'}</p>`).join('')}<small>These are past final-score groups, not a prediction of time spent leading.</small><p>${p.samples.map(s=>`<a href="https://www.espn.com/college-football/boxscore/_/gameId/${encodeURIComponent(s.gameId)}" target="_blank" rel="noreferrer">${esc(s.date.slice(5,10))}: ${s.value}</a>`).join(' · ')}</p></details></td></tr>`;
 }).join('')}</tbody></table></div>`:'<p>Not enough recorded appearances to project players for this game yet.</p>'}<p class="sniper-footnote">*Estimated hit rate is the share of matchup-adjusted past performances that beat the posted line. It is experimental, not a validated chance of winning. Missing stat rows are excluded, not treated as zero. Small samples, injuries and role changes can change the outlook.</p>`;}
 document.getElementById('sniper-games').innerHTML=data.games.filter(g=>Date.parse(g.date)>Date.now()).map(g=>`<details class="sniper-game"><summary><span class="sniper-teams"><span class="sniper-side">${logo(g.away)} ${rankedName(g.away)}</span><span class="sniper-at">at</span><span class="sniper-side">${logo(g.home)} ${rankedName(g.home)}</span></span><span>${new Date(g.date).toLocaleDateString(undefined,{month:'short',day:'numeric'})} · ${g.players.length} player markets <b>＋</b></span></summary><div class="sniper-body" data-game-body="${esc(g.id)}"></div></details>`).join('')||'<article>No upcoming games in the current forecast.</article>';
 section.querySelectorAll('.sniper-game').forEach(details=>details.addEventListener('toggle',()=>{
 if(!details.open)return;const body=details.querySelector('[data-game-body]');if(body.dataset.loaded)return;
 const g=data.games.find(g=>g.id===body.dataset.gameBody);body.innerHTML=gameBody(g);body.dataset.loaded='true';
 const b=body.querySelector('.sniper-build');b.addEventListener('click',()=>{
 const g=data.games.find(g=>g.id===b.dataset.game),check=readiness(g,data,M.refreshRunId),ticket=check.ticket,out=document.getElementById('sniper-ticket-'+g.id);
 if(!ticket){out.innerHTML=`<p><strong>SGP unavailable:</strong> ${esc(check.message)}</p>`;b.disabled=true;b.textContent='SGP unavailable';document.getElementById('sniper-reason-'+g.id).textContent=check.message;return;}
 out.innerHTML=`<h3>SGP research slip · ${esc(ticket.legs[0].q.book)}</h3>${ticket.legs.map(({p,q})=>`<p><strong>${esc(p.name)}</strong> · ${esc(q.side)} ${q.line} ${esc(p.label)} <b>${odds(q.odds)}</b></p>`).join('')}<p>Both legs would have hit in <b>${ticket.hits} of ${ticket.n}</b> shared historical games after the matchup adjustment.</p><p>Selected from the strongest historical combinations; this can overstate future success. Individual odds are shown above. Combined payout requires a sportsbook SGP quote and is not estimated here. Confirm both players are active and the book permits this pairing.</p>`;
 });
 }));
}
(async()=>{try{await initialDataReady;const r=await fetch('sniper-props.json',{cache:'no-store'});if(!r.ok)throw Error();render(await r.json());}catch(e){document.getElementById('sniper-status').textContent='Player data could not load. Refresh the page to try again.';}})();
})(typeof globalThis!=='undefined'?globalThis:this);
