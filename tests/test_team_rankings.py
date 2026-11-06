import copy
import datetime as dt
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import team_rankings as r

NOW = dt.datetime(2026, 11, 6, tzinfo=dt.timezone.utc)
REQUIRED = {str(i) for i in range(1, 101)}
def fpi():
    return {'count': 100, 'pageCount': 1, 'items': [
        {'season': 2026, 'team': {'$ref': f'https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/seasons/2026/teams/{i}'},
         'lastUpdated': '2026-11-05T09:00Z', 'predictives': [{'name': 'fpi', 'value': 42}, {'name': 'fpirank', 'value': float(101-i)}]}
        for i in range(1, 101)]}
def cfp():
    return {'rankings': [{'type': 'ap', 'season': {'year': 2026}, 'ranks': []},
        {'type': 'cfp', 'season': {'year': 2026}, 'date': '2026-11-03T08:00Z', 'occurrence': {'number': 10},
         'ranks': [{'current': i, 'team': {'id': str(i)}} for i in range(1, 26)]}]}
class RankingsTests(unittest.TestCase):
    def test_published_rank_not_row_order_or_fpi_value(self):
        self.assertEqual(r.parse_fpi(fpi(), 2026, REQUIRED, NOW)['ranks']['1'], 100)
    def test_incomplete_or_duplicate_fpi_rejected(self):
        for mutation in ('page', 'duplicate', 'missing', 'date', 'season', 'host'):
            p = fpi()
            if mutation == 'page': p['pageCount'] = 2
            if mutation == 'duplicate': p['items'][1]['predictives'][1]['value'] = 100
            if mutation == 'missing': p['items'].pop()
            if mutation == 'date': p['items'][0]['lastUpdated'] = '2026-11-07T09:00Z'
            if mutation == 'season': p['items'][0]['season'] = 2025
            if mutation == 'host': p['items'][0]['team']['$ref'] = 'https://unrelated.test/teams/1'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): r.parse_fpi(p, 2026, REQUIRED, NOW)
    def test_cfp_only_and_unranked_omitted(self):
        parsed = r.parse_cfp(cfp(), 2026, REQUIRED, NOW)
        self.assertEqual(parsed['ranks']['1'], 1)
        self.assertNotIn('26', parsed['ranks'])
        for mutation in ('no_cfp', 'old', 'partial', 'duplicate', 'zero', 'unmapped'):
            p = cfp()
            if mutation == 'no_cfp': p['rankings'].pop()
            if mutation == 'old': p['rankings'][1]['season']['year'] = 2025
            if mutation == 'partial': p['rankings'][1]['ranks'].pop()
            if mutation == 'duplicate': p['rankings'][1]['ranks'][1]['current'] = 1
            if mutation == 'zero': p['rankings'][1]['ranks'][0]['current'] = 0
            if mutation == 'unmapped': p['rankings'][1]['ranks'][0]['team']['id'] = '999'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): r.parse_cfp(p, 2026, REQUIRED, NOW)
    def test_failed_fetch_preserves_original_dates_and_labels_stale(self):
        data = {'games': [{'season': 2026}], 'teams': {k: {'conference': 'FBS'} for k in REQUIRED}}
        fresh = r.refresh(data, 'one', now=NOW, fetcher=lambda url: fpi() if 'powerindex' in url else cfp())
        self.assertEqual(fresh['coverage']['fpi']['teams'], 100)
        def fail(url): raise TimeoutError()
        old = r.refresh(data, 'two', fresh, NOW+dt.timedelta(days=1), fail)
        self.assertEqual(old['runId'], 'two')
        self.assertEqual(old['fpi']['status'], 'stale')
        self.assertEqual(old['fpi']['retrievedAt'], fresh['fpi']['retrievedAt'])
        self.assertEqual(old['cfp']['publishedAt'], fresh['cfp']['publishedAt'])
        absent = r.refresh(data, 'three', now=NOW, fetcher=fail)
        self.assertEqual(absent['cfp']['status'], 'unavailable')
        self.assertEqual(absent['cfp']['ranks'], {})
        wrong_season = copy.deepcopy(fresh);wrong_season['season'] = 2025
        self.assertEqual(r.refresh(data, 'four', wrong_season, NOW, fail)['fpi']['status'], 'unavailable')
if __name__ == '__main__': unittest.main()
