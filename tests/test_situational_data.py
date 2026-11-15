import copy,datetime as dt,importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('situational_data',Path(__file__).resolve().parents[1]/'scripts/situational_data.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Situations(unittest.TestCase):
 def setUp(self):
  self.now=dt.datetime(2026,11,14,12,tzinfo=dt.timezone.utc)
  self.s=[{'game_id':'g','season_type':'regular','season':'2026','start_date':'2026-11-15T18:00Z','home_id':'h','away_id':'a','completed':'false','status':'STATUS_SCHEDULED','neutral_site':'false','venue_id':'v','venue':'Home Park','fbs_game':'true','fbs_participant':'true'}]
  self.t=[{'team_id':t,'school':t,'is_fbs':'true','venue_id':'v' if t=='h' else 'w','latitude':'30','longitude':'-80'} for t in ['h','a']]
 def build(self,b=None,q=None,started=None):return m.build(self.s,b or [],self.t,{'games':[]},q or {},started or {},self.now,'run')
 def test_defaults_are_not_real_spreads(self):
  out=self.build([{'game_id':'g','home_team_spread':'2.5','game_spread_available':'true','odds_source':'default'}]);self.assertIsNone(out['games'][0]['homeSpread'])
 def test_quote_after_kickoff_rejected(self):
  out=self.build(q={'games':{'g':{'state':'pre','homeSpread':-3,'retrievedAt':'2026-11-15T19:00Z'}}});self.assertIsNone(out['games'][0]['quote']);self.assertEqual(out['snapshots'],[])
 def test_before_kickoff_context_and_exact_quote_saved(self):
  out=self.build(q={'games':{'g':{'state':'pre','homeSpread':-3.5,'awaySpreadOdds':-105,'provider':'Book','retrievedAt':'2026-11-14T11:55Z'}}});self.assertEqual(out['snapshots'][0]['quote']['homeSpread'],-3.5);self.assertEqual(out['snapshots'][0]['quote']['awayOdds'],-105)
 def test_first_snapshot_is_not_rewritten(self):
  a={'gameId':'g','kickoff':'2026-11-15T18:00Z','quote':{'homeSpread':-3}};b=copy.deepcopy(a);b['quote']['homeSpread']=-7;out=m.merge_archive({'snapshots':[a]},[b]);self.assertEqual(out['snapshots'][0]['quote']['homeSpread'],-3)
 def test_postponed_games_are_not_archived(self):
  self.s[0]['status']='STATUS_POSTPONED';out=self.build(q={'games':{'g':{'state':'pre','homeSpread':-3,'retrievedAt':'2026-11-14T11:55Z'}}});self.assertEqual(out['snapshots'],[])
if __name__=='__main__':unittest.main()
