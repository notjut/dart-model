import copy
import datetime as dt
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from daily_refresh import grade, grade_snapshots, validate_sources, validate_forecasts


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.game = {'id': 'a', 'date': '2026-10-31T23:30:00Z', 'home': 'USC', 'away': 'OSU',
                     'done': True, 'hs': 30, 'as': 18}
        self.forecast = {'id': 'a', 'coreMargin': -2.54, 'coreTotal': 50.58}
        self.snap = {'generatedAt': '2026-10-24T15:06:54Z', 'type': 'recovered_saved_forecast',
                     'forecasts': [self.forecast], 'games': {'a': dict(self.game, done=False)},
                     'quotes': {'a': {'retrievedAt': '2026-10-24T05:39:00Z', 'homeSpread': 6.5, 'overUnder': 53.5}}}

    def test_upset_is_outright_not_cover(self):
        data = {'games': [dict(self.game, hs=24, **{'as': 27})]}
        r = grade_snapshots([self.snap], data)['games'][0]
        self.assertEqual(r['spread'], 'win')
        self.assertFalse(r['upset'])

    def test_osu_usc_winner_miss_cover_and_under_win(self):
        r = grade_snapshots([self.snap], {'games': [self.game]})['games'][0]
        self.assertEqual((r['winner'], r['spread'], r['total']), ('loss', 'win', 'win'))
        self.assertTrue(r['upset'])

    def test_postgame_prediction_never_grades(self):
        self.snap['generatedAt'] = '2026-11-01T12:00:00Z'
        self.assertEqual(grade_snapshots([self.snap], {'games': [self.game]})['games'], [])

    def test_postgame_line_never_grades(self):
        self.snap['quotes']['a']['retrievedAt'] = '2026-11-01T12:00:00Z'
        r = grade_snapshots([self.snap], {'games': [self.game]})['games'][0]
        self.assertEqual((r['spread'], r['total']), ('unavailable', 'unavailable'))

    def test_latest_pregame_snapshot_not_best_hindsight_pick(self):
        later = copy.deepcopy(self.snap)
        later['generatedAt'] = '2026-10-31T12:00:00Z'
        later['forecasts'][0]['coreMargin'] = -5
        rows = grade_snapshots([later, self.snap], {'games': [self.game]})['games']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['predictedHomeMargin'], -5)

    def test_push_and_no_pick_are_not_wins(self):
        self.assertEqual(grade(4, 0), 'push')
        self.assertEqual(grade(0, 4), 'no_pick')

    def test_upset_that_model_missed_is_not_an_upset_hit(self):
        result = grade_snapshots([self.snap], {'games': [self.game]})
        self.assertTrue(result['games'][0]['upset'])
        self.assertFalse(result['games'][0]['pickedUnderdog'])
        self.assertEqual(result['records']['upset']['win'], 0)

    def test_underdog_cover_without_win_is_a_missed_upset(self):
        self.forecast['coreMargin'] = 1
        result = grade_snapshots([self.snap], {'games': [dict(self.game, hs=24, **{'as':27})]})
        row = result['games'][0]
        self.assertEqual((row['spread'], row['upsetPickResult']), ('win', 'loss'))
        self.assertEqual(result['records']['upset'], {'win':0, 'loss':1, 'push':0})

    def test_home_and_away_underdog_wins(self):
        self.forecast['coreMargin'] = 1
        self.assertEqual(grade_snapshots([self.snap], {'games':[self.game]})['records']['upset']['win'], 1)
        self.forecast['coreMargin'] = -1
        self.snap['quotes']['a']['homeSpread'] = -6.5
        row = grade_snapshots([self.snap], {'games':[dict(self.game, hs=20, **{'as':30})]})['games'][0]
        self.assertEqual((row['pickedTeam'],row['upsetPickResult']), ('OSU','win'))

    def test_pickem_and_missing_line_cannot_define_an_upset_pick(self):
        for line in [0, None]:
            self.snap['quotes']['a']['homeSpread'] = line
            row = grade_snapshots([self.snap], {'games':[self.game]})['games'][0]
            self.assertFalse(row['pickedUnderdog'])
            self.assertIsNone(row['explanation'])

    def test_earlier_rescheduled_kickoff_blocks_late_pick(self):
        self.snap['generatedAt'] = '2026-10-31T20:00:00Z'
        result = grade_snapshots([self.snap], {'games':[dict(self.game,date='2026-10-31T17:00:00Z')]})
        self.assertEqual(result['games'], [])

    def test_explanation_uses_saved_main_model_not_experiment(self):
        self.forecast.update(coreMargin=1, coreSd=10, coreIntercept=.5,
                             coreContributions=[{'name':'Home field','points':.5}],
                             contributions=[{'name':'Magic narrative','points':20}])
        row = grade_snapshots([self.snap], {'games':[self.game]})['games'][0]
        self.assertEqual(row['explanation']['drivers'], [{'factor':'home field','pointsTowardPick':.5}])
        self.assertGreater(row['pickWinProbability'],.5)
        self.assertIn('forecast-archive/',row['sourceArchive'])

    def test_incomplete_refresh_blocks_release(self):
        previous = {'teams': {'a': {'conference': 'SEC'}}, 'games': []}
        data = {'refresh': {'scheduleTeamsRefreshed': []}, 'failures': [], 'games': []}
        with self.assertRaises(ValueError):
            validate_sources(data, previous)

    def test_started_game_cannot_be_current_forecast(self):
        data = {'asOf': '2026-11-01', 'retrievedAt': 'stamp', 'games': [self.game]}
        model = {'asOf': data['asOf'], 'inputRetrievedAt': 'stamp', 'forecasts': [self.forecast]}
        with self.assertRaises(ValueError):
            validate_forecasts(data, model, dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc))


if __name__ == '__main__':
    unittest.main()

class MarketPriceTests(unittest.TestCase):
    def test_same_offer_prices_and_favorite_sign(self):
        from daily_refresh import market_prices
        row = market_prices({'spread': 2.5, 'overUnder': 42.5, 'overOdds': -102, 'underOdds': -118,
                             'homeTeamOdds': {'moneyLine': 120, 'spreadOdds': -102, 'favorite': False},
                             'awayTeamOdds': {'moneyLine': -142, 'spreadOdds': -118, 'favorite': True}})
        self.assertEqual(row['homeSpread'], 2.5)
        self.assertEqual(row['awaySpread'], -2.5)
        self.assertEqual(row['homeSpreadOdds'], -102)
        self.assertEqual(row['underOdds'], -118)
    def test_no_invented_price_or_ambiguous_spread(self):
        from daily_refresh import market_prices
        row = market_prices({'spread': 3, 'overUnder': 48, 'overOdds': True,
                             'homeTeamOdds': {'favorite': True}, 'awayTeamOdds': {'favorite': True}})
        self.assertIsNone(row['homeSpread'])
        self.assertIsNone(row['overOdds'])
        self.assertIsNone(row['homeSpreadOdds'])
        self.assertEqual(row['total'], 48)
