'use strict';
const Seabiscuit=(()=>{
 const minimumOdds=170,maxQuoteAge=72*3600000;
 function eligibleQuote(o,g,now=Date.now()){
  if(!o||!g||g.done||o.state!=='pre'||o.timeValid!==true)return false;
  const start=Date.parse(o.date),kickoff=Date.parse(g.date),stamp=Date.parse(o.retrievedAt);
  return [start,kickoff,stamp].every(Number.isFinite)&&Math.min(start,kickoff)>now&&stamp<=now&&now-stamp<=maxQuoteAge&&['homeMoneyline','awayMoneyline'].every(k=>Number.isFinite(o[k])&&Math.abs(o[k])>=100);
 }
 function isUpsetPick(r){return Number.isFinite(r.odds)&&r.odds>=100&&r.p>.5&&r.margin>0&&r.o[r.side==='home'?'awayMoneyline':'homeMoneyline']<0;}
 function isSeabiscuit(r){return isUpsetPick(r)&&r.odds>=minimumOdds;}
 function picks(pool){return pool.filter(isUpsetPick).sort((a,b)=>Number(isSeabiscuit(b))-Number(isSeabiscuit(a))||b.p-a.p||b.odds-a.odds);}
 const api={eligibleQuote,isUpsetPick,isSeabiscuit,picks};
 if(typeof module!=='undefined')module.exports=api;
 if(typeof document==='undefined')return api;
 function time(value){return new Date(value).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})+' ET';}
 function card(r){const special=isSeabiscuit(r),opp=r.g[r.side==='home'?'away':'home'],q=forecast(r.f);
  return `<article class="sb-card ${special?'sb-special':''}"><div class="sb-card-top"><span class="sb-badge">${special?'<img class="brand-seabiscuit-mark" src="assets/darkhorse-mark.png" alt=""> SEABISCUIT PLAY':'UPSET PICK'}</span><span class="sb-location">${r.g.neutral?'NEUTRAL SITE':r.side==='home'?'HOME UNDERDOG':'ROAD UNDERDOG'}</span></div><div class="sb-logo">${logo(r.team)}</div><h3>${esc(name(r.team))}</h3><strong class="sb-odds">+${r.odds}</strong><div class="sb-market">MONEYLINE · TO WIN OUTRIGHT</div><p class="sb-opponent">${r.g.neutral||r.side==='home'?'vs.':'@'} ${esc(name(opp))}</p><div class="sb-model"><div><small>MODEL WIN CHANCE</small><b>${pPercent(r.p)}</b></div><div><small>PROJECTED SCORE</small><b>${r.side==='home'?q.h:q.a}<span> – </span>${r.side==='home'?q.a:q.h}</b></div></div>${(r.f.coachChangeEvents||[]).map(e=>`<p class="sb-coach-note">${e.team===r.team?'This team’s':'Opponent’s'} first game after a coaching change. See the matchup report.</p>`).join('')}<p class="sb-reason">${esc(pReason(r))}</p><p class="sb-kickoff">${esc(time(r.o.date))}<br>${esc(r.o.channels?.length?r.o.channels.join(' / '):channel(r.g))}</p><button type="button" class="sb-report" data-sb-match="${esc(r.id)}">Why this pick? <span>↗</span></button><div class="sb-source">${esc(r.o.provider||'Posted odds')} · Checked ${esc(time(r.o.retrievedAt))}</div></article>`;
 }
 function section(week,forecasts,pool,now){const selected=picks(pool),special=selected.filter(isSeabiscuit),priced=new Set(pool.map(r=>r.id)).size,upcoming=forecasts.filter(f=>{const g=game(f);return !g.done&&Date.parse(g.date)>now;}).length,stale=DartHealth.health(M,now).stale;
  let status=stale?'New picks are paused while the forecast data refreshes.':!priced?'No eligible moneyline quotes are loaded for this selection yet.':!special.length?'No SEABISCUIT PLAY qualifies in this selection yet.':`${special.length} SEABISCUIT ${special.length===1?'PLAY':'PLAYS'} · Model picks an underdog at +${minimumOdds} or higher to win.`;
  return `<section class="sb-week"><div class="sb-week-head"><div><div class="eyebrow">THE DARKHORSE MODEL · ${esc(pWeekLabel(week))}</div><h2>THE UPSET <span>CARD.</span></h2><p>Underdogs we pick to win. <b>Outright.</b></p></div><span class="sb-count">${selected.length}<small>UPSET PICKS</small></span></div><div class="sb-rule ${special.length?'sb-rule-active':''}"><span class="sb-horse" aria-hidden="true"><img src="assets/darkhorse-mark.png" alt="" width="42" height="42"></span><div><b>SEABISCUIT PLAY</b><p>+${minimumOdds} or higher moneyline. Our model picks the win.</p><small>${esc(status)}</small></div>${special.length?'<span class="sb-live-dot" aria-hidden="true"></span>':''}</div>${selected.length?`<div class="sb-scroll-note"><span>LOGO. ODDS. OUR PICK.</span><span>Scroll for all ${selected.length} picks →</span></div><div class="sb-rail" tabindex="0" role="region" aria-label="${esc(pWeekLabel(week))} outright upset picks">${selected.map(card).join('')}</div>`:`<div class="sb-empty">${stale?'Fresh forecasts will bring this card back.':priced?'No priced underdog is projected to win outright in this selection.':'This week’s upset picks will appear here when eligible odds and forecasts are available.'}</div>`}<p class="sb-coverage">${priced} of ${upcoming} upcoming games eligible for this card. Only underdogs the model picks to win appear here. Odds are saved quotes and can change.</p></section>`;
 }
 function bind(mount){mount.querySelectorAll('[data-sb-match]').forEach(b=>b.onclick=()=>{$('matchConference').value='all';fillGames();show(b.dataset.sbMatch);tab('lab');document.querySelector('nav').scrollIntoView({behavior:'smooth',block:'start'});});}
 api.renderWeek=(week,pool)=>{const mount=$('weeklyUpsets');if(!mount)return;mount.innerHTML=section(week,M.forecasts.filter(f=>pWeek(game(f).date)===week),pool,Date.now());bind(mount);};
 api.renderHub=fs=>{
  if(typeof parlayOdds==='undefined'||!parlayOdds)return;
  let mount=$('seabiscuitHub');if(!mount){mount=document.createElement('div');mount.id='seabiscuitHub';}
  if($('slate').firstElementChild!==mount)$('slate').prepend(mount);
  const now=Date.now(),weeks=[...new Set(fs.filter(f=>Date.parse(game(f).date)>now).map(f=>pWeek(game(f).date)))].sort();
  mount.innerHTML=weeks.map(w=>{const forecasts=fs.filter(f=>pWeek(game(f).date)===w),ids=new Set(forecasts.map(f=>f.id));return section(w,forecasts,pCandidates(w,now).filter(r=>ids.has(r.id)),now);}).join('');bind(mount);
 };
 return api;
})();
