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
