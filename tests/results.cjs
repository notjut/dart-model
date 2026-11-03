const assert=require('node:assert/strict');
const {tally,filter,weekOf,easternDate}=require('../results.js');
const teams={a:{name:'Home team',conference:'SEC'},b:{name:'Visitor',conference:'ACC'}};
const rows=[
 {date:'2026-11-01T00:30:00Z',home:'a',away:'b',winner:'win',spread:'loss',total:'push',upsetPickResult:'not_picked'},
 {date:'2026-10-24T20:00:00Z',home:'a',away:'b',winner:'loss',spread:'win',total:'unavailable',upsetPickResult:'loss'},
 {date:'2026-10-24T19:00:00Z',home:'a',away:'b',winner:'win',spread:'no_pick',total:'win',upsetPickResult:'win'}
];
assert.equal(easternDate(rows[0].date),'2026-10-31');
assert.equal(weekOf(rows[0].date),'2026-10-26');
assert.deepEqual(tally(rows,'upset'),{win:1,loss:1,push:0,no_pick:0,unavailable:0});
assert.equal(tally(rows,'total').win,1);
assert.equal(tally(rows,'total').push,1);
assert.equal(filter(rows,'week:2026-10-26','all','',teams).length,1);
assert.equal(filter(rows,'day:2026-10-24','SEC','visitor',teams).length,2);
assert.equal(filter(rows,'all','ACC','',teams).length,3);
assert.equal(filter(rows,'all','Big Ten','',teams).length,0);
console.log('Results filters, dates, and record counting passed');
