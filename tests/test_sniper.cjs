const assert=require('node:assert/strict');
const {fresh,rate,formulate}=require('../sniper.js');
const now=Date.parse('2026-11-06T12:00:00Z');
const q={bookKey:'a',side:'Over',line:50,updatedAt:'2026-11-06T11:00:00Z'};
const p={id:'1',team:'a',matchupFactor:1,quotes:[q],samples:[10,50,60,70,80,90].map((value,i)=>({gameId:String(i),value}))};
assert.deepEqual(rate(p,q),{wins:4,pushes:1,n:6});
assert.equal(fresh({...q,updatedAt:'2026-11-05T11:00:00Z'},now),false);
assert.equal(fresh({...q,updatedAt:'2026-11-07T11:00:00Z'},now),false);
const g={date:'2026-11-07T12:00:00Z',players:[p,{...p,id:'2'}]};
assert.equal(formulate(g,now).hits,4); // Shared outcomes, not .667 squared.
assert.equal(formulate({...g,reviewRequired:true},now),null);
assert.equal(formulate({...g,date:'2026-11-05T12:00:00Z'},now),null);
assert.equal(formulate({...g,players:[p,{...p,id:'2',team:'b'}]},now),null);
assert.equal(formulate({...g,players:[p,{...p,id:'2',quotes:[{...q,bookKey:'b'}]}]},now),null);
assert.equal(formulate({...g,players:[p,p]},now),null);
console.log('Sniper freshness, pushes, correlated samples and ticket restrictions passed');
