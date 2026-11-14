import importlib.util, unittest, datetime as dt
from pathlib import Path
spec=importlib.util.spec_from_file_location('sims_data',Path(__file__).resolve().parents[1]/'scripts/sims_data.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SimsDataTests(unittest.TestCase):
 def test_verified_completed_scores_only(self):
  event=lambda n,done,score:{'id':n,'date':'2026-09-01T00:00Z','competitions':[{'status':{'type':{'completed':done}},'competitors':[{'id':'1','homeAway':'home','score':{'value':score}},{'id':'2','score':{'value':7}}]}]}
  data={'asOf':'2026-11-14','teams':{'1':{'name':'One'}},'games':[]}
  out=m.build(data,lambda *a:{'team':{'id':'1'},'season':{'year':2026},'events':[event('a',True,21),event('a',True,21),event('b',False,50),event('c',True,None)]},dt.datetime(2026,11,14,tzinfo=dt.timezone.utc))
  self.assertEqual(out['teams']['1']['n'],1);self.assertEqual(out['teams']['1']['off'],21)
 def test_mismatched_identity_is_unavailable(self):
  out=m.build({'asOf':'2026-11-14','teams':{'1':{'name':'One'}},'games':[]},lambda *a:{'team':{'id':'2'},'season':{'year':2026}},dt.datetime.now(dt.timezone.utc))
  self.assertEqual(out['unavailable'],['1']);self.assertFalse(out['teams'])
if __name__=='__main__':unittest.main()
