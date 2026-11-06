"""Regularized offense/defense ratings against an average FBS opponent.

Only earlier-date, completed FBS games in the target season enter a fit.
Each observed offense is fitted against the defense it actually faced, with
venue estimated separately. Three game-equivalents of shrinkage per team
reduce small-sample extremes. No market, ranking, future result or target
game enters these ratings. Retrospectively retrieved inputs remain a replay.
"""
import collections
import datetime as dt
import math

import numpy as np
from scipy.sparse import coo_matrix, diags, vstack
from scipy.sparse.linalg import lsqr

VERSION = 'opponent-adjusted-v1'
PRIOR_GAMES = 3.0
DEFAULTS = {'points': 28.0, 'yards': 370.0, 'success': .42, 'explosive': .07}


def number(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


class OpponentRatings:
    def __init__(self, data):
        self.data = data
        self.ids = sorted(t for t, team in data['teams'].items()
                          if team.get('conference') != 'Non-FBS opponent')
        self.index = {t: i for i, t in enumerate(self.ids)}
        self.cache = {}

    def at(self, before):
        # Upcoming dates cannot make future observations available.
        last = (dt.date.fromisoformat(self.data['asOf']) + dt.timedelta(days=1)).isoformat()
        cutoff = min(before[:10], last)
        season = int(before[:4])
        key = (season, cutoff)
        if key in self.cache:
            return self.cache[key]
        games = sorted((g for g in self.data['games'] if g.get('done') is True
                        and g['season'] == season and g['date'][:10] < cutoff
                        and g['home'] in self.index and g['away'] in self.index
                        and number(g.get('hs')) is not None and number(g.get('as')) is not None),
                       key=lambda g: (g['date'], g['id']))
        rows = {metric: [] for metric in DEFAULTS}
        own_games = collections.defaultdict(list)
        for g in games:
            for home in (True, False):
                t, opp = (g['home'], g['away']) if home else (g['away'], g['home'])
                location = 0 if g.get('neutral') else (1 if home else -1)
                stats = g.get('stats', {}).get(t, {})
                points = float(g['hs'] if home else g['as'])
                own_games[t].append({'id': g['id'], 'date': g['date'], 'opponent': opp,
                                     'url': g.get('url'), 'opponentName': self.data['teams'][opp].get('name', opp), 'points': points})
                rows['points'].append((t, opp, location, points, 1.0))
                yards = number(stats.get('yards'))
                if yards is not None and yards >= 0:
                    rows['yards'].append((t, opp, location, yards, 1.0))
                plays = number(stats.get('plays'))
                if plays is not None and plays > 0:
                    for metric in ('success', 'explosive'):
                        count = number(stats.get(metric))
                        if count is not None and 0 <= count <= plays:
                            rows[metric].append((t, opp, location, count / plays, min(plays / 60, 1.5)))
        fits = {metric: self._fit(values, DEFAULTS[metric]) for metric, values in rows.items()}
        profiles = {}
        for t in self.ids:
            i = self.index[t]
            metrics = {}
            for metric, fitted in fits.items():
                off, defense = fitted['offense'][i], fitted['defense'][i]
                if metric in ('success', 'explosive'):
                    off, defense = float(np.clip(off, 0, 1)), float(np.clip(defense, 0, 1))
                metrics[metric] = {'offense': float(off), 'defenseAllowed': float(defense),
                                   'offenseGames': fitted['offenseGames'][t],
                                   'defenseGames': fitted['defenseGames'][t]}
            schedule = own_games[t]
            opp_strengths = [fits['points']['offense'][self.index[g['opponent']]] -
                             fits['points']['defense'][self.index[g['opponent']]] for g in schedule]
            profiles[t] = {'games': len(schedule), 'metrics': metrics,
                           'opponentStrength': float(np.mean(opp_strengths)) if opp_strengths else None,
                           'sourceGames': schedule}
        result = {'version': VERSION, 'season': season, 'cutoff': cutoff, 'games': len(games),
                  'profiles': profiles, 'averages': {k: v['mean'] for k, v in fits.items()},
                  'priorGames': PRIOR_GAMES}
        self.cache[key] = result
        return result

    def _fit(self, rows, default):
        n = len(self.ids)
        off_n, def_n = collections.Counter(), collections.Counter()
        if not rows:
            return {'mean': default, 'offense': np.full(n, default), 'defense': np.full(n, default),
                    'offenseGames': off_n, 'defenseGames': def_n}
        rr, cc, vv, target = [], [], [], []
        # Columns: intercept, offense effects, defense-allowed effects, venue.
        for r, (t, opp, venue, value, weight) in enumerate(rows):
            scale = math.sqrt(weight)
            rr.extend([r] * 4)
            cc.extend([0, 1 + self.index[t], 1 + n + self.index[opp], 1 + 2 * n])
            vv.extend([scale, scale, scale, venue * scale])
            target.append(value * scale)
            off_n[t] += 1
            def_n[opp] += 1
        width = 2 * n + 2
        design = coo_matrix((vv, (rr, cc)), shape=(len(rows), width)).tocsr()
        penalty = np.full(width, math.sqrt(PRIOR_GAMES)); penalty[0] = 0
        fitted = lsqr(vstack([design, diags(penalty)]),
                      np.r_[target, np.zeros(width)], atol=1e-10, btol=1e-10)[0]
        return {'mean': float(fitted[0]), 'offense': fitted[0] + fitted[1:n + 1],
                'defense': fitted[0] + fitted[n + 1:2 * n + 1],
                'offenseGames': off_n, 'defenseGames': def_n}

    def matchup(self, game):
        rating = self.at(game['date'])
        if any(t not in self.index for t in (game['home'], game['away'])):
            return {'version': VERSION, 'status': 'unavailable_non_fbs', 'appliedToMain': False,
                    'reason': 'An opponent is outside the FBS rating pool; legacy forecast retained.'}
        return {'version': VERSION, 'status': 'adjusted', 'appliedToMain': True,
                'cutoff': rating['cutoff'], 'priorGames': PRIOR_GAMES,
                'home': rating['profiles'][game['home']], 'away': rating['profiles'][game['away']],
                'method': 'Separate offensive and defensive ratings from earlier-date FBS games, adjusted for the opponent and venue. Small samples shrink toward average. FCS games remain in team records but are excluded from these performance inputs.'}


def adjusted_features(raw, matchup):
    values = list(raw)
    if not matchup.get('appliedToMain'):
        return values
    h, a = matchup['home']['metrics'], matchup['away']['metrics']
    net = lambda p, key: p[key]['offense'] - p[key]['defenseAllowed']
    values[1] = 100 * (net(h, 'success') - net(a, 'success'))
    values[2] = net(h, 'points') - net(a, 'points')
    values[3] = sum(p['points'][k] for p in (h, a) for k in ('offense', 'defenseAllowed')) / 2
    values[6] = 100 * (h['explosive']['offense'] - a['explosive']['offense'])
    values[7] = h['yards']['offense'] - a['yards']['offense']
    return values
