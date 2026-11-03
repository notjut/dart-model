'use strict';
(function(root){
  const staleHours=30;
  function health(model,now=Date.now()){
    const stamp=Date.parse(model?.inputRetrievedAt||model?.generatedAt);
    const age=(now-stamp)/3600000;
    return {stale:!Number.isFinite(age)||age<-.1||age>staleHours,age,staleHours};
  }
  function weekEnd(asOf){
    const day=new Date(asOf+'T12:00:00Z');
    day.setUTCDate(day.getUTCDate()+((7-day.getUTCDay())%7));
    return day.toISOString().slice(0,10);
  }
  root.DartHealth={health,weekEnd};
  if(typeof module!=='undefined')module.exports=root.DartHealth;
})(globalThis);

if(typeof document!=='undefined'){
  async function loadDailyUpdates(){
    await initialDataReady;
    if(!D||!M)return;
    const banner=document.createElement('aside');
    banner.className='refresh-banner';banner.id='refreshBanner';banner.setAttribute('role','status');
    document.querySelector('nav').before(banner);
    function update(){
      const h=DartHealth.health(M);
      const when=new Date(M.inputRetrievedAt||M.generatedAt).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
      banner.classList.toggle('stale',h.stale);
      banner.textContent=h.stale?`UPDATE OVERDUE · These forecasts use older data (${when} ET). Automated tickets are paused until a successful refresh.`:`DATA CHECKED ${when} ET · ${M.forecasts.length} upcoming forecasts. Availability coverage varies by game.`;
      const stamp=document.querySelector('.masthead-foot .status');
      if(stamp)stamp.textContent=(h.stale?'UPDATE OVERDUE · ':'UPDATED · ')+M.asOf;
    }
    update();setInterval(update,60000);

  }
  document.addEventListener('DOMContentLoaded',()=>loadDailyUpdates().catch(console.error),{once:true});
}
