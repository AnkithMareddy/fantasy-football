#!/usr/bin/env python3
"""Export the replay + drill data the arcade page reads.

Kept separate from build_site.py on purpose: site/data.json is already large and the
front page doesn't need any of this. Writes site/arcade.json.
"""
import json, os
from nflcolors import TEAM_COLORS

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PB = json.load(open('state/playback.json'))
DR = json.load(open('state/drills.json'))
CB = json.load(open('state/comebacks.json'))
try:
    TD = json.load(open('sleeper/team_display.json'))
except FileNotFoundError:
    TD = {}


def disp(team):
    return (TD.get(team) or {}).get('team_name') or team


weeks = {}
for w, matchups in PB.items():
    weeks[w] = [{
        'a': m['a'], 'b': m['b'], 'a_name': disp(m['a']), 'b_name': disp(m['b']),
        'a_total': m['a_total'], 'b_total': m['b_total'],
        'key_step': m['key_step'], 'key_swing': m['key_swing'],
        'steps': m['steps'],
    } for m in matchups]

drills = {w: [{**d, 'team_name': disp(d['team']), 'opp_name': disp(d['opp'])}
              for d in rows] for w, rows in DR.items()}

# team colours ride along so the page can draw jersey tokens without its own lookup table
def tint(rows):
    for r in rows or []:
        c = TEAM_COLORS.get(r.get('nfl') or '')
        if c:
            r['colors'] = list(c)
    return rows


for rows in drills.values():
    for d in rows:
        tint(d.get('lineup')); tint(d.get('options'))

# only ship spots a player can actually win — an unwinnable comeback isn't a game
comebacks = {w: [c for c in rows if c.get('winnable')] for w, rows in CB.items()}
comebacks = {w: v for w, v in comebacks.items() if v}
for rows in comebacks.values():
    for c in rows:
        tint(c.get('lineup')); tint(c.get('held'))
        for sw in c.get('swaps') or []:
            col = TEAM_COLORS.get(sw.get('in_nfl') or '')
            if col:
                sw['colors'] = list(col)

out = {'weeks': weeks, 'drills': drills, 'comebacks': comebacks,
       'built': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
json.dump(out, open('site/arcade.json', 'w'), separators=(',', ':'))
n_m = sum(len(v) for v in weeks.values())
n_d = sum(len(v) for v in drills.values())
n_c = sum(len(v) for v in comebacks.values())
print(f"wrote site/arcade.json — {n_m} replays, {n_d} drills, {n_c} comebacks across "
      f"{len(weeks)} weeks ({os.path.getsize('site/arcade.json')//1024} KB)")
