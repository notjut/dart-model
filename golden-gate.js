/* Only the encrypted payload is public. No shared password or strategy is stored here. */
(function(root){
'use strict';
function bytes(s){return Uint8Array.from(atob(s),c=>c.charCodeAt(0));}
async function decrypt(vault,password){
 if(vault.version!==1||vault.kdf!=='PBKDF2-SHA256'||!Number.isInteger(vault.iterations)||vault.iterations<600000||vault.iterations>2000000)throw Error('Unsupported vault');
 const material=await root.crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveKey']);
 const key=await root.crypto.subtle.deriveKey({name:'PBKDF2',salt:bytes(vault.salt),iterations:vault.iterations,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['decrypt']);
 const plain=await root.crypto.subtle.decrypt({name:'AES-GCM',iv:bytes(vault.iv)},key,bytes(vault.ciphertext));
 return JSON.parse(new TextDecoder().decode(plain));
}
root.GoldenGate={decrypt};if(typeof module!=='undefined')module.exports={decrypt};
if(typeof document==='undefined')return;
const form=document.getElementById('goldenForm'),password=document.getElementById('goldenPassword'),message=document.getElementById('goldenMessage'),unlock=document.getElementById('goldenUnlock'),show=document.getElementById('goldenShow');
show.addEventListener('click',()=>{const visible=password.type==='password';password.type=visible?'text':'password';show.textContent=visible?'Hide':'Show';show.setAttribute('aria-label',visible?'Hide password':'Show password');show.setAttribute('aria-pressed',String(visible));});
form.addEventListener('submit',async e=>{e.preventDefault();if(unlock.disabled)return;unlock.disabled=true;form.setAttribute('aria-busy','true');message.textContent='Unlocking…';let payload;
 try{
  if(!root.crypto?.subtle)throw Error('Secure connection required');
  const response=await fetch('golden-vault.json?v=20261114-gold1',{cache:'no-store'});if(!response.ok)throw Error('Vault unavailable');
  const vault=await response.json();
  try{payload=await decrypt(vault,password.value);}catch(err){message.textContent=err.name==='OperationError'?'Password not recognized. Try again.':'Unable to unlock. Please reload and try again.';password.value='';password.focus();return;}
  if(payload.schema!==1||typeof payload.module!=='string')throw Error('Invalid section');
  const url=URL.createObjectURL(new Blob([payload.module],{type:'text/javascript'}));
  try{const app=await import(url);const target=document.getElementById('goldenContent');document.getElementById('goldenGate').hidden=true;target.hidden=false;password.value='';message.textContent='';await app.mount(target,payload.study);document.getElementById('goldenGate')?.remove();target.querySelector('h1')?.focus();}finally{URL.revokeObjectURL(url);}
 }catch(err){document.getElementById('goldenGate').hidden=false;const target=document.getElementById('goldenContent');target.hidden=true;target.replaceChildren();message.textContent='This section is temporarily unavailable. Please try again.';}
 finally{unlock.disabled=false;form.removeAttribute('aria-busy');payload=null;}
});
})(globalThis);
