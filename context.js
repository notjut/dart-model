/* Matchup-specific evidence: never silently changes a calibrated forecast. */
let contextData={}, environmentData={}, availabilityData={};
const contextLabels={injuries:'Player availability · centers, OL & DL',qb:'Quarterback experience',situations:'Schedule, rematches & stakes',stadium:'Stadium & home/road history',specialTeams:'Kicking & special teams',weather:'Game-day weather',travel:'Travel & body-clock time',coaching:'Coaching matchup'};
function contextSource(s){const url=s.url||s.sourceUrl;return url&&/^https?:\/\//.test(url)?`<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(s.label||'Source')}</a>`:''}
function renderMatchupContext(f){
 const node=document.getElementById('contextCards');if(!node||!f)return;
 const g=game(f),c=contextData.games?.[f.id],env=environmentData.games?.[f.id];
 const sections={...(c?.sections||{}),...(env?.sections||{})};
 if(c?.sections?.coaching&&env?.sections?.coaching)sections.coaching={...c.sections.coaching,items:[...(c.sections.coaching.items||[]),...(env.sections.coaching.items||[])],sources:[...(c.sections.coaching.sources||[]),...(env.sections.coaching.sources||[])]};
 const availabilityItems=[];
 for(const t of [g.away,g.home]){
  const availabilityGame=availabilityData.games?.[f.id];const a=availabilityGame?.[t===g.home?'home':'away'];if(!a)continue;
  availabilityItems.push({title:name(t),text:a.summary||a.status||'Availability report',sourceUrl:a.sourceUrl,observedAt:a.observedAt});
  for(const p of (a.concerns||a.players||a.items||[]))availabilityItems.push({title:p.name||p.title||'Player report',text:p.text||[p.position,p.status,p.detail,p.roleEvidence?'Center role verified by official team bio':null].filter(Boolean).join(' · '),sourceUrl:p.roleEvidence?.url||p.sourceUrl||a.sourceUrl,observedAt:p.observedAt||a.observedAt});
 }
 if(availabilityItems.length)sections.injuries={...(sections.injuries||{}),summary:'Latest retrieved availability evidence. An omitted player is not automatically healthy. A listed lineman is not automatically a starter.',items:availabilityItems,sources:[...(availabilityData.games?.[f.id]?.home?.sources||[]),...(availabilityData.games?.[f.id]?.away?.sources||[])],status:'Reported availability'};
 if(!availabilityItems.length&&availabilityData.games?.[f.id]?.note)sections.injuries={...(sections.injuries||{}),status:'not_reported',summary:availabilityData.games[f.id].note};
 const times=[contextData.generatedAt,environmentData.generatedAt,availabilityData.generatedAt].filter(Boolean);
 document.getElementById('contextStatus').innerHTML=`<p class="tiny">${times.length?'Research retrieved '+esc(new Date(times.sort()[0]).toLocaleString('en-US',{timeZone:'America/New_York'}))+' ET':'Research not loaded'}. Main forecast uses results through ${esc(D.asOf)}. <b>These are matchup facts and warning signs; no untested point bonuses are added.</b></p>`;
 node.innerHTML=Object.entries(contextLabels).map(([k,label])=>{const s=sections[k];if(!s)return `<section class="context-card"><h3>${label}</h3><p>No verified report retrieved for this matchup. This factor does not change the score.</p></section>`;return `<section class="context-card"><h3>${label}</h3><span class="pill">${esc(({available:'Data available',partial:'Partial coverage',unverified:'Not verified',reported:'Official report',not_reported:'Report not available'})[s.status]||s.status||'Context only')}</span><p>${esc(s.summary||'')}</p>${(s.items||[]).map(i=>`<div class="context-item"><b>${esc(i.title||'')}</b><p>${esc(i.text||'')}</p>${contextSource(i)}${i.observedAt?` <small>Retrieved ${esc(new Date(i.observedAt).toLocaleDateString('en-US'))}</small>`:''}</div>`).join('')}${(s.sources||[]).length?`<details><summary>Sources & coverage</summary>${s.sources.map(contextSource).filter(Boolean).join(' · ')}</details>`:''}</section>`}).join('');
}
async function loadMatchupContext(){
 const files=['matchup-context.json','matchup-environment.json','availability.json'];
 const loaded=await Promise.all(files.map(async file=>{try{const r=await fetch(file,{cache:'no-cache'});if(!r.ok)throw Error(file);return await r.json()}catch(e){console.warn('Research source unavailable',file);return {}}}));
 [contextData,environmentData,availabilityData]=loaded;
 await initialDataReady;renderMatchupContext(current);
}
loadMatchupContext();
