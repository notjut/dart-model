import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('sniper_props',Path(__file__).resolve().parents[1]/'scripts/sniper_props.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Props(unittest.TestCase):
    def test_boxscore_numeric_strings(self):
        self.assertEqual(m.number('232'),232)
        self.assertEqual(m.number('-4'),-4)
        for value in [None,'--','NaN','inf']:
            self.assertIsNone(m.number(value))
    def test_missing_statistics_are_not_zero(self):
        g={'id':'1','date':'2026-01-01','home':'1','hs':30,'as':20}
        d={'boxscore':{'players':[{'team':{'id':'1'},'statistics':[{'name':'passing','keys':['passingYards'],'athletes':[{'athlete':{'id':'2','displayName':'QB'},'stats':['--']},{'athlete':{'id':'3','displayName':'QB2'},'stats':['0']}]}]}]}}
        rows=m.extract(g,d)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['value'],0)
        self.assertEqual(rows[0]['playerId'],'3')
