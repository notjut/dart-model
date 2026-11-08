"""The fast first screen must keep the canonical forecast and settlement inputs."""
import json
from pathlib import Path
import runpy
import unittest
ROOT=Path(__file__).resolve().parents[1]
class DashboardBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runpy.run_path(str(ROOT/'scripts/build_dashboard.py'))
        cls.bootstrap=json.loads((ROOT/'picks-bootstrap.json').read_text())
        cls.model=json.loads((ROOT/'model.json').read_text())
        cls.data=json.loads((ROOT/'data.json').read_text())
    def test_forecasts_keep_moneyline_score_and_eligibility_inputs(self):
        tiny=self.bootstrap['model']
        self.assertEqual(tiny['refreshRunId'],self.model['refreshRunId'])
        self.assertEqual(tiny['inputRetrievedAt'],self.model['inputRetrievedAt'])
        self.assertEqual(len(tiny['forecasts']),len(self.model['forecasts']))
        for a,b in zip(tiny['forecasts'],self.model['forecasts']):
            for k in ['id','coreMargin','coreTotal','coreSd','coreContributions','reviewRequired']:
                self.assertEqual(a.get(k),b.get(k),k)
    def test_all_completed_scores_retained_for_existing_saved_tickets(self):
        games={g['id']:g for g in self.bootstrap['data']['games']}
        for original in self.data['games']:
            for k in ['id','home','away','date','done','hs','as']:
                self.assertEqual(games[original['id']].get(k),original.get(k),k)
    def test_full_research_contract_is_not_replaced(self):
        self.assertNotIn('heldout',self.bootstrap['model'])
        self.assertIn('heldout',self.model)
        self.assertLess((ROOT/'picks-bootstrap.json').stat().st_size,700_000)
        for name in ['history.json','player-facts.json','upset-history.json','availability.json','matchup-environment.json']:
            self.assertTrue((ROOT/name).is_file(),name)
if __name__=='__main__':unittest.main()
