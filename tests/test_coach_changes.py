import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from coach_changes import archived_line, build, first_game, confirmed_change


class CoachChangeTests(unittest.TestCase):
    def event(self, **changes):
        return dict(dict(id='dismissal', team='1', teamName='Test team', date='2026-10-04',
                         season=2026, immediate=True, changeType='dismissal'), **changes)

    def game(self, gid='next', date='2026-10-17T23:00:00Z', **changes):
        return dict(dict(id=gid, home='1', away='2', season=2026, date=date,
                         neutral=False, done=True, hs=20, **{'as': 23}), **changes)

    def build(self, events, games, quotes=None, as_of='2026-10-20'):
        data = {'asOf': as_of, 'teams': {'1': {'name': 'One', 'conference': 'ACC'},
                                        '2': {'name': 'Two', 'conference': 'ACC'}}, 'games': games}
        return build(data, {'games': []}, {'events': events, 'coverage': 'Test sample'}, quotes or {})

    def test_next_game_after_bye_only(self):
        before = self.game('before', '2026-10-03T18:00:00Z')
        first = self.game()
        second = self.game('second', '2026-10-24T18:00:00Z')
        self.assertEqual(first_game(self.event(), [second, before, first])['id'], 'next')
        result = self.build([self.event()], [before, first, second])
        self.assertEqual(result['rows'][0]['daysAfterChange'], 13)
        self.assertEqual(result['cohorts']['afterLongerBreak']['games'], 1)

    def test_not_offseason_or_announced_future_exit(self):
        next_year = self.game(season=2027, date='2027-09-04T18:00:00Z')
        self.assertIsNone(first_game(self.event(), [next_year]))
        self.assertIsNone(first_game(self.event(immediate=False), [self.game()]))

    def test_coach_identity_uses_only_announcements_known_in_that_season(self):
        events = [self.event(), self.event(id='later', date='2026-10-24')]
        self.assertEqual(confirmed_change('1', 2026, '2026-10-20', events)['id'], 'dismissal')
        self.assertIsNone(confirmed_change('1', 2025, '2025-10-20', events))
        self.assertIsNone(confirmed_change('1', 2026, '2026-10-03', events))

    def test_local_day_does_not_flag_game_before_dismissal(self):
        # UTC Sunday, but still Saturday evening in the Eastern time zone.
        saturday = self.game('saturday', '2026-10-04T02:00:00Z')
        self.assertIsNone(first_game(self.event(), [saturday]))

    def test_cover_is_not_an_outright_upset(self):
        out = self.build([self.event()], [self.game()], {'next': {'homeSpread': 7}})
        row = out['rows'][0]
        self.assertFalse(row['won'])
        self.assertEqual(row['ats'], 'win')
        self.assertEqual(out['cohorts']['homeUnderdogs']['wins'], 0)
        self.assertEqual(out['cohorts']['homeUnderdogs']['losses'], 1)

    def test_away_spread_sign_and_push(self):
        out = self.build([self.event(team='2')], [self.game()], {'next': {'homeSpread': 3}})
        row = out['rows'][0]
        self.assertEqual(row['teamSpread'], -3)
        self.assertTrue(row['won'])
        self.assertEqual(row['ats'], 'push')

    def test_missing_line_is_not_a_loss_or_underdog(self):
        c = self.build([self.event()], [self.game()])['cohorts']
        self.assertEqual(c['fbs']['missingLines'], 1)
        self.assertEqual(c['fbs']['atsLosses'], 0)
        self.assertEqual(c['underdogs']['games'], 0)

    def test_mutual_departure_stays_separate(self):
        c = self.build([self.event(changeType='mutual_departure')], [self.game()])['cohorts']
        self.assertEqual(c['fbs']['games'], 0)
        self.assertEqual(c['mutualDepartures']['games'], 1)

    def test_future_results_cannot_enter_history(self):
        out = self.build([self.event()], [self.game()], as_of='2026-10-10')
        self.assertFalse(out['rows'][0]['completed'])
        self.assertEqual(out['games']['next']['history']['fbs']['games'], 0)
        self.assertEqual(out['cohorts']['fbs']['games'], 0)

    def test_next_game_gets_only_earlier_completed_history(self):
        prior = self.game('prior', '2026-10-10T18:00:00Z')
        upcoming = self.game('upcoming', '2026-10-24T18:00:00Z', done=False)
        events = [self.event(), self.event(id='second-dismissal', team='2', date='2026-10-18')]
        out = self.build(events, [prior, upcoming])
        self.assertEqual(out['games']['upcoming']['history']['fbs']['gameIds'], ['prior'])

    def payload(self):
        return {'header': {'id': 'next', 'competitions': [{'status': {'type': {'completed': True}},
                 'competitors': [{'id': '1', 'homeAway': 'home'}, {'id': '2', 'homeAway': 'away'}]}]},
                'pickcenter': [{'provider': {'name': 'Archived sportsbook', 'priority': 1},
                                'spread': 7, 'homeTeamOdds': {'favorite': False},
                                'awayTeamOdds': {'favorite': True}}]}

    def test_line_requires_matching_completed_game_and_known_favorite(self):
        payload = self.payload()
        self.assertEqual(archived_line(payload, self.game())['homeSpread'], 7)
        wrong = copy.deepcopy(payload)
        wrong['header']['id'] = 'other'
        self.assertIsNone(archived_line(wrong, self.game()))
        wrong = copy.deepcopy(payload)
        wrong['header']['competitions'][0]['status']['type']['completed'] = False
        self.assertIsNone(archived_line(wrong, self.game()))
        wrong = copy.deepcopy(payload)
        wrong['pickcenter'][0]['awayTeamOdds']['favorite'] = False
        self.assertIsNone(archived_line(wrong, self.game()))
        wrong = copy.deepcopy(payload)
        wrong['pickcenter'][0]['provider']['name'] = 'numberfire'
        self.assertIsNone(archived_line(wrong, self.game()))


if __name__ == '__main__':
    unittest.main()
