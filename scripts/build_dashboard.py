"""Build a small, lossless view of fields needed on the Picks screen.
Canonical data/model files remain unchanged and are loaded for research.
"""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
d=json.loads((root/'data.json').read_text());m=json.loads((root/'model.json').read_text())
forecast_keys={'id','coreMargin','coreTotal','coreSd','coreContributions','reviewRequired','coreIntercept','coachChangeEvents'}
small_m={k:v for k,v in m.items() if k not in {'forecasts','heldout'}}
small_m['forecasts']=[{k:v for k,v in f.items() if k in forecast_keys} for f in m['forecasts']]
small_d={k:v for k,v in d.items() if k!='games'}
game_keys={'id','home','away','date','done','hs','as','season','neutral','venue','venueId','url','timeValid','state','status'}
ids={f['id'] for f in m['forecasts']}
small_d['games']=[{k:v for k,v in g.items() if k in (game_keys if g['id'] in ids else {'id','home','away','date','done','hs','as'})} for g in d['games']]
(root/'picks-bootstrap.json').write_text(json.dumps({'data':small_d,'model':small_m},separators=(',',':')))

# Keep the existing explanation label without downloading the full research profiles.
for source,target in zip(m['forecasts'],small_m['forecasts']):
    if source.get('opponentAdjustment',{}).get('appliedToMain'): target['opponentAdjustment']={'appliedToMain':True}
(root/'picks-bootstrap.json').write_text(json.dumps({'data':small_d,'model':small_m},separators=(',',':')))
