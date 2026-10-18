#!/usr/bin/env python3
"""Export each manager's current lineup for the playable game (site/teams.json).

This is our own football game, not a port of anyone's. Nothing here is borrowed from a
commercial title: the engine, the art and the play calls are ours, and the only thing
that comes from outside is the league's own roster and each player's season average,
which is what makes playing YOUR matchup mean something.

Players are exported with the season ppg the rest of the model uses, so a stronger real
roster actually plays better in the game rather than everyone being interchangeable.
"""
import json, os
from nflcolors import TEAM_COLORS

os.chdir(os.path.dirname(os.path.abspath(__file__)))

SI = json.load(open('season_input.json'))
try:
    TD = json.load(open('sleeper/team_display.json'))
except FileNotFoundError:
    TD = {}
try:
    WK = json.load(open('state/week.json'))
except FileNotFoundError:
    WK = {}

# league average ppg per position — the engine rates a player against his own position,
# so a 15 ppg QB isn't treated as better than a 15 ppg tight end
pool = {}
for roster in SI['teams'].values():
    for p in roster:
        pool.setdefault(p['pos'], []).append(p.get('ppg') or 0.0)
AVG = {pos: (sum(v) / len(v) if v else 1.0) or 1.0 for pos, v in pool.items()}

teams = {}
for key, roster in SI['teams'].items():
    best = {}
    for p in roster:
        pos = p['pos']
        if pos not in ('QB', 'RB', 'WR', 'TE', 'K', 'DEF'):
            continue
        best.setdefault(pos, []).append(p)
    squad = {}
    for pos, players in best.items():
        players.sort(key=lambda p: -(p.get('ppg') or 0))
        keep = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1, 'K': 1, 'DEF': 1}.get(pos, 1)
        squad[pos] = [{
            'name': p['n'], 'pos': pos, 'nfl': p.get('tm'),
            'ppg': round(p.get('ppg') or 0.0, 1),
            # rating ~1.0 is league average at that position; clamped so one star can't
            # turn the game into a formality
            'rating': round(max(0.6, min(1.5, (p.get('ppg') or 0.0) / AVG.get(pos, 1.0))), 3),
            'colors': list(TEAM_COLORS.get(p.get('tm') or '', ('#2C7A3F', '#9FD39F'))),
        } for p in players[:keep]]
    teams[key] = {'name': (TD.get(key) or {}).get('team_name') or key, 'squad': squad}

out = {'teams': teams, 'week': WK.get('nfl_week'),
       'built': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
json.dump(out, open('site/teams.json', 'w'), separators=(',', ':'))
print(f"wrote site/teams.json — {len(teams)} teams "
      f"({os.path.getsize('site/teams.json')//1024} KB)")
