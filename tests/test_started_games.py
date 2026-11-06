import copy,datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from started_games import build
class StartedGamesTests(unittest.TestCase):
 def setUp(self):
  self.now=dt.datetime(2026,11,6,4,tzinfo=dt.timezone.utc)
  self.g={'id':'g','date':'2026-11-06T00:30Z','home':'FAU','away':'UTSA','done':False,'hs':0,'as':0,'status':'STATUS_IN_PROGRESS'}
  self.snap={'generatedAt':'2026-11-06T00:27Z','recordedAt':'2026-11-06T00:28Z','asOf':'2026-11-05','type':'prospective_snapshot','games':{'g':copy.deepcopy(self.g)},'forecasts':[{'id':'g','coreMargin':-3.8,'coreTotal':60.8}],'quotes':{'g':{'retrievedAt':'2026-11-06T00:27Z','homeSpread':7,'overUnder':72.5}}}
 def run_board(self,snaps=None,g=None):return build([self.snap] if snaps is None else snaps,{'games':[g or self.g]},{},'run',self.now)['games']
 def test_in_progress_keeps_pregame_pick_without_fake_zero_score(self):
  r=self.run_board()[0];self.assertEqual(r['savedPick']['homeMargin'],-3.8);self.assertIsNone(r['homeScore']);self.assertIsNone(r['awayScore'])
 def test_later_prediction_or_later_recording_cannot_replace_pick(self):
  for field in ['generatedAt','recordedAt']:
   later=copy.deepcopy(self.snap);later[field]='2026-11-06T01:00Z';later['forecasts'][0]['coreMargin']=30
   self.assertEqual(self.run_board([self.snap,later])[0]['savedPick']['homeMargin'],-3.8)
 def test_postkickoff_line_excluded(self):
  self.snap['quotes']['g']['retrievedAt']='2026-11-06T01:00Z';self.assertEqual(self.run_board()[0]['savedPick']['quote'],{})
 def test_latest_pre_game_selected_not_best_pick(self):
  earlier=copy.deepcopy(self.snap);earlier['generatedAt']='2026-11-05T12:00Z';earlier['forecasts'][0]['coreMargin']=12
  self.assertEqual(self.run_board([earlier,self.snap])[0]['savedPick']['homeMargin'],-3.8)
 def test_started_game_with_no_archive_still_visible(self):self.assertIsNone(self.run_board([])[0]['savedPick'])
 def test_future_game_excluded(self):self.assertEqual(self.run_board(g=dict(self.g,date='2026-11-07T00:30Z')),[])
 def test_completed_score_retains_same_pick(self):
  r=self.run_board(g=dict(self.g,done=True,hs=41,**{'as':35}))[0]
  self.assertEqual((r['homeScore'],r['awayScore'],r['savedPick']['homeMargin']),(41,35,-3.8))
 def test_earlier_rescheduled_kickoff_rejects_pick(self):self.assertIsNone(self.run_board(g=dict(self.g,date='2026-11-05T22:00Z'))[0]['savedPick'])
if __name__=='__main__':unittest.main()
