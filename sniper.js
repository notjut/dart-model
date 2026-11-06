/* Sniper Sauce: observed player production and verified bookmaker snapshots. */
(function(root){
'use strict';
const fresh=(q,now=Date.now())=>Number.isFinite(Date.parse(q.updatedAt)) && now-Date.parse(q.updatedAt)>=0 && now-Date.parse(q.updatedAt)<=6*3600000;
const win=(value,q)=>q.side==='Over'?value>q.line:value<q.line;
function rate(p,q){const values=p.samples.map(s=>s.value*p.matchupFactor);return {wins:values.filter(v=>win(v,q)).length,pushes:values.filter(v=>v===q.line).length,n:values.length};}
function formulate(g,now=Date.now()){
 if(Date.parse(g.date)<=now || g.reviewRequired)return null;
 const candidates=g.players.flatMap(p=>p.quotes.filter(q=>fresh(q,now)).map(q=>({p,q,r:rate(p,q)}))).filter(x=>x.r.n>=6&&x.r.wins/x.r.n>=.6);
 let best=null;
 for(let i=0;i<candidates.length;i++)for(let j=i+1;j<candidates.length;j++){
  const a=candidates[i],b=candidates[j];
  if(a.p.id===b.p.id||a.p.team!==b.p.team||a.q.bookKey!==b.q.bookKey)continue;
  const pairs=a.p.samples.flatMap(x=>{const y=b.p.samples.find(y=>y.gameId===x.gameId);return y?[[x.value*a.p.matchupFactor,y.value*b.p.matchupFactor]]:[]});
  if(pairs.length<6)continue;
  const hits=pairs.filter(([x,y])=>win(x,a.q)&&win(y,b.q)).length;
  if(!best||hits/pairs.length>best.hits/best.n)best={legs:[a,b],hits,n:pairs.length};
 }
 return best;
}
root.SniperEngine={fresh,rate,formulate};
if(typeof module!=='undefined')module.exports=root.SniperEngine;
if(typeof document==='undefined')return;
const section=document.createElement('section');section.id='sniper';section.className='tab';section.hidden=true;
section.innerHTML='<article class="sniper-hero"><span class="eyebrow">THE DARKHORSE PROP DESK</span><h2>SNIPER <em>SAUCE</em><span class="sniper-cross">⌖</span></h2><p>Find the player. See the number. Understand the angle.</p><div id="sniper-status" role="status">Loading player production…</div></article><label class="sniper-search">Find a matchup<input id="sniper-search" type="search" placeholder="Search a team…"></label><div id="sniper-games"></div>';
document.querySelector('main footer').before(section);
const nav=document.querySelector('#mainNavigation');const button=document.createElement('button');button.dataset.tab='sniper';button.textContent='Sniper Sauce';button.onclick=()=>tab('sniper');nav.insertBefore(button,nav.children[2]);
 document.getElementById('sniper-search').addEventListener('input',e=>section.querySelectorAll('.sniper-game').forEach(g=>g.hidden=!g.querySelector('summary').textContent.toLowerCase().includes(e.target.value.toLowerCase())));
const odds=x=>(x>0?'+':'')+x;
function render(data){
 const stale=data.refreshRunId!==M.refreshRunId || !Number.isFinite(Date.parse(data.inputRetrievedAt)) || Date.now()-Date.parse(data.inputRetrievedAt)>30*3600000;
 document.getElementById('sniper-status').innerHTML=`<b>${stale?'Refresh needed':data.lineStatus==='connected'?'Prop feed connected':'Posted prop lines unavailable'}</b><p>${stale?'Player data does not match a fresh forecast. SGP suggestions are paused.':data.lineStatus==='connected'?'Only quotes updated within six hours qualify for suggestions. Confirm availability and the final price at your sportsbook.':'Real player game logs are loaded. A player-prop API key is needed to show sportsbook lines and build tickets. No made-up lines or percentages.'}</p><small>Experimental projections · ${esc(new Date(data.generatedAt).toLocaleString())} · ${(data.missingBoxscores||[]).length} source boxscores unavailable</small>`;
 function gameBody(g){return `<div class="sniper-toolbar"><p>Projected stat = recent average, adjusted for the opposing defense. <strong>Availability is not confirmed.</strong></p><button class="sniper-build" data-game="${esc(g.id)}" ${stale||g.reviewRequired||!g.players.some(p=>p.quotes.some(q=>fresh(q)))?'disabled':''}>⌖ Formulate SGP</button></div>${g.reviewRequired?'<p class="sniper-warning">This matchup needs a lineup review. Ticket suggestions are paused.</p>':''}<div class="sniper-ticket" id="sniper-ticket-${esc(g.id)}" aria-live="polite"></div>${g.players.length?`<div class="sniper-table"><table><thead><tr><th>Player / prop</th><th>Posted line</th><th>Projected stat</th><th>Estimated hit rate*</th><th>Why this number?</th></tr></thead><tbody>${g.players.map(p=>{
 const quotes=stale?[]:p.quotes.filter(q=>fresh(q));
 return `<tr><td><strong>${esc(p.name)}</strong><small>${esc(name(p.team))} · ${esc(p.label)}</small></td><td>${quotes.length?quotes.map(q=>`<div>${esc(q.side)} ${q.line} <b>${odds(q.odds)}</b><small>${esc(q.book)} · ${esc(new Date(q.updatedAt).toLocaleTimeString())}</small></div>`).join(''):'<span class="sniper-muted">Awaiting current line</span>'}</td><td class="sniper-number">${p.projection}<small>Average ${p.average}</small></td><td>${quotes.length?quotes.map(q=>{const r=rate(p,q);return `<div><b>${Math.round(100*r.wins/r.n)}%</b><small>${esc(q.side)} ${q.line}: ${r.wins}/${r.n} · ${r.pushes} pushes</small></div>`}).join(''):'—'}</td><td><details><summary>See the breakdown</summary><p>${esc(p.name)} averaged ${p.average} across ${p.samples.length} recorded stat appearances. ${p.matchupFactor===1?'No matchup adjustment applied.':`The opponent adjustment changes that by ${Math.round((p.matchupFactor-1)*100)}%, using ${p.opponentSample} games of yards allowed.`}</p><b>How game outcomes changed production</b>${Object.entries(p.scenarios).map(([label,s])=>`<p>${esc(label)}: ${s.n?`${s.average} average (${s.n} games)`:'No recorded sample'}</p>`).join('')}<small>These are past final-score groups, not a prediction of time spent leading.</small><p>${p.samples.map(s=>`<a href="https://www.espn.com/college-football/boxscore/_/gameId/${encodeURIComponent(s.gameId)}" target="_blank" rel="noreferrer">${esc(s.date.slice(5,10))}: ${s.value}</a>`).join(' · ')}</p></details></td></tr>`;
 }).join('')}</tbody></table></div>`:'<p>Not enough recorded appearances to project players for this game yet.</p>'}<p class="sniper-footnote">*Estimated hit rate is the share of matchup-adjusted past performances that beat the posted line. It is experimental, not a validated chance of winning. Missing stat rows are excluded, not treated as zero. Small samples, injuries and role changes can change the outlook.</p>`;}
 document.getElementById('sniper-games').innerHTML=data.games.filter(g=>Date.parse(g.date)>Date.now()).map(g=>`<details class="sniper-game"><summary><span class="sniper-teams">${logo(g.away)} ${esc(name(g.away))}<span class="sniper-at">at</span>${logo(g.home)} ${esc(name(g.home))}</span><span>${new Date(g.date).toLocaleDateString(undefined,{month:'short',day:'numeric'})} · ${g.players.length} player markets <b>＋</b></span></summary><div class="sniper-body" data-game-body="${esc(g.id)}"></div></details>`).join('')||'<article>No upcoming games in the current forecast.</article>';
 section.querySelectorAll('.sniper-game').forEach(details=>details.addEventListener('toggle',()=>{
 if(!details.open)return;const body=details.querySelector('[data-game-body]');if(body.dataset.loaded)return;
 const g=data.games.find(g=>g.id===body.dataset.gameBody);body.innerHTML=gameBody(g);body.dataset.loaded='true';
 const b=body.querySelector('.sniper-build');b.addEventListener('click',()=>{
 const g=data.games.find(g=>g.id===b.dataset.game),ticket=Date.now()-Date.parse(data.inputRetrievedAt)>30*3600000?null:formulate(g),out=document.getElementById('sniper-ticket-'+g.id);
 if(!ticket){out.innerHTML='<p>No supported two-leg combination: we need fresh lines from the same book and at least six shared historical games for two different players on the same team.</p>';return;}
 out.innerHTML=`<h3>SGP research slip · ${esc(ticket.legs[0].q.book)}</h3>${ticket.legs.map(({p,q})=>`<p><strong>${esc(p.name)}</strong> · ${esc(q.side)} ${q.line} ${esc(p.label)} <b>${odds(q.odds)}</b></p>`).join('')}<p>Both legs would have hit in <b>${ticket.hits} of ${ticket.n}</b> shared historical games after the matchup adjustment.</p><p>Selected from the strongest historical combinations; this can overstate future success. Individual odds are shown above. Combined payout requires a sportsbook SGP quote and is not estimated here. Confirm both players are active and the book permits this pairing.</p>`;
 });
 }));
}
(async()=>{try{await initialDataReady;const r=await fetch('sniper-props.json',{cache:'no-store'});if(!r.ok)throw Error();render(await r.json());}catch(e){document.getElementById('sniper-status').textContent='Player data could not load. Refresh the page to try again.';}})();
})(typeof globalThis!=='undefined'?globalThis:this);
