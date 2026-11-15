/* Public system entry point. Kept at its existing URL for older page links. */
(async function(){
'use strict';
const target=document.getElementById('goldenContent');
if(!target)return;
document.getElementById('goldenGate')?.remove();
target.hidden=false;
target.setAttribute('aria-busy','true');
try{
 const [app,study]=await Promise.all([
  import('./golden.js?v=20261115-public1'),
  fetch('golden-study.json?v=20261115-public1').then(r=>{if(!r.ok)throw Error('Study unavailable');return r.json();})
 ]);
 await app.mount(target,study);
}catch(error){
 target.replaceChildren();
 const title=document.createElement('h1'),message=document.createElement('p'),retry=document.createElement('button');
 title.textContent='The Golden System';
 message.textContent='System research is temporarily unavailable. Please try again.';
 message.setAttribute('role','alert');
 retry.type='button';retry.textContent='Try again';retry.onclick=()=>location.reload();
 target.append(title,message,retry);
}finally{target.removeAttribute('aria-busy');}
})();
