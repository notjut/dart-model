import copy
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import upset_engine as engine


def play(pid, kind='Rush', gain=3, team='h', period=1, **extra):
    return {'id': pid, 'type': {'text': kind}, 'start': {'down': 1, 'team': {'id': team}},
            'period': {'number': period}, 'statYardage': gain, 'text': '', **extra}


def summary():
    drives = []
    for team in ['h', 'a']:
        for n in range(3):
            drives.append({'id': team+str(n), 'team': {'id': team}, 'plays': [
                play(team+str(n)+str(i), 'Pass Reception' if i % 2 else 'Rush', team=team) for i in range(4)]})
    return {'header': {'competitions': [{'competitors': [{'id':'h'}, {'id':'a'}], 'status': {'type': {'completed': True}}}]},
            'drives': {'previous': drives}}


class InputTests(unittest.TestCase):
    def setUp(self):
        self.game = {'id':'g', 'home':'h', 'away':'a', 'season':2026, 'date':'2026-09-01T20:00:00Z'}

    def test_drive_denominator_excludes_kneels_and_overtime(self):
        s = summary()
        s['drives']['previous'] += [
            {'id':'kneel', 'team':{'id':'h'}, 'plays':[play('k', text='QB kneels')]},
            {'id':'ot', 'team':{'id':'h'}, 'plays':[play('ot', 'Rushing Touchdown', period=5)]}]
        r = engine.extract(s, self.game, '2026-09-02T00:00:00Z')
        self.assertEqual(r['teams']['h']['drives'], 3)
        self.assertEqual(r['teams']['h']['touchdowns'], 0)

    def test_sacks_not_runs_pick_six_not_offensive_td_and_deduplicate(self):
        s = summary(); d = s['drives']['previous'][0]
        d['plays'] += [play('s', 'Sack', -5), play('s', 'Sack', -5),
                       play('td', 'Passing Touchdown', 20),
                       play('pick', 'Pass Interception Return', 0, isTurnover=True)]
        s['drives']['previous'].append(copy.deepcopy(d))
        r = engine.extract(s, self.game, '2026-09-02T00:00:00Z')['teams']['h']
        self.assertEqual((r['sacks'],r['runs'],r['passPlays'],r['drives'],r['touchdowns']), (1,6,9,3,1))

    def test_incomplete_and_wrong_game_are_not_zeros(self):
        s = summary(); s['header']['competitions'][0]['status']['type']['completed'] = False
        self.assertIsNone(engine.extract(s,self.game,'stamp'))
        s = summary(); s['header']['competitions'][0]['competitors'][0]['id'] = 'other'
        self.assertIsNone(engine.extract(s,self.game,'stamp'))
        s = summary(); s['drives']['previous'] = []
        self.assertIsNone(engine.extract(s,self.game,'stamp'))

    def test_profile_blocks_future_same_day_other_season_and_target_game(self):
        counts = dict(passPlays=60,sacks=6,runs=60,stuffed=12,drives=20,touchdowns=5)
        metrics = {'games':{}}
        for i,day,season in [('old','2026-08-01',2026),('target','2026-09-01',2026),
                             ('same','2026-09-01',2026),('future','2026-09-02',2026),('prior','2025-08-01',2025)]:
            metrics['games'][i] = dict(id=i,date=day+'T01:00:00Z',season=season,home='h',away='a',
                                     teams={'h':counts,'a':counts},sourceUrl='https://example.org',observedAt='2026-09-03T00:00:00Z')
        profile=engine.profile('h',self.game,metrics,engine.date('2026-09-03T00:00:00Z'))
        self.assertEqual(profile['games'],1)
        self.assertFalse(profile['ready'])
        self.assertEqual(profile['sources'][0]['id'],'old')
        # Outcomes after the input cutoff cannot enter a future matchup.
        profile=engine.profile('h',dict(self.game,date='2026-09-04T00:00:00Z'),metrics,engine.date('2026-08-20T00:00:00Z'))
        self.assertEqual(profile['games'],1)

    def test_unknown_availability_is_not_healthy_or_a_starter_absence(self):
        now=engine.date('2026-08-31T20:00:00Z')
        row={'status':'reported','teamId':'h','opponent':'a','gameDate':'2026-09-01',
             'retrievedAt':'2026-08-31T19:00:00Z','publishedAt':'2026-08-31T18:00:00Z',
             'sourceUrl':'https://example.org','concerns':[{'name':'QB','position':'QB','unit':'Quarterback','status':'Out'}]}
        av={'games':{'g':{'status':'reported','home':row}}}
        r=engine.lineup(self.game,av,now)
        self.assertEqual(r['home']['status'],'reported')
        self.assertEqual(r['home']['startingRoles'],'unknown')
        self.assertEqual(r['away']['status'],'unknown')
        for key,value in [('opponent','other'),('gameDate','2026-08-25'),('retrievedAt','2026-08-28T19:00:00Z'),('publishedAt','2026-09-02T00:00:00Z'),('publishedAt',None)]:
            bad=copy.deepcopy(av);bad['games']['g']['home'][key]=value
            self.assertEqual(engine.lineup(self.game,bad,now)['home']['status'],'unknown')


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.game={'id':'g','date':'2026-11-07T20:00:00Z','home':'h','away':'a','done':True,'hs':20,'as':24}
        self.snap={'type':'prospective_snapshot','generatedAt':'2026-11-06T10:00:00Z',
                   'recordedAt':'2026-11-06T11:00:00Z','games':{'g':dict(self.game,done=False)},
                   'quotes':{'g':{'retrievedAt':'2026-11-06T09:00:00Z','homeSpread':4}},
                   'forecasts':[{'id':'g','coreMargin':-2,'upsetResearch':{
                       'version':engine.VERSION,'status':'testing','generatedAt':'2026-11-06T10:30:00Z',
                       'candidateHomeMargin':1,'candidateSd':12}}]}

    def grade(self,*snaps):
        return engine.grade_trial(list(snaps) or [self.snap],{'games':[self.game]})

    def test_losing_candidate_and_winning_baseline_both_count(self):
        r=self.grade()['summary']
        self.assertEqual(r['baseline']['winnerRecord']['win'],1)
        self.assertEqual(r['candidate']['winnerRecord']['loss'],1)
        self.assertEqual(r['candidate']['upsetRecord'],{'win':0,'loss':1})
        self.assertGreater(r['candidate']['brier'],r['baseline']['brier'])

    def test_latest_not_best_forecast(self):
        early=copy.deepcopy(self.snap);early['recordedAt']='2026-11-06T10:45:00Z'
        early['forecasts'][0]['upsetResearch']['candidateHomeMargin']=-8
        self.assertEqual(self.grade(self.snap,early)['games'][0]['candidate']['homeMargin'],1)

    def test_recording_after_kickoff_recovered_and_wrong_version_excluded(self):
        for change in ['late','recovered','version','rescheduled','candidate_late']:
            s=copy.deepcopy(self.snap)
            if change=='late':s['recordedAt']='2026-11-08T00:00:00Z'
            if change=='recovered':s['type']='recovered_saved_forecast'
            if change=='version':s['forecasts'][0]['upsetResearch']['version']='old'
            if change=='rescheduled':s['games']['g']['date']='2026-11-06T10:40:00Z'
            if change=='candidate_late':s['forecasts'][0]['upsetResearch']['generatedAt']='2026-11-08T00:00:00Z'
            self.assertEqual(self.grade(s)['games'],[],change)

    def test_post_snapshot_line_not_used_to_claim_upsets(self):
        self.snap['quotes']['g']['retrievedAt']='2026-11-07T19:00:00Z'
        self.assertEqual(self.grade()['summary']['candidate']['upsetRecord'],{'win':0,'loss':0})

    def test_no_pick_tie_not_a_correct_winner(self):
        self.snap['forecasts'][0]['upsetResearch']['candidateHomeMargin']=0
        self.assertEqual(self.grade()['summary']['candidate']['winnerRecord'],{'win':0,'loss':0,'no_pick':1})


