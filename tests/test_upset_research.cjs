const assert=require('node:assert/strict');
const fs=require('node:fs');
const {match,results}=require('../upset-research.js');
assert.equal(match(null),'');
let html=match({status:'insufficient_data',baselineHomeMargin:3,candidateHomeMargin:null,facts:[],missing:['Unknown'],profiles:{home:{games:0},away:{games:0}}},'Home','Away');
assert.match(html,/Waiting for enough data/);assert.doesNotMatch(html,/NaN|undefined/);
html=match({status:'testing',baselineHomeMargin:-3,candidateHomeMargin:1,contributions:[{name:'<script>',homeMarginPoints:4}],facts:['<img onerror=alert(1)>'],missing:[],profiles:{home:{games:3,sources:[{id:'a',date:'2026-10-01',sourceUrl:'javascript:alert(1)',observedAt:'now'}]}}},'<Home>','Away');
assert.match(html,/4.0 points toward &lt;Home&gt;/);assert.doesNotMatch(html,/<script>|<img|href="javascript:/);
html=results({summary:{baseline:{games:0}},method:'prospective only'});assert.match(html,/No completed games/);assert.doesNotMatch(html,/NaN|undefined/);
const m=JSON.parse(fs.readFileSync('model.json'));
for(const f of m.forecasts){if(!f.upsetResearch)continue;html=match(f.upsetResearch,'Home','Away');assert.doesNotMatch(html,/NaN|undefined/);assert.equal(f.upsetResearch.appliedToMain,false);}
console.log('Experimental forecast rendering, missing-data states and HTML safety passed.');
