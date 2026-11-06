const assert=require('node:assert/strict');const board=require('../started-games.js');
const g={home:'FAU',away:'UTSA',date:'2026-11-06T00:30Z',status:'STATUS_IN_PROGRESS',done:false,savedPick:{homeMargin:-3.8,total:60.8,quote:{homeSpread:7,overUnder:72.5}}};
const options={asOf:'2026-11-05',teams:{FAU:{name:'Florida Atlantic',abbr:'FAU',conference:'American'},UTSA:{name:'UTSA',abbr:'UTSA',conference:'American'}}};
assert.equal(board.filter([g],options).length,1);
assert.equal(board.filter([g],{...options,query:'FAU'}).length,1);
assert.equal(board.filter([g],{...options,conference:'SEC'}).length,0);
assert.equal(board.filter([g],{...options,week:'next'}).length,0);
assert.deepEqual(board.selections(g),{winner:'UTSA',spread:{team:'FAU',line:7},total:{side:'Under',line:72.5}});
assert.equal(board.state(g),'In progress at last check');assert.equal(board.state({...g,done:true}),'Final');
assert.equal(board.selections({...g,savedPick:null}),null);
assert.equal(board.filter([{...g,date:'2026-11-09T00:30Z'}],options).length,1); // Sunday Eastern, Monday UTC.
assert.equal(board.filter([{...g,date:'2026-11-09T14:00Z'}],options).length,0);
console.log('Started-game visibility, Eastern weeks and saved-pick selections passed');