class TrainingTests(unittest.TestCase):
    def test_residual_training_never_uses_target_date_and_keeps_main_forecast(self):
        start=dt.datetime(2026,7,1,tzinfo=dt.timezone.utc)
        games=[]; held=[]
        for i in range(63):
            day=start+dt.timedelta(days=min(i,61))
            g={'id':str(i),'date':day.isoformat(),'season':2026,'home':'h','away':'a','done':True}
            games.append(g);held.append({'id':str(i),'core':[2,50],'actual':[i%7-3,50],'coreSd':12})
        future=dict(games[-1],id='next',date='2026-11-07T20:00:00Z',done=False);games.append(future)
        forecast={'id':'next','coreMargin':2,'coreTotal':50,'coreSd':12}
        model={'heldout':held,'forecasts':[forecast], 'inputRetrievedAt':'2026-11-06T10:00:00Z'}
        data={'games':games,'teams':{'h':{'name':'Home'},'a':{'name':'Away'}}}
        profile={'ready':False,'sources':[],'games':0}
        calls=[]
        real_fit=engine.fit
        def checked_fit(rows):
            calls.append(copy.deepcopy(rows)); return real_fit(rows)
        with patch.object(engine,'features',return_value=([1,2,3],profile,profile)),patch.object(engine,'fit',side_effect=checked_fit):
            engine.apply(data,model,{'games':{},'coverage':{}},{},engine.date('2026-11-06T11:00:00Z'))
        self.assertEqual(len(calls[0]),60)
        self.assertEqual(len(calls[1]),61)  # Both games on day 61 use the same earlier set.
        self.assertTrue(all(r['date'][:10]<'2026-08-31' for r in calls[1]))
        self.assertEqual(len(calls[-1]),63)
        self.assertEqual(forecast['coreMargin'],2)
        self.assertEqual(forecast['coreTotal'],50)
        self.assertFalse(forecast['upsetResearch']['appliedToMain'])


if __name__=='__main__':
    unittest.main()
