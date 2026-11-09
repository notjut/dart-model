/* Current rankings are display context, not new inputs to Darkhorse predictions. */
(function(root){
'use strict';
const escape=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let snapshot={};
const date=x=>Number.isFinite(Date.parse(x))?new Date(x).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}):'date unavailable';
function state(source,kind='fpi',now=Date.now()){
 if(!source||!['current','stale'].includes(source.status))return 'unavailable';
 const retrieved=Date.parse(source.retrievedAt),published=Date.parse(source.publishedAt);
 return source.status==='stale'||!Number.isFinite(retrieved)||!Number.isFinite(published)||now-retrieved>30*3600000||retrieved>now+300000||published>now+300000||now-published>(kind==='fpi'?7:14)*86400000?'stale':'current';
}
function badges(team,historical=false,data=snapshot,now=Date.now()){
 const chips=[];
 for(const kind of ['fpi','cfp']){
  const source=data[kind],status=state(source,kind,now),rank=source?.ranks?.[String(team)];
  if(Number.isInteger(rank)&&rank>0&&status!=='unavailable'){
   const label=kind.toUpperCase(),old=status==='stale';
   chips.push(`<span class="rank-chip rank-${kind}${old?' rank-stale':''}" title="${label}: ${kind==='fpi'?'ESPN team-strength ranking':'College Football Playoff committee ranking'}. Published ${escape(date(source.publishedAt))}.${old?' Older snapshot; refresh needed.':''}">${label} #${rank}${old?' · older':''}</span>`);
  }else if(kind==='fpi')chips.push('<span class="rank-chip rank-missing" title="No verified ESPN FPI rank is available for this team">FPI —</span>');
  else if(status==='unavailable')chips.push('<span class="rank-chip rank-missing" title="The CFP poll could not be verified">CFP unavailable</span>');
 }
 return `<span class="team-ranks" aria-label="${historical?'Current team rankings, not game-day rankings':'Team rankings'}">${historical?'<span class="rank-current">Current</span>':''}${chips.join('')}</span>`;
}
function text(team,data=snapshot){const labels=['fpi','cfp'].flatMap(k=>{const rank=data[k]?.ranks?.[String(team)],s=state(data[k],k);return Number.isInteger(rank)&&s!=='unavailable'?[`${k.toUpperCase()} #${rank}${s==='stale'?' (older)':''}`]:k==='fpi'?['FPI unavailable']:[];});return labels.join(' · ');}
function cardRanks(team,historical=false,data=snapshot,now=Date.now()){
 const rows=['fpi','ap','cfp'].map(kind=>{
  const source=data[kind],status=state(source,kind,now),rank=source?.ranks?.[String(team)],label=kind.toUpperCase();
  const available=status!=='unavailable',value=available&&Number.isInteger(rank)?'#'+rank:available&&kind!=='fpi'?'NR':'—';
  const detail=!available?'Ranking unavailable':value==='NR'?'Not ranked in the Top 25':'Rank '+rank;
  const title=label+': '+detail+(status==='stale'?'. Older snapshot':'')+(historical?'. Current ranking, not game-day ranking':'');
  return `<span title="${escape(title)}" aria-label="${escape(title)}"><small>${label}</small><b>${value}${status==='stale'?'<sup>*</sup>':''}</b></span>`;
 });
 return `<div class="gd-school-ranks" aria-label="${historical?'Current rankings':'Team rankings'}">${rows.join('')}</div>`;
}
function legend(data=snapshot){return `<div class="ranking-key"><b>THE RANKINGS</b><span><a href="https://www.espn.com/college-football/fpi" target="_blank" rel="noreferrer">FPI</a> = ESPN’s team-strength rank <span class="rank-date">${escape(date(data.fpi?.publishedAt))}${state(data.fpi)!=='current'?' · '+state(data.fpi):''}</span></span><span><a href="https://www.espn.com/college-football/rankings" target="_blank" rel="noreferrer">CFP</a> = playoff committee’s Top 25 <span class="rank-date">${escape(date(data.cfp?.publishedAt))}${state(data.cfp,'cfp')!=='current'?' · '+state(data.cfp,'cfp'):''}</span></span><span><a href="https://www.espn.com/college-football/rankings" target="_blank" rel="noreferrer">AP</a> = Associated Press Top 25 <span class="rank-date">${escape(date(data.ap?.publishedAt))}${state(data.ap,'ap')!=='current'?' · '+state(data.ap,'ap'):''}</span></span><span class="ranking-key-note">NR = unranked. — = unavailable. * = older ranking snapshot. Lower is better. CFP badge appears only for ranked teams.${state(data.cfp,'cfp')==='unavailable'?' CFP source unavailable.':''}</span></div>`;}
const api={badges,text,legend,cardRanks,state,get data(){return snapshot;}};root.TeamRankings=api;
if(typeof module!=='undefined')module.exports=api;
if(typeof document==='undefined')return;
api.ready=(async()=>{try{const r=await fetch('team-rankings.json',{cache:'no-cache',signal:AbortSignal.timeout(12000)});if(!r.ok)throw Error('Rankings unavailable');const value=await r.json();if(!value.runId||!value.coverage)throw Error('Invalid ranking snapshot');snapshot=value;}catch(error){console.warn('Team rankings unavailable:',error.message);}return snapshot;})();
})(globalThis);
