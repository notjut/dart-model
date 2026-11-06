'use strict';
(function(root){
  const finite=x=>typeof x==='number'&&Number.isFinite(x);
  const avg=xs=>xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:null;
  const one=x=>Number(x).toFixed(1);
  const record=rows=>`${rows.filter(r=>r.pf>r.pa).length}–${rows.filter(r=>r.pf<r.pa).length}`;
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const source=url=>/^https:\/\//.test(url||'')?url:null;
  const evening=g=>g.timeValid===true&&Number(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',hourCycle:'h23'}).format(new Date(g.date)))>=19;
  // Football membership verified for these seasons only. Do not project current
  // conference membership backward through realignment or into future seasons.
  const acc2024to2026=new Set(['103','25','228','150','52','59','97','2390','153','152','221','2567','24','183','258','259','154']);
  const accSource='https://theacc.com/news/2024/8/29/stanford-cal-football-to-kick-off-as-acc-members-this-weekend.aspx';
  function createEngine({data,history,model}){
    const teams=data.teams||{},teamName=id=>teams[id]?.name||id;
    const loaded=new Map((history?.games||[]).map(g=>[String(g.id),g]));
    for(const g of data.games||[])loaded.set(String(g.id),g);
    const all=[...loaded.values()].filter(g=>g.done!==false&&Number.isFinite(Date.parse(g.date))&&finite(g.hs)&&finite(g.as)&&g.hs>=0&&g.as>=0&&g.hs!==g.as).sort((a,b)=>a.date.localeCompare(b.date));
    const dataGames=data.games||[],rankCache=new Map();
    function before(game){
      const input=Date.parse(model.inputRetrievedAt);
      // No future results, and no results on the prediction's game date. Match
      // the model's earlier-date rule rather than leaking same-day outcomes.
      return Math.min(Number.isFinite(input)?input:0,Date.parse(game.date.slice(0,10)+'T00:00:00Z'));
    }
    function rowsFor(id,game,{historical=false,since=game.season}={}){
      const cutoff=before(game);
      return (historical?all:dataGames).filter(g=>g.id!==game.id&&g.done!==false&&g.season>=since&&g.season<=game.season&&Date.parse(g.date)<cutoff&&finite(g.hs)&&finite(g.as)&&g.hs!==g.as&&[g.home,g.away].includes(id)).map(g=>({
        id:g.id,date:g.date,season:g.season,team:id,opponent:g.home===id?g.away:g.home,
        pf:g.home===id?g.hs:g.as,pa:g.home===id?g.as:g.hs,
        location:g.neutral?'neutral':g.home===id?'home':'away',night:evening(g),g,url:g.url
      })).sort((a,b)=>a.date.localeCompare(b.date));
    }
    function defensiveRanks(game){
      const key=game.season+':'+before(game);
      if(rankCache.has(key))return rankCache.get(key);
      const ids=Object.keys(teams).filter(id=>teams[id].conference&&teams[id].conference!=='Non-FBS opponent');
      const entries=[];
      for(const id of ids){
        const rows=rowsFor(id,game),values=rows.map(r=>{const raw=r.g.stats?.[r.opponent]?.yards??r.g.stats?.[r.opponent]?.boxscore?.totalYards;return raw!==''&&raw!==null&&raw!==undefined?Number(raw):NaN;});
        if(rows.length>=3&&values.every(x=>Number.isFinite(x)&&x>=0))entries.push({id,allowed:avg(values),n:rows.length});
      }
      entries.sort((a,b)=>a.allowed-b.allowed);
      const ranks={};
      entries.forEach((r,i)=>{r.rank=i&&r.allowed===entries[i-1].allowed?entries[i-1].rank:i+1;ranks[r.id]=r;});
      const result={ranks,complete:ids.length>=60&&entries.length===ids.length,total:ids.length,ranked:entries.length};
      rankCache.set(key,result);return result;
    }
    function receipt(rows){return rows.map(r=>({id:r.id,date:r.date,team:teamName(r.team),opponent:teamName(r.opponent),pf:r.pf,pa:r.pa,location:r.location,url:r.url,opponentRank:r.opponentRank}));}
    function fact(title,meaning,rows,scope,extra={}){
      return {title,meaning,scope,n:rows.length,games:receipt(rows),caution:rows.length<4?`Only ${rows.length} game${rows.length===1?'':'s'} in this group. Treat this as a clue, not a reliable trend.`:'',...extra};
    }
    function build(f,q,ui){
      const game=dataGames.find(g=>g.id===f.id);
      if(!game)return null;
      const tied=q.margin===0,picked=q.margin>0?game.home:game.away,other=picked===game.home?game.away:game.home;
      const n=teamName(picked),on=teamName(other),p=picked===game.home?q.p:1-q.p;
      const pr=picked===game.home?f.homeProfile:f.awayProfile,op=picked===game.home?f.awayProfile:f.homeProfile;
      const own=rowsFor(picked,game),opponent=rowsFor(other,game),support=[],risks=[],context=[],gaps=[];
      const season=String(game.season),scope=`${season} season · completed games before this forecast`;
      const headline=tied?'The model has this game even.':ui.market&&ui.team===picked?`Darkhorse picks ${n} to win the upset.`:`Darkhorse picks ${n} to win.`;
      const summary=tied?'There is no outright winner pick. The displayed score uses a one-point tiebreak.':`Projected score: ${teamName(game.away)} ${q.a}, ${teamName(game.home)} ${q.h}. ${n} has an estimated ${Math.round(p*100)}% chance to win. ${ui.market&&ui.team===picked?'This is an outright-win pick, not just a pick to cover the spread.':ui.market?`The underdog is ${teamName(ui.team)}; the model is not picking it to win.`:'No posted underdog is established for this matchup.'}`;
      // Put actual scoring production ahead of abstract feature names.
      if(own.length&&opponent.length){
        const scored=avg(own.map(r=>r.pf)),oppScored=avg(opponent.map(r=>r.pf)),allowed=avg(opponent.map(r=>r.pa));
        const better=scored>oppScored;
        (better?support:risks).push(fact(`${n} scores ${one(scored)} points per game; ${on} scores ${one(oppScored)}.`,better?`${n} has produced more points so far. ${on} allows ${one(allowed)} per game, so the model still has to account for the defense in front of it.`:`The pick is not backed by a higher season scoring average. ${on} has the stronger scoring record so far.`,[...own,...opponent],scope,{sample:`${own.length} ${n} games · ${opponent.length} ${on} games`,caution:'These teams faced different schedules. The scoring gap is not a prediction of the final margin.'}));
      }else gaps.push('Not enough completed scoring results for both teams.');
      if(pr?.plays>=80&&op?.plays>=80&&finite(pr.exp)&&finite(op.exp)&&Math.abs(pr.exp-op.exp)>=.01){
        const better=pr.exp>op.exp;
        (better?support:risks).push(fact(`${n} produces a 20-yard gain on about ${Math.round(pr.exp*100)} of every 100 plays; ${on} does it on ${Math.round(op.exp*100)}.`,better?`${n} has been more likely to turn a play into a big gain. That gives it a way to score quickly without needing a long, mistake-free drive.`:`${on} has the stronger big-play record. A few long gains could turn this game against the pick.`,[...own,...opponent],scope,{sample:`${pr.plays} ${n} offensive plays · ${op.plays} ${on} offensive plays`,caution:'These are the model’s season estimates, including a small-sample adjustment. Different opponents can affect the comparison.',modelUse:'Big-play rate is an input to the main score model.'}));
      }
      if(pr?.n&&op?.n&&finite(pr.margin)&&finite(op.margin)){
        const favorable=pr.margin>op.margin;
        const text=x=>x>=0?`outscored opponents by ${one(x)}`:`been outscored by ${one(-x)}`;
        (favorable?support:risks).push(fact(`In its last ${pr.n} games, ${n} has ${text(pr.margin)} points per game.`,`${on} has ${text(op.margin)} over its last ${op.n}. ${favorable?'Recent scoring results help explain the pick.':'Recent scoring results work against the pick.'}`,[...rowsFor(picked,game,{since:game.season-1}).slice(-pr.n),...rowsFor(other,game,{since:game.season-1}).slice(-op.n)],'Recent results · may include the previous season',{sample:`${pr.n} ${n} games · ${op.n} ${on} games`,modelUse:'Recent scoring margin is an input to the main score model.'}));
      }
      if(pr?.plays>=80&&op?.plays>=80&&finite(pr.net)&&finite(op.net)){
        const gap=100*(pr.net-op.net);
        if(Math.abs(gap)<1){
          risks.push(fact('Both teams are about even at keeping drives moving and getting stops.',`When we compare each offense with its own defense, the gap between the teams is only ${one(Math.abs(gap))} percentage points. That is too small to describe as a major advantage for either team.`,[...own,...opponent],scope,{sample:`${pr.plays} ${n} offensive plays · ${op.plays} ${on} offensive plays`,caution:`${n}: ${one(pr.net*100)} percentage points of net success rate. ${on}: ${one(op.net*100)}. A successful play gains enough yards to keep a drive on track. Model rates include a small-sample adjustment.`,modelUse:'This rate is in the score model. A tiny difference is not labeled a major advantage.'}));
        }else{
          (gap>0?support:risks).push(fact(`${gap>0?n:on} has the better drive-efficiency balance.`,`${n}’s offense keeps about ${Math.round(pr.sr*100)} of every 100 plays on track; its defense allows about ${Math.round(pr.dsr*100)}. ${on}: ${Math.round(op.sr*100)} on offense and ${Math.round(op.dsr*100)} allowed. ${gap>0?'That balance supports the pick.':'That balance is a reason the pick could lose.'}`,[...own,...opponent],scope,{sample:`${pr.plays} / ${op.plays} offensive plays`,caution:'Rates are model estimates with a small-sample adjustment. Opponent strength is handled separately.'}));
        }
      }
      const ranks=defensiveRanks(game),oppRank=ranks.ranks[other];
      if(ranks.complete&&oppRank){
        const weak=own.filter(r=>ranks.ranks[r.opponent]?.rank>=60).map(r=>({...r,opponentRank:ranks.ranks[r.opponent].rank}));
        if(weak.length>=3){
          const scored=avg(weak.map(r=>r.pf));
          const relevant=oppRank.rank>=60;
          const item=fact(`${n} averages ${one(scored)} points against defenses ranked 60th or worse in our current table.`,`${on} ranks ${oppRank.rank} of ${ranks.total} in yards allowed per game. ${relevant?`${on} falls in that group, giving us a relevant scoring comparison.`:'It is outside that group, so those scoring results do not establish the same advantage here.'}`,weak,`${season} · our yards-allowed ranking as of ${model.asOf||data.asOf}`,{modelUse:'Extra matchup context; this group is not an extra score bonus.',caution:`${weak.length} games. Rankings use the current saved results, not each opponent’s ranking on game day. This is our calculation, not an official NCAA ranking.`,rankCoverage:{ranked:ranks.ranked,total:ranks.total}});
          if(relevant){if(scored<avg(own.map(r=>r.pf))){item.meaning+=` That is below ${n}’s overall ${one(avg(own.map(r=>r.pf)))}-point average, so these results do not support assuming a scoring explosion.`;risks.push(item);}else support.push(item);}else context.push(item);
        }else gaps.push(`${n} has fewer than three loaded games against defenses ranked 60th or worse. No scoring trend is claimed.`);
      }else gaps.push('The full FBS yards-allowed table is incomplete. No “ranked 60th or worse” claim is shown.');
      if(!game.neutral){
        for(const [id,rows] of [[picked,own],[other,opponent]]){
          const atHome=id===game.home,split=rows.filter(r=>r.location===(atHome?'home':'away'));
          if(!split.length)continue;
          const nm=teamName(id),wins=split.filter(r=>r.pf>r.pa).length,margin=avg(split.map(r=>r.pf-r.pa));
          const item=fact(`${nm} is ${record(split)} ${atHome?'at home':'on the road'}, scoring ${one(avg(split.map(r=>r.pf)))} and allowing ${one(avg(split.map(r=>r.pa)))} per game.`,`${atHome?'Home':'Road'} results are the relevant split for this matchup. ${wins===split.length?'It has won every loaded game in this setting.':wins===0?'It has not won in this setting in the loaded season.':`It has won ${wins} of ${split.length} in this setting.`}`,split,scope,{modelUse:'Venue records explain the matchup; they are not added as extra points.'});
          ((id===picked?margin>0:margin<0)?support:risks).push(item);
          if(evening(game)){
            const nights=split.filter(r=>r.night);
            if(nights.length)context.push(fact(`${nm} is ${record(nights)} in ${atHome?'home':'road'} games starting at 7 p.m. ET or later.`,`${game.season} results in the same home/road and kickoff-time group. This is a record, not proof that the time caused the outcome.`,nights,scope,{caution:`${nights.length} games. “Evening” uses Eastern time, not local stadium darkness. Unconfirmed kickoff times are excluded.`}));
          }
        }
      }
      const selectedOppConference=teams[other]?.conference;
      if(selectedOppConference&&selectedOppConference!=='Non-FBS opponent'&&!selectedOppConference.includes('Independent')){
        const acc=selectedOppConference==='Atlantic Coast Conference'&&game.season>=2024&&game.season<=2026;
        const rows=rowsFor(picked,game,{historical:acc,since:acc?2024:game.season}).filter(r=>acc?acc2024to2026.has(r.opponent):teams[r.opponent]?.conference===selectedOppConference);
        if(rows.length)(rows.filter(r=>r.pf>r.pa).length<rows.length/2?risks:context).push(fact(`${n} is ${record(rows)} against ${acc?'ACC':({'Southeastern Conference':'SEC','Big Ten Conference':'Big Ten','Big 12 Conference':'Big 12','Pac-12 Conference':'Pac-12','American Conference':'American','Conference USA':'CUSA','Mid-American Conference':'MAC','Mountain West Conference':'Mountain West','Sun Belt Conference':'Sun Belt'}[selectedOppConference]||selectedOppConference)} teams ${acc?'since 2024':`in ${season}`}.`,`${on} plays in that conference. This shows how ${n} has fared against that group; it does not make those teams interchangeable with ${on}.`,rows,acc?'2024 through the saved forecast · loaded meetings':scope,{caution:`${rows.length} meetings. Schedules may omit postseason games. Different coaches and rosters can limit the comparison.`,membershipSource:acc?accSource:null}));
      }
      for(const [id,rows] of [[picked,own],[other,opponent]]){
        const ordered=[...rows].sort((a,b)=>a.date.localeCompare(b.date)),last=ordered.at(-1);
        if(!last)continue;
        const won=last.pf>last.pa,after=ordered.filter((r,i)=>i>0&&(ordered[i-1].pf>ordered[i-1].pa)===won);
        if(after.length)context.push(fact(`${teamName(id)} is ${record(after)} in games after a ${won?'win':'loss'} this season.`,`${teamName(id)} just ${won?'beat':'lost to'} ${teamName(last.opponent)} ${last.pf}–${last.pa}. That makes this the relevant after-result group.`,after,scope,{caution:`${after.length} games. This does not prove momentum or a letdown.`}));
      }
      const series=rowsFor(picked,game,{historical:true,since:Math.max(history?.startSeason||2016,game.season-10)}).filter(r=>r.opponent===other);
      if(series.length)context.push(fact(`${n} is ${record(series)} in ${series.length} loaded meetings with ${on} since ${Math.min(...series.map(r=>r.season))}.`,'Actual head-to-head results. Older games are background—not proof that today’s players or coaches have the same advantage.',series,'Loaded head-to-head history · before this forecast',{caution:history?.failures?.length?'Some history sources failed; coverage is incomplete.':'Postseason coverage may be incomplete.'}));
      else gaps.push(`No completed ${n}–${on} meeting was found in the loaded history window.`);
      if(f.reviewRequired)risks.unshift(fact('A reported quarterback concern needs a fresh check.','This game is flagged for availability review. The projection does not establish who will start.',[],'Current availability review',{caution:'Do not read missing injury reports as a healthy roster.'}));
      // Do not suppress contrary evidence just because a model selected this team.
      if(!risks.length)risks.push(fact('This is still a forecast, not a lock.',`The model gives ${on} about a ${Math.round((1-p)*100)}% chance to win. A favorite or underdog can outperform its past averages.`,[], 'Model estimate',{caution:''}));
      return {research:f.upsetResearch,homeName:teamName(game.home),awayName:teamName(game.away),headline,summary,picked,tied,support,risks,context,gaps,season,cutoff:new Date(before(game)).toISOString(),facts:support.length+risks.length,modelNote:'The main score and win chance are unchanged. Season splits and historical groups provide context; they do not create extra point bonuses. Missing injury or starting-QB information is not treated as confirmation of a healthy lineup.'};
    }
    return {build,rowsFor,defensiveRanks};
  }
  function renderFact(f){
    const games=f.games||[];
    return `<li class="brief-fact"><strong>${esc(f.title)}</strong><p>${esc(f.meaning)}</p><details class="brief-receipt"><summary>${esc(f.sample||`${f.n} game${f.n===1?'':'s'}`)} · see the evidence</summary><p>${esc(f.scope)}</p>${f.caution?`<p>${esc(f.caution)}</p>`:''}${f.modelUse?`<p>${esc(f.modelUse)}</p>`:''}${games.length?`<ul>${games.map(g=>`<li>${source(g.url)?`<a href="${esc(g.url)}" target="_blank" rel="noreferrer">`:''}${esc(g.date.slice(0,10))} · ${esc(g.team)} ${g.pf}–${g.pa} ${esc(g.opponent)} · ${esc(g.location)}${g.opponentRank?` · opponent defense #${g.opponentRank}`:''}${source(g.url)?'</a>':''}</li>`).join('')}</ul>`:''}${source(f.membershipSource)?`<a href="${esc(f.membershipSource)}" target="_blank" rel="noreferrer">Conference membership source ↗</a>`:''}</details></li>`;
  }
  function render(brief){
    if(!brief)return '<p>The matchup explanation could not be loaded.</p>';
    return `<div class="matchup-brief"><section aria-label="Reasons behind the pick"><h4>${brief.tied?'Why this is close':'The case for the pick'}</h4><ul class="brief-list">${brief.support.map(renderFact).join('')||'<li>No strong supporting comparison is available in the loaded data.</li>'}</ul></section><section class="brief-risks" aria-label="Reasons the pick could lose"><h4>What could make this pick lose</h4><ul class="brief-list">${brief.risks.map(renderFact).join('')}</ul></section>${brief.context.length?`<details class="brief-context"><summary>More matchup history · ${brief.context.length} facts</summary><ul class="brief-list">${brief.context.map(renderFact).join('')}</ul></details>`:''}${brief.gaps.length?`<details class="brief-context"><summary>What we could not verify</summary><ul>${brief.gaps.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>`:''}${typeof DarkhorseResearch!=='undefined'?DarkhorseResearch.match(brief.research,brief.homeName,brief.awayName):''}<p class="brief-method">${esc(brief.modelNote)}</p></div>`;
  }
  root.DarkhorseBrief={createEngine,render,evening};
  if(typeof module!=='undefined')module.exports=root.DarkhorseBrief;
})(globalThis);
