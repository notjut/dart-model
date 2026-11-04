const assert=require('node:assert/strict');
const fs=require('node:fs');
const {createEngine,render,evening}=require('../matchup-brief.js');
const q={margin:5,total:49,h:27,a:22,p:.65};
const game={id:'future',date:'2026-11-07T17:00Z',season:2026,home:'41',away:'153',neutral:false,done:false,timeValid:true};
const g=(id,date,home,away,hs,as,extra={})=>({id,date,home,away,hs,as,done:true,timeValid:true,season:Number(date.slice(0,4)),url:'https://example.com/'+id,...extra});
const data={asOf:'2026-11-04',teams:{'41':{name:'UConn',conference:'FBS Independents'},'153':{name:'North Carolina',conference:'Atlantic Coast Conference'},'25':{name:'California',conference:'Atlantic Coast Conference'},'9':{name:'Other',conference:'Non-FBS opponent'}},games:[
  g('a','2026-09-12T23:30Z','41','9',35,14),g('b','2026-09-19T17:00Z','9','41',28,21),
  g('c','2026-09-12T23:00Z','153','9',20,21),g('d','2026-09-19T17:00Z','9','153',13,30),game,
  g('leak','2026-11-05T17:00Z','41','9',70,0),g('same-day','2026-11-07T01:00Z','41','9',70,0)
]};
const profile={n:2,margin:7,plays:100,dplays:100,net:.025,sr:.45,dsr:.425};
const f={id:'future',homeProfile:profile,awayProfile:{...profile,net:.023,margin:1}};
const history={startSeason:2016,games:[g('old','2023-09-02T17:00Z','25','41',14,20),g('valid','2024-09-02T17:00Z','25','41',14,20)]};
const model={inputRetrievedAt:'2026-11-04T20:00:00Z',asOf:'2026-11-04'};
let e=createEngine({data,history,model});
let r=e.build(f,q,{market:true,team:'41'});
assert.match(r.headline,/picks UConn to win the upset/);
assert.doesNotMatch(r.headline,/striking distance/);
assert.equal(e.rowsFor('41',game).length,2,'Future and same-day results cannot enter a brief');
assert.equal(r.risks.filter(x=>x.title.includes('Both teams')).length,1,'Tiny efficiency gaps must not become major advantages');
assert.ok(r.gaps.some(x=>x.includes('full FBS')),'Incomplete ranking coverage suppresses rank-based claims');
assert.ok(r.context.some(x=>x.title==='UConn is 1–0 against ACC teams since 2024.'),'Do not backfill ACC membership into 2023');
assert.ok(!r.context.some(x=>x.title.includes('7 p.m.')),'Afternoon games do not get night-game narratives');
assert.equal(evening({date:'2026-09-12T23:30Z',timeValid:false}),false);
assert.equal(evening({date:'2026-09-12T23:30Z',timeValid:true}),true);
const neutralData=structuredClone(data);neutralData.games.find(x=>x.id===game.id).neutral=true;
r=createEngine({data:neutralData,history,model}).build(f,q,{market:false});
assert.ok(![...r.support,...r.risks].some(x=>x.title.includes('at home')||x.title.includes('on the road')));
assert.doesNotMatch(r.headline,/upset/,'No market underdog, no upset classification');
r=e.build(f,{...q,margin:0},{market:true,team:'41'});
assert.match(r.headline,/even/);assert.match(r.summary,/no outright winner/);
const safe=render({...r,support:[{title:'<script>alert(1)</script>',meaning:'test',n:1,games:[{team:'A',opponent:'B',date:'2026-01-01',pf:1,pa:0,url:'javascript:alert(1)'}]}],risks:[],context:[],gaps:[]});
assert.ok(!safe.includes('<script>'));assert.ok(!safe.includes('href="javascript:'));

// Exercise every current forecast, not just the screenshot's matchup.
const D=JSON.parse(fs.readFileSync('data.json')),H=JSON.parse(fs.readFileSync('history.json')),M=JSON.parse(fs.readFileSync('model.json')),B=JSON.parse(fs.readFileSync('game-details.json'));
const original=JSON.stringify(M);e=createEngine({data:D,history:H,model:M});
function cdf(x){let z=Math.abs(x),t=1/(1+.2316419*z),v=1-.3989422804*Math.exp(-z*z/2)*t*(.319381530+t*(-.356563782+t*(1.781477937+t*(-1.821255978+t*1.330274429))));return x>=0?v:1-v;}
for(const f of M.forecasts){
 const g=D.games.find(x=>x.id===f.id),margin=f.coreMargin,total=Math.max(Math.abs(margin)+2,f.coreTotal);
 let h=Math.round((total+margin)/2),a=Math.round((total-margin)/2);if(h===a){if(margin>=0)h++;else a++;}
 const spread=B.games[f.id]?.homeSpread,ui={market:Number.isFinite(spread)&&spread!==0,team:spread>0?g.home:g.away};
 const q={margin,total,h,a,p:cdf(margin/f.coreSd)},r=e.build(f,q,ui),html=render(r);
 assert.ok(r.support.length+r.risks.length>0,`${f.id}: missing explanation`);
 assert.ok(!/\bNaN\b|undefined/.test(html),`${f.id}: invalid rendered value`);
 assert.ok(r.summary.includes(`${a}`)&&r.summary.includes(`${h}`));
 for(const fact of [...r.support,...r.risks,...r.context])for(const item of fact.games){
  assert.ok(Date.parse(item.date)<Date.parse(r.cutoff),`${f.id}: leaked result ${item.id}`);
  assert.notEqual(item.id,f.id);
 }
}
assert.equal(JSON.stringify(M),original,'Explanation changes must not mutate forecasts or weights');
console.log(`Plain-language briefs verified across all ${M.forecasts.length} forecasts, plus leakage, membership, tiny-edge, neutral-site and HTML-safety checks.`);
