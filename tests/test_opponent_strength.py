import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from opponent_strength import OpponentRatings, adjusted_features


def game(i, home, away, hs, away_score, day='2026-09-01', stats=True):
    g = {'id': str(i), 'home': home, 'away': away, 'hs': hs, 'as': away_score,
         'done': True, 'neutral': True, 'date': day + 'T20:00Z', 'season': 2026}
    if stats:
        g['stats'] = {home: {'yards': hs * 10, 'plays': 60, 'success': 25, 'explosive': 4},
                      away: {'yards': away_score * 10, 'plays': 60, 'success': 25, 'explosive': 4}}
    return g


class OpponentStrengthTests(unittest.TestCase):
    def setUp(self):
        self.data = {'asOf': '2026-10-01',
                     'teams': {t: {'conference': 'FBS'} for t in ['A', 'B', 'D', 'W', 'R', 'S']},
                     'games': []}
        # D is a strong defense; W allows far more to the same reference teams.
        for n in range(4):
            self.data['games'] += [game(f'd{n}', 'R' if n % 2 else 'S', 'D', 7, 21),
                                   game(f'w{n}', 'R' if n % 2 else 'S', 'W', 42, 21)]
        self.data['games'] += [game('a', 'A', 'D', 28, 21), game('b', 'B', 'W', 28, 21)]

    def test_same_production_against_stronger_defense_gets_more_credit(self):
        p = OpponentRatings(self.data).at('2026-10-02')['profiles']
        self.assertGreater(p['A']['metrics']['points']['offense'], p['B']['metrics']['points']['offense'])
        self.assertGreater(p['A']['metrics']['yards']['offense'], p['B']['metrics']['yards']['offense'])
        self.assertGreater(p['A']['opponentStrength'], p['B']['opponentStrength'])

    def test_future_same_day_unplayed_and_previous_season_never_enter(self):
        before = '2026-09-15'
        clean = OpponentRatings(self.data).at(before)
        changed = copy.deepcopy(self.data)
        changed['games'] += [game('same', 'A', 'B', 100, 0, before),
                             game('future', 'A', 'B', 100, 0, '2026-09-20'),
                             dict(game('old', 'A', 'B', 100, 0, '2025-09-01'), season=2025),
                             dict(game('unplayed', 'A', 'B', 100, 0), done=False)]
        self.assertEqual(clean, OpponentRatings(changed).at(before))

    def test_upcoming_game_cannot_include_results_after_saved_input_date(self):
        self.data['games'].append(game('late', 'A', 'B', 100, 0, '2026-10-03'))
        ratings = OpponentRatings(self.data)
        self.assertEqual(ratings.at('2026-10-02'), ratings.at('2026-11-01'))

    def test_fcs_blowout_does_not_inflate_fbs_performance(self):
        clean = OpponentRatings(self.data).at('2026-10-02')
        self.data['teams']['FCS'] = {'conference': 'Non-FBS opponent'}
        self.data['games'].append(game('fcs', 'A', 'FCS', 100, 0))
        self.assertEqual(clean, OpponentRatings(self.data).at('2026-10-02'))

    def test_missing_stats_are_not_recorded_as_zero_production(self):
        self.data['games'] = [game('missing', 'A', 'B', 20, 10, stats=False)]
        p = OpponentRatings(self.data).at('2026-10-02')['profiles']['A']
        self.assertEqual(p['metrics']['points']['offenseGames'], 1)
        self.assertEqual(p['metrics']['yards']['offenseGames'], 0)
        self.assertEqual(p['metrics']['success']['offenseGames'], 0)
        self.assertGreater(p['metrics']['yards']['offense'], 0)

    def test_small_sample_shrinks_and_venue_is_separate(self):
        self.data['games'] = [game('one', 'A', 'B', 70, 0)]
        p = OpponentRatings(self.data).at('2026-10-02')['profiles']
        self.assertLess(p['A']['metrics']['points']['offense'], 70)
        self.assertGreater(p['B']['metrics']['points']['offense'], 0)
        swapped = copy.deepcopy(self.data)
        swapped['games'] = [game('one', 'B', 'A', 0, 70)]
        self.assertAlmostEqual(p['A']['metrics']['points']['offense'],
                               OpponentRatings(swapped).at('2026-10-02')['profiles']['A']['metrics']['points']['offense'])

    def test_feature_replacement_preserves_raw_data_and_other_inputs(self):
        m = OpponentRatings(self.data).matchup(game('target', 'A', 'B', 0, 0, '2026-10-02'))
        raw = list(range(17)); copied = list(raw)
        new = adjusted_features(raw, m)
        self.assertEqual(raw, copied)
        for i in [0, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15, 16]:
            self.assertEqual(new[i], raw[i])
        self.assertNotEqual(new[2], raw[2])
        self.assertTrue(m['appliedToMain'])

    def test_non_fbs_opponent_is_explicitly_unavailable(self):
        m = OpponentRatings(self.data).matchup(game('target', 'A', 'FCS', 0, 0, '2026-10-02'))
        self.assertFalse(m['appliedToMain'])
        self.assertEqual(adjusted_features([1, 2, 3], m), [1, 2, 3])


if __name__ == '__main__':
    unittest.main()
