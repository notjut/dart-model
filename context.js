/* Matchup-specific evidence: never silently changes a calibrated forecast. */
let contextData={}, environmentData={}, availabilityData={}, coachChangeData={};
const contextLabels={injuries:'Player availability · centers, OL & DL',qb:'Quarterback experience',situations:'Schedule, rematches & stakes',stadium:'Stadium & home/road history',specialTeams:'Kicking & special teams',weather:'Game-day weather',travel:'Travel & body-clock time',coaching:'Coaching matchup'};
let contextLoaded=false;
function matchupCoverage(g,c={},a={},teamName=id=>id){
 const sides=[['away',g.away],['home',g.home]],pending=[],missing=[],confirmed=[];
 for(const [side,id] of sides){const report=a[side];if(report?.status==='pending')pending.push(teamName(id));else if(report?.status!=='reported')missing.push(teamName(id));else confirmed.push(teamName(id));}
 const parts=[];
 if(pending.length)parts.push(`Injury reports are still pending for ${pending.join(' and ')}.`);
 if(missing.length)parts.push(`No verified injury report is loaded for ${missing.join(' and ')}.`);
 if(confirmed.length)parts.push(`Official availability reports are loaded for ${confirmed.join(' and ')}.`);
 const qb=c.sections?.qb?.items||[],unconfirmed=sides.filter(([,id])=>!qb.some(p=>p.team===id&&p.starterConfirmed===true));
 if(unconfirmed.length===2)parts.push(qb.some(p=>Number(p.appearances)>0)?'QB statistics are loaded; this game’s starters are not confirmed.':'Starting-QB information is not verified for this game.');
 else if(unconfirmed.length)parts.push(`${teamName(unconfirmed[0][1])}’s starting QB is not confirmed.`);
 else parts.push('Both starting QBs are confirmed in the loaded reports.');
 parts.push('Injuries and QB changes do not yet change the projected score.');
 return parts.join(' ');
}
if(typeof module!=='undefined')module.exports={matchupCoverage};
function contextSource(s){const url=s.url||s.sourceUrl;return url&&/^https?:\/\//.test(url)?`<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(s.label||'Source')}</a>`:''}
function coachRecord(r){return `${r.wins}–${r.losses}${r.ties?'–'+r.ties:''}`;}
function coachHistoryHTML(history,rows){
 const all=history.fbs,ats=all.atsWins+all.atsLosses+all.atsPushes;
 const stats=[['WON THE GAME',coachRecord(all),`${all.games} games vs. FBS opponents`],['BEAT THE SPREAD',`${all.atsWins}–${all.atsLosses}${all.atsPushes?'–'+all.atsPushes:''}`,`${ats} archived lines · ${all.missingLines} unavailable`],['UNDERDOGS WON OUTRIGHT',coachRecord(history.underdogs),`${history.underdogs.games} games with a verified underdog`]];
 return `<div class="coach-records">${stats.map(([label,value,note])=>`<div><small>${label}</small><b>${value}</b><span>${note}</span></div>`).join('')}</div><p class="tiny">Home: ${coachRecord(history.home)}. Road: ${coachRecord(history.road)}. Home underdogs: ${coachRecord(history.homeUnderdogs)} outright. Within 7 days: ${coachRecord(history.withinSevenDays)}; after a longer break: ${coachRecord(history.afterLongerBreak)}.</p><details class="coach-games"><summary>See every first game and its sources</summary><div class="tablewrap"><table><thead><tr><th>Team / coach change</th><th>First game</th><th>Final / result</th><th>Team’s spread / result</th></tr></thead><tbody>${rows.filter(r=>r.completed&&r.changeType==='dismissal'&&r.fbsOpponent).map(r=>`<tr><td><b>${esc(r.teamName)} · ${r.season}</b><br>${esc(r.outgoingCoach)} → ${esc(r.interimCoach)}<br>${contextSource({url:r.sourceUrl,label:'School announcement'})}</td><td>${esc(r.gameLocalDate||r.gameDate.slice(0,10))}<br>${r.location==='away'?'@':r.location==='neutral'?'Neutral vs.':'vs.'} ${esc(r.opponentName)}</td><td>${r.scoreFor}–${r.scoreAgainst} · ${r.won?'W':'L'}<br>${contextSource({url:r.gameUrl,label:'Game result'})}</td><td>${r.teamSpread===null?'No archived line':`${r.teamSpread>0?'+':''}${r.teamSpread} · ${r.ats==='win'?'Covered':r.ats==='loss'?'Missed':'Push'}`}<br>${esc(r.quote?.provider||'')}</td></tr>`).join('')}</tbody></table></div></details><p class="tiny">Verified sample, not every firing in college football. First game after an immediate dismissal; FCS opponents and mutual departures are excluded from these totals. Archived lines were retrieved after the games; this is historical context, not our model’s betting record.</p>`;
}
function renderCoachChanges(f){
 const mount=$('coachChangeReport');if(!mount)return;
 const active=coachChangeData.games?.[f.id];mount.innerHTML='';
 if(active){
  const rows=(coachChangeData.rows||[]).filter(r=>r.completed&&r.gameDate<game(f).date);
  mount.innerHTML=`<section class="coach-change-note"><div class="eyebrow">NEW COACH · FIRST GAME</div>${active.events.map(e=>{const repeat=rows.filter(r=>r.team===e.team&&r.opponent===e.opponent&&r.changeType==='dismissal');return `<h3>${esc(e.teamName)} is changing coaches.</h3><p>${esc(e.outgoingCoach)} ${e.changeType==='dismissal'?'was dismissed':'departed by mutual agreement'} on ${esc(e.date)}. This is ${esc(e.interimCoach)}’s first game in charge.</p>${repeat.map(r=>`<p><b>Same-school history:</b> In ${r.season}, ${esc(r.teamName)} ${r.won?'beat':'lost to'} ${esc(r.opponentName)} ${r.scoreFor}–${r.scoreAgainst} in its first game after dismissing ${esc(r.outgoingCoach)}. ${contextSource({url:r.gameUrl,label:'See that game'})}</p>`).join('')}${contextSource({url:e.sourceUrl,label:'Official coaching announcement'})}`;}).join('')}<h4>What happened after other firings?</h4>${coachHistoryHTML(active.history,rows)}<p class="coach-model-use"><b>Score impact:</b> No adjustment to the main pick yet. ${M.coachChangeTrial?.testedGamesWithChange??0} comparable firing games are in the current-season prediction test; that is too little to establish a reliable scoring adjustment.${M.coachChangeTrial?.testedGamesWithChange>0&&M.coachChangeTrial.candidateMarginMAE>=M.coachChangeTrial.baselineMarginMAE?' Adding the factor did not improve those trial forecasts.':''}</p></section>`;
 }
 let study=$('coachChangeStudy');if(!study&&coachChangeData.cohorts){study=document.createElement('article');study.id='coachChangeStudy';$('method').prepend(study);}
 if(study&&coachChangeData.cohorts)study.innerHTML=`<div class="eyebrow">THE COACHING CHANGE FILE</div><h2>The first game after a firing.</h2><p>${coachChangeData.eventsVerified} school-sourced coaching changes checked. The history below separates winning the game from beating the spread.</p>${coachHistoryHTML(coachChangeData.cohorts,coachChangeData.rows)}<p class="tiny">The first-game indicator is included in a separate model test at each refresh. It has not earned a numerical adjustment in the main model. Existing picks are not rewritten after the result.</p>`;
}

function renderMatchupContext(f){
 const node=document.getElementById('contextCards');if(!node||!f)return;
 const g=game(f),c=contextData.games?.[f.id],env=environmentData.games?.[f.id];
 const coverage=document.getElementById('matchCoverage');if(coverage)coverage.textContent=contextLoaded?matchupCoverage(g,c,availabilityData.games?.[f.id],name):'Checking injury reports and starting-QB confirmation.';
 renderCoachChanges(f);
 const sections={...(c?.sections||{}),...(env?.sections||{})};
 if(c?.sections?.coaching&&env?.sections?.coaching)sections.coaching={...c.sections.coaching,items:[...(c.sections.coaching.items||[]),...(env.sections.coaching.items||[])],sources:[...(c.sections.coaching.sources||[]),...(env.sections.coaching.sources||[])]};
 const availabilityItems=[];
 for(const t of [g.away,g.home]){
  const availabilityGame=availabilityData.games?.[f.id];const a=availabilityGame?.[t===g.home?'home':'away'];if(!a)continue;
  availabilityItems.push({title:name(t),text:(a.summary||a.status||'Availability report')+(a.reportPublished?' Report published '+a.reportPublished+'.':''),sourceUrl:a.sourceUrl,observedAt:a.retrievedAt});
  for(const p of (a.concerns||a.players||a.items||[]))availabilityItems.push({title:p.name||p.title||'Player report',text:p.text||[p.position,p.status,p.detail,p.roleEvidence?'Center role verified by official team bio':null].filter(Boolean).join(' · '),sourceUrl:p.roleEvidence?.url||p.sourceUrl||a.sourceUrl,observedAt:a.retrievedAt});
 }
 if(availabilityItems.length)sections.injuries={...(sections.injuries||{}),summary:'Latest retrieved availability evidence. An omitted player is not automatically healthy. A listed lineman is not automatically a starter.',items:availabilityItems,sources:[...(availabilityData.games?.[f.id]?.home?.sources||[]),...(availabilityData.games?.[f.id]?.away?.sources||[])],status:availabilityData.games?.[f.id]?.status||'unverified'};
 if(!availabilityItems.length&&availabilityData.games?.[f.id]?.note)sections.injuries={...(sections.injuries||{}),status:'not_reported',summary:availabilityData.games[f.id].note};
 const times=[contextData.generatedAt,environmentData.generatedAt,availabilityData.generatedAt].filter(Boolean);
 document.getElementById('contextStatus').innerHTML=`<p class="tiny">${times.length?'Research retrieved '+esc(new Date(times.sort()[0]).toLocaleString('en-US',{timeZone:'America/New_York'}))+' ET':'Research not loaded'}. Main forecast uses results through ${esc(D.asOf)}. Historical evaluation remains frozen through ${esc(M.evaluationFrozenThrough||M.testEnd)}. <b>These are matchup facts and warning signs; no untested point bonuses are added.</b></p>`;
 node.innerHTML=Object.entries(contextLabels).map(([k,label])=>{const s=sections[k];if(!s)return `<section class="context-card"><h3>${label}</h3><p>No verified report retrieved for this matchup. This factor does not change the score.</p></section>`;return `<section class="context-card"><h3>${label}</h3><span class="pill">${esc(({available:'Data available',partial:'Partial coverage',unverified:'Not verified',reported:'Official report',not_reported:'Report not available',pending:'Report pending'})[s.status]||s.status||'Context only')}</span><p>${esc(s.summary||'')}</p>${(s.items||[]).map(i=>`<div class="context-item"><b>${esc(i.title||'')}</b><p>${esc(i.text||'')}</p>${contextSource(i)}${i.observedAt?` <small>Retrieved ${esc(new Date(i.observedAt).toLocaleDateString('en-US'))}</small>`:''}</div>`).join('')}${(s.sources||[]).length?`<details><summary>Sources & coverage</summary>${s.sources.map(contextSource).filter(Boolean).join(' · ')}</details>`:''}</section>`}).join('');
}
async function loadMatchupContext(){
 const files=['matchup-context.json','matchup-environment.json','availability.json','coach-change-history.json'];
 const loaded=await Promise.all(files.map(async file=>{try{const r=await fetch(file,{cache:'no-cache'});if(!r.ok)throw Error(file);return await r.json()}catch(e){console.warn('Research source unavailable',file);return {}}}));
 [contextData,environmentData,availabilityData,coachChangeData]=loaded;contextLoaded=true;
 await initialDataReady;renderMatchupContext(current);
}
if(typeof document!=='undefined')loadMatchupContext();
