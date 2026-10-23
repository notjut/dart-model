'use strict';
const parlayCategories=[
 {id:'straight',icon:'01',name:'One & Done',tag:'STRAIGHT PICKS',desc:'One game. One winner. Ranked by the model’s advantage over the quoted break-even chance.'},
 {id:'confidence',icon:'02',name:'Model Favorites',tag:'MOST CONFIDENT',desc:'Two-leg tickets with the highest combined model win chance among eligible picks.'},
 {id:'upsets',icon:'03',name:'Underdog Energy',tag:'UPSET HUNTERS',desc:'Two plus-money teams, each with at least a 30% model chance. Both must win outright.'},
 {id:'longshot',icon:'04',name:'The Long Shot',tag:'HIGH PAYOUTS',desc:'Three-leg tickets ranked by payout, with at least a 35% model chance for each leg. Expect more misses.'},
 {id:'mix',icon:'05',name:'Saturday Sampler',tag:'FAVORITES + AN UPSET',desc:'Two model favorites and one plus-money upset pick. Three different games.'}
];
let parlayOdds,parlayCategory='confidence',parlayTickets=[];
const pDecimal=odds=>odds>0?1+odds/100:1+100/Math.abs(odds);
const pAmerican=decimal=>decimal>=2?'+'+Math.round((decimal-1)*100):String(-Math.round(100/(decimal-1)));
const pPercent=x=>(x*100).toFixed(1)+'%';
function pWeek(date){const s=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(date));const d=new Date(s+'T12:00:00Z');d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));return d.toISOString().slice(0,10)}
function pWeekLabel(key){const d=new Date(key+'T12:00:00Z'),end=new Date(d);end.setUTCDate(end.getUTCDate()+6);const fmt=new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',timeZone:'UTC'});return fmt.format(d)+' – '+fmt.format(end)}
function pCandidates(week,now=Date.now()){
 const result=[];
 for(const f of M.forecasts){
  const g=game(f),o=parlayOdds.games[f.id];
  if(!o||o.state!=='pre'||!o.timeValid||Date.parse(o.date)<=now||pWeek(o.date)!==week||now-Date.parse(o.retrievedAt)>72*3600000)continue;
  const q=forecast(f);
  for(const side of ['home','away']){
   const odds=o[side+'Moneyline'];if(!Number.isFinite(odds)||Math.abs(odds)<100)continue;
   const team=g[side],p=side==='home'?q.p:1-q.p,decimal=pDecimal(odds);
   result.push({id:f.id,team,side,p,odds,decimal,edge:p-1/decimal,f,g,o,margin:side==='home'?q.margin:-q.margin});
  }
 }
 return result;
}
function pCombinations(pool,n){const out=[];function visit(start,legs){if(legs.length===n){out.push({legs:[...legs],p:legs.reduce((a,b)=>a*b.p,1),decimal:legs.reduce((a,b)=>a*b.decimal,1)});return}for(let i=start;i<pool.length;i++){const r=pool[i];if(legs.some(l=>l.id===r.id||l.g.home===r.g.home||l.g.home===r.g.away||l.g.away===r.g.home||l.g.away===r.g.away||l.o.provider!==r.o.provider))continue;visit(i+1,[...legs,r])}}visit(0,[]);return out}
function pBuild(category,pool){
 let tickets=[];
 if(category==='straight')tickets=pCombinations(pool.filter(r=>r.p>=.5&&r.edge>0),1).sort((a,b)=>b.legs[0].edge-a.legs[0].edge);
 if(category==='confidence')tickets=pCombinations(pool.filter(r=>r.p>=.65).sort((a,b)=>b.p-a.p).slice(0,14),2).sort((a,b)=>b.p-a.p);
 if(category==='upsets')tickets=pCombinations(pool.filter(r=>r.odds>0&&r.p>=.3).sort((a,b)=>b.p-a.p).slice(0,14),2).sort((a,b)=>b.p-a.p);
 if(category==='longshot')tickets=pCombinations(pool.filter(r=>r.p>=.35).sort((a,b)=>b.decimal-a.decimal).slice(0,18),3).sort((a,b)=>b.decimal-a.decimal||b.p-a.p);
 if(category==='mix'){
  const favorites=pool.filter(r=>r.odds<0&&r.p>=.65).sort((a,b)=>b.p-a.p).slice(0,8),dogs=pool.filter(r=>r.odds>0&&r.p>=.35).sort((a,b)=>b.p-a.p).slice(0,8);
  tickets=pCombinations([...favorites,...dogs],3).filter(t=>t.legs.filter(r=>r.odds>0).length===1).sort((a,b)=>b.p-a.p);
 }
 return tickets.slice(0,3);
}
function pReason(r){
 const drivers=r.f.coreContributions.map(x=>({...x,points:x.points*(r.side==='home'?1:-1)})).filter(x=>x.points>0).sort((a,b)=>b.points-a.points);
 const labels={'Elo difference':'team strength','Net success-rate difference':'drive efficiency','Scoring margin difference':'recent scoring','Scoring environment':'scoring environment','Home field':'home field','Explosive-rate difference':'big plays','Yards/game difference':'offensive yardage'};
 return `${r.margin>=0?'Projected to win':'Projected to lose'} by ${Math.abs(r.margin).toFixed(1)}. ${drivers.length?'The strongest positive factor is '+(labels[drivers[0].name]||drivers[0].name.toLowerCase())+'.':''}`;
}
function pCard(t,i){const single=t.legs.length===1;return `<article class="ticket"><div class="ticket-top"><span>${single?'SINGLE PICK':t.legs.length+'-LEG PARLAY'} · ${esc(t.legs[0].o.provider)}</span><b>#${i+1}</b></div><div class="ticket-pay"><strong>${pAmerican(t.decimal)}</strong><span>${single?'Quoted moneyline':'Calculated combined odds'}</span></div><div class="ticket-metrics"><div><b>${pPercent(t.p)}</b><small>${single?'Model win chance':'Estimated all-legs hit chance*'}</small></div><div><b>$${(10*t.decimal).toFixed(2)}</b><small>Total return on $10 · includes stake</small></div></div><div class="ticket-risk">${pPercent(1-t.p)} estimated chance of losing${single?'':' at least one leg'}.</div><div class="ticket-legs">${t.legs.map(r=>`<div class="ticket-leg"><div class="ticket-team">${logo(r.team)}<div><b>${esc(name(r.team))}</b><small>TO WIN · ${r.odds>0?'+':''}${r.odds}</small></div><span>${pPercent(r.p)}</span></div><p class="ticket-match">${esc(name(r.g.away))} at ${esc(name(r.g.home))}<br>${esc(new Date(r.o.date).toLocaleString('en-US',{timeZone:'America/New_York',weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}))} ET · ${esc(r.o.channels.length?r.o.channels.join(' / '):channel(r.g))}</p><p>${esc(pReason(r))}</p><button class="ticket-report" data-pmatch="${esc(r.id)}">Matchup report ↗</button><details><summary>Price & source</summary><p>Break-even at this price: ${pPercent(1/r.decimal)}. Model: ${pPercent(r.p)}. Difference: ${(r.edge*100).toFixed(1)} percentage points. This comparison does not establish a betting edge.</p><p>Retrieved ${esc(new Date(r.o.retrievedAt).toLocaleString('en-US',{timeZone:'America/New_York'}))} ET. <a href="${esc(r.o.url)}" target="_blank" rel="noreferrer">ESPN game source ↗</a></p></details></div>`).join('')}</div><div class="ticket-bottom"><span>Profit if it wins: <b>$${(10*(t.decimal-1)).toFixed(2)}</b></span><button data-pticket="${i}" class="ticket-save">Save ticket ↓</button></div></article>`}
function pRender(){
 const week=$('parlayWeek').value,pool=pCandidates(week),cat=parlayCategories.find(c=>c.id===parlayCategory);
 parlayTickets=pBuild(parlayCategory,pool);
 $('parlayCats').innerHTML=parlayCategories.map(c=>`<button aria-pressed="${c.id===parlayCategory}" class="${c.id===parlayCategory?'selected':''}" data-pcategory="${c.id}"><span>${c.icon} / ${c.tag}</span><b>${c.name}</b></button>`).join('');
 $('parlayHeading').textContent=cat.name;$('parlayDescription').textContent=cat.desc;
 $('parlayCount').textContent=new Set(pool.map(r=>r.id)).size+' priced upcoming games';
 $('parlayCards').innerHTML=parlayTickets.length?parlayTickets.map(pCard).join(''):'<article class="parlay-empty"><h3>No qualifying tickets yet.</h3><p>Try another category or week. Games need a known kickoff, an unstarted game and moneylines retrieved within 72 hours. We won’t fill a ticket with unavailable odds.</p></article>';
 $('parlayUpdated').textContent=`Odds retrieved ${new Date(parlayOdds.retrievedAt).toLocaleString('en-US',{timeZone:'America/New_York'})} ET · Model results through ${parlayOdds.modelAsOf}. Saved snapshots, not a live feed.`;
}
function pSave(index){const t=parlayTickets[index];if(!t)return;const text=['DART MODEL · '+parlayCategories.find(c=>c.id===parlayCategory).name,pWeekLabel($('parlayWeek').value),...t.legs.map(r=>`${name(r.team)} to win (${r.odds>0?'+':''}${r.odds}) — ${name(r.g.away)} at ${name(r.g.home)} — ${r.o.date}`),`Combined odds: ${pAmerican(t.decimal)}; estimated chance: ${pPercent(t.p)}.`,`$10 example total return: $${(10*t.decimal).toFixed(2)} including stake.`,`Probability assumes independent games. Snapshot odds, not a sportsbook ticket. Model data through ${parlayOdds.modelAsOf}; odds retrieved ${parlayOdds.retrievedAt}.`].join('\n');const url=URL.createObjectURL(new Blob([text],{type:'text/plain'})),a=document.createElement('a');a.href=url;a.download='dart-model-ticket.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('parlaySaveStatus').textContent='Ticket downloaded.'}
async function initParlays(){
 const link=document.createElement('link');link.rel='stylesheet';link.href='parlays.css';document.head.append(link);
 const button=document.createElement('button');button.dataset.tab='parlays';button.textContent='02 / Picks & Parlays';const nav=document.querySelector('nav');nav.insertBefore(button,nav.children[1]);button.addEventListener('click',()=>{tab('parlays');if(parlayOdds)pRender()});
 [...nav.children].forEach((b,i)=>b.textContent=String(i+1).padStart(2,'0')+' / '+b.textContent.split(' / ')[1]);
 const section=document.createElement('section');section.id='parlays';section.className='tab';section.hidden=true;section.innerHTML='<article><h2>Building the weekly ticket board…</h2></article>';document.querySelector('footer').before(section);
 try{
  await initialDataReady;if(!D||!M)throw Error('Model data unavailable');const res=await fetch('parlay-odds.json');if(!res.ok)throw Error('Odds unavailable');parlayOdds=await res.json();
  const currentWeek=pWeek(Date.now()),weeks=[...new Set([currentWeek,...Object.values(parlayOdds.games).map(o=>pWeek(o.date)).filter(w=>w>=currentWeek)])].sort();
  section.innerHTML=`<div class="parlay-hero"><div><div class="eyebrow">THE WEEKLY TICKET BOARD</div><h2>Pick your<br><em>Saturday story.</em></h2><p>Five ways to read the slate. Every pick has a reason.</p><span class="parlay-label">MONEYLINE PICKS · WIN THE GAME OUTRIGHT</span></div><div class="parlay-week"><label>Choose your week<select id="parlayWeek">${weeks.map(w=>`<option value="${w}">${pWeekLabel(w)}</option>`).join('')}</select></label><span id="parlayCount"></span><div class="parlay-stamp">DART<br><small>PICKS DESK</small></div></div></div><div id="parlayCats" class="parlay-categories"></div><div class="parlay-sectionhead"><div><h2 id="parlayHeading"></h2><p id="parlayDescription"></p></div><span class="pill">$10 PAYOUT EXAMPLES</span></div><p id="parlayUpdated" class="tiny"></p><div class="parlay-note">Model-ranked ideas, not proven profitable bets. Prices can change. Check current odds and availability before using a pick.</div><div id="parlayCards" class="parlay-grid"></div><p role="status" id="parlaySaveStatus"></p><details class="technical parlay-method"><summary>How these tickets are built</summary><p>All picks use the current main model, not the experimental history model. Straight picks require at least 50% model win chance and a positive difference from the quoted break-even chance. Each category uses the selection rule shown above it.</p><p>*Parlay hit chance multiplies the individual probabilities, assuming independent games. Shared model errors can make that estimate unreliable. We allow one pick per game, no repeated teams, and one sportsbook provider per ticket. Different tickets may overlap; they are alternatives, not a diversified portfolio.</p><p>Combined odds multiply the decimal moneylines. Returns are examples for $10, including stake, before any taxes or adjustments. They are not a bookmaker quote for the complete parlay. A void leg changes the ticket and return under the sportsbook’s rules.</p><p>These ticket categories have not been backtested. The underlying winner model was correct in 65.4% of its 182-game historical test; that is not a parlay success rate. Injury effects are not fitted. Odds snapshots expire from this board after 72 hours; games disappear at their scheduled kickoff. Refreshing the page does not refresh source data.</p></details>`;
  $('parlayWeek').addEventListener('change',pRender);section.addEventListener('click',e=>{const category=e.target.closest('[data-pcategory]'),report=e.target.closest('[data-pmatch]'),save=e.target.closest('[data-pticket]');if(category){parlayCategory=category.dataset.pcategory;pRender()}if(report){$('matchConference').value='all';fillGames();show(report.dataset.pmatch);tab('lab');window.scrollTo({top:200,behavior:'smooth'})}if(save)pSave(Number(save.dataset.pticket))});pRender();setInterval(pRender,60000);
 }catch(e){section.innerHTML='<article><h2>The ticket board couldn’t load.</h2><p>Please reload the page to try again.</p></article>';console.error(e)}
}
initParlays();
