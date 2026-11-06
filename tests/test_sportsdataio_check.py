from copy import deepcopy
import datetime as dt
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sportsdataio_check import check, request_rows, NoRedirect

NOW = dt.datetime(2026, 11, 6, 12, tzinfo=dt.timezone.utc)


class InjuryCheckTests(unittest.TestCase):
    def setUp(self):
        self.player = {'name': 'Example Player', 'position': 'C', 'unit': 'Center',
                       'status': 'Out', 'isConcern': True, 'roleVerified': True,
                       'roleEvidence': {'summary': 'Official center bio'}}
        team = {'teamId': '1', 'teamName': 'Example College', 'status': 'reported',
                'gameDate': '2026-11-07', 'publishedAt': '2026-11-05T18:00:00-05:00',
                'retrievedAt': '2026-11-06T11:00:00+00:00',
                'players': [deepcopy(self.player)], 'concerns': [deepcopy(self.player)]}
        self.availability = {'games': {'g': {'gameDate': '2026-11-07', 'status': 'reported',
                                           'home': team, 'away': None}},
                             'teams': {'1': deepcopy(team)}, 'coverage': {'reportedMatchups': 1}}
        self.rows = [{'PlayerID': 100, 'TeamID': 10, 'FirstName': 'Example', 'LastName': 'Player',
                      'Position': 'OL', 'InjuryStatus': 'Out', 'InjuryNotes': 'RAW DIAGNOSIS'}]
        self.teams = [{'TeamID': 10, 'School': 'Example College'}]

    def fetch(self, path, key):
        rows = self.teams if path.endswith('/Teams') else self.rows
        return {'state': 'returned_rows', 'records': len(rows)}, rows

    def run_check(self, **kwargs):
        return check(self.availability, 'secret-test-value', 'run-test', NOW, kwargs.get('fetch', self.fetch))

    def test_same_status_preserves_verified_center_and_official_coverage(self):
        before = deepcopy(self.availability)
        out = self.run_check()
        p = out['games']['g']['home']['players'][0]
        self.assertEqual(p['supplementalCheck']['status'], 'same_status')
        self.assertEqual({k: v for k, v in p.items() if k != 'supplementalCheck'}, self.player)
        self.assertEqual(out['coverage'], before['coverage'])
        self.assertEqual(self.availability, before)
        self.assertFalse(out['supplementalCheck']['scoreAdjustmentsApplied'])
        self.assertEqual(out['supplementalCheck']['priorityUnits']['Center']['same_status'], 1)
        self.assertEqual(out['teams']['1']['concerns'][0]['supplementalCheck']['status'], 'same_status')

    def test_conflict_keeps_official_status(self):
        self.rows[0]['InjuryStatus'] = 'Questionable'
        p = self.run_check()['games']['g']['home']['concerns'][0]
        self.assertEqual(p['status'], 'Out')
        self.assertEqual(p['supplementalCheck']['status'], 'status_differs')
        self.assertNotIn('Questionable', json.dumps(p))

    def test_no_trial_only_players_or_diagnoses_published(self):
        self.rows.append({'TeamID': 10, 'PlayerID': 101, 'FirstName': 'Unverified',
                          'LastName': 'Person', 'InjuryStatus': 'Out'})
        output = json.dumps(self.run_check())
        for raw in ['RAW DIAGNOSIS', 'Unverified', 'Person', 'secret-test-value', 'PlayerID', 'InjuryStatus']:
            self.assertNotIn(raw, output)

    def test_missing_player_is_not_healthy(self):
        self.rows[0]['LastName'] = 'Different'
        p = self.run_check()['games']['g']['home']['players'][0]
        self.assertEqual(p['supplementalCheck']['status'], 'not_listed')
        self.assertEqual(p['status'], 'Out')

    def test_duplicates_and_incompatible_positions_are_not_matched(self):
        for mode in ['duplicate', 'different_position', 'missing_id']:
            with self.subTest(mode=mode):
                original = deepcopy(self.rows)
                if mode == 'duplicate':
                    self.rows.append(deepcopy(self.rows[0]))
                elif mode == 'different_position':
                    self.rows[0]['Position'] = 'QB'
                else:
                    del self.rows[0]['PlayerID']
                p = self.run_check()['games']['g']['home']['players'][0]
                self.assertEqual(p['supplementalCheck']['status'], 'ambiguous_match')
                self.rows = original

    def test_ambiguous_team_is_not_matched(self):
        self.teams.append({'TeamID': 11, 'School': 'Example College'})
        self.assertNotIn('supplementalCheck', self.run_check()['games']['g']['home'])

    def test_unknown_status_not_comparable(self):
        self.rows[0]['InjuryStatus'] = None
        self.assertEqual(self.run_check()['games']['g']['home']['players'][0]['supplementalCheck']['status'], 'not_comparable')

    def test_missing_pending_stale_future_and_other_game_reports_not_promoted(self):
        changes = [{'status': 'pending'}, {'publishedAt': None}, {'gameDate': '2026-10-31'},
                   {'retrievedAt': '2026-11-04T00:00:00+00:00'},
                   {'publishedAt': '2026-11-07T00:00:00+00:00'},
                   {'publishedAt': '2026-10-28T00:00:00+00:00'}]
        for change in changes:
            with self.subTest(change=change):
                old = deepcopy(self.availability)
                self.availability['games']['g']['home'].update(change)
                self.assertNotIn('supplementalCheck', self.run_check()['games']['g']['home'])
                self.availability = old
        self.availability['games']['g']['home'] = None
        self.assertIsNone(self.run_check()['games']['g']['home'])

    def test_current_feed_not_applied_to_later_week(self):
        self.availability['games']['g']['gameDate'] = '2026-11-21'
        self.availability['games']['g']['home']['gameDate'] = '2026-11-21'
        self.assertNotIn('supplementalCheck', self.run_check()['games']['g']['home'])

    def test_provider_failure_removes_old_success_and_keeps_officials(self):
        self.availability = self.run_check()
        out = self.run_check(fetch=lambda *args: ({'state': 'key_or_subscription_denied'}, []))
        self.assertEqual(out['supplementalCheck']['status'], 'unavailable')
        self.assertNotIn('supplementalCheck', out['games']['g']['home']['players'][0])
        self.assertEqual(out['games']['g']['home']['players'][0]['status'], 'Out')

    def test_no_key_makes_no_requests(self):
        with patch('sportsdataio_check.request_rows') as fetch:
            out = check(self.availability, '', 'run-test', NOW, fetch)
            fetch.assert_not_called()
            self.assertEqual(out['supplementalCheck']['status'], 'not_configured')

    def test_request_keeps_key_out_of_url_and_refuses_redirects(self):
        class Opener:
            def open(inner, req, timeout):
                self.assertEqual(req.full_url, 'https://api.sportsdata.io/v3/cfb/scores/json/Teams')
                self.assertEqual(req.get_header('Ocp-apim-subscription-key'), 'secret-test-value')
                return io.BytesIO(b'[{"TeamID":10}]')
        with patch('sportsdataio_check.urllib.request.build_opener', return_value=Opener()):
            state, rows = request_rows('scores/json/Teams', 'secret-test-value')
            self.assertEqual(state['state'], 'returned_rows')
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.test'))
        with self.assertRaises(ValueError):
            request_rows('https://other.test/', 'secret-test-value')

    def test_transient_retry_once_but_auth_and_quota_not_retried(self):
        with patch('sportsdataio_check.urllib.request.build_opener') as builder:
            opened = builder.return_value.open
            opened.side_effect = [HTTPError('u', 503, 'sensitive body', {}, None), io.BytesIO(b'[]')]
            self.assertEqual(request_rows('scores/json/Teams', 'k')[0]['state'], 'empty_response')
            self.assertEqual(opened.call_count, 2)
        for code in [401, 403, 429]:
            with patch('sportsdataio_check.urllib.request.build_opener') as builder:
                opened = builder.return_value.open
                opened.side_effect = HTTPError('u', code, 'sensitive body', {}, None)
                output = request_rows('scores/json/Teams', 'k')
                self.assertNotIn('sensitive body', json.dumps(output))
                self.assertEqual(opened.call_count, 1)


if __name__ == '__main__':
    unittest.main()
