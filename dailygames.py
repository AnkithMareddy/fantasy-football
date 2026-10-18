#!/usr/bin/env python3
"""Daily puzzles for the arcade: Guess the Player, Guess the Game, Guess the Manager.

Ships a POOL rather than one puzzle a day. The page picks today's entry by hashing the
date, so everyone opening the site on the same day gets the same puzzle, and the pool
keeps working even if the nightly run fails for a week.

Everything is drawn from data the pipeline already has — rostered players, the replay
win% curves, and each manager's own draft and roster behaviour. No third-party photos:
the player clue is a pixel jersey we draw from team colours and a number, which is both
legally clean and a better fit for the 8-bit theme than a blurred headshot.

Writes: site/puzzles.json
"""
import json, os, statistics

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from nflcolors import TEAM_COLORS

P = json.load(open('sleeper/players.json'))
PW = json.load(open('state/player_weeks.json'))
PB = json.load(open('state/playback.json'))
SI = json.load(open('season_input.json'))
try:
    TD = json.load(open('sleeper/team_display.json'))
except FileNotFoundError:
    TD = {}
FINAL = set(json.load(open('state/actuals.json')))


def disp(t):
    return (TD.get(t) or {}).get('team_name') or t


# ---------------------------------------------------------------- guess the player
def player_puzzles():
    """Rostered players with enough of a season to be guessable, hardest clue first."""
    owner = {}
    for team, roster in SI['teams'].items():
        for p in roster:
            if p.get('pid'):
                owner[str(p['pid'])] = team

    weekly = {}
    for w, teams in PW.items():
        if w not in FINAL:
            continue
        for row in teams.values():
            for pid, pts in row['all_pts'].items():
                weekly.setdefault(str(pid), []).append(pts)

    out = []
    for pid, team in owner.items():
        meta = P.get(pid) or {}
        pts = [x for x in weekly.get(pid, []) if x]
        pos, nfl = meta.get('p'), meta.get('t')
        if not meta.get('n') or pos in (None, 'DEF') or nfl not in TEAM_COLORS:
            continue
        if len(pts) < 3:
            continue                     # not enough season to be fair
        hi = max(pts)
        clues = [
            # number 0 is legal and falsy — test for None, not truthiness
            {'k': 'JERSEY', 'v': f"#{meta['num']}" if meta.get('num') is not None else '#--'},
            {'k': 'POSITION', 'v': pos},
            {'k': 'BEST WEEK', 'v': f"{hi:.1f} pts"},
            {'k': 'SEASON AVG', 'v': f"{statistics.mean(pts):.1f} pts"},
            {'k': 'EXPERIENCE', 'v': (f"{meta['exp']} yr" + ('s' if (meta.get('exp') or 0) != 1 else '')
                                      + ' in the league') if meta.get('exp') is not None else 'unknown'},
            {'k': 'COLLEGE', 'v': meta.get('col') or 'unknown'},
            {'k': 'NFL TEAM', 'v': nfl},
            {'k': 'ROSTERED BY', 'v': disp(team)},
        ]
        out.append({
            'answer': meta['n'], 'pos': pos, 'nfl': nfl,
            'num': meta.get('num'), 'colors': TEAM_COLORS[nfl], 'clues': clues,
        })
    out.sort(key=lambda x: x['answer'])
    return out


# ---------------------------------------------------------------- guess the game
def game_puzzles():
    """A win% curve with both teams hidden. Which matchup was it?"""
    out = []
    for w, matchups in PB.items():
        if w not in FINAL:
            continue
        for m in matchups:
            steps = m['steps']
            if len(steps) < 4:
                continue
            swing = m['key_swing']
            if swing < 0.25:
                continue                 # a flat curve is not a puzzle
            out.append({
                'week': int(w),
                'curve': [round(s['wp'], 3) for s in steps],
                'labels': [s['label'] for s in steps],
                'answer': f"{disp(m['a'])} vs {disp(m['b'])}",
                'a_name': disp(m['a']), 'b_name': disp(m['b']),
                'final': f"{m['a_total']:.2f} - {m['b_total']:.2f}",
                'clues': [
                    {'k': 'WEEK', 'v': f"Week {w}"},
                    {'k': 'BIGGEST SWING', 'v': f"{swing*100:.0f}% in one window"},
                    {'k': 'FINAL', 'v': f"{m['a_total']:.2f} - {m['b_total']:.2f}"},
                    {'k': 'ONE TEAM', 'v': disp(m['a'])},
                ],
            })
    return out


# ---------------------------------------------------------------- guess the manager
def manager_puzzles():
    """Identify a manager from how their roster and season actually look."""
    out = []
    for team, roster in SI['teams'].items():
        by_pos = {}
        for p in roster:
            by_pos.setdefault(p['pos'], []).append(p)
        totals = [sum(PW[w][team]['total'] for w in FINAL if team in PW.get(w, {}))]
        wk = [PW[w][team]['total'] for w in sorted(FINAL, key=int) if team in PW.get(w, {})]
        if not wk:
            continue
        best = max(roster, key=lambda p: p.get('ppg') or 0)
        counts = ', '.join(f"{len(v)} {k}" for k, v in
                           sorted(by_pos.items(), key=lambda kv: -len(kv[1])))
        out.append({
            'answer': disp(team),
            'clues': [
                {'k': 'ROSTER SHAPE', 'v': counts},
                {'k': 'BEST WEEK', 'v': f"{max(wk):.1f} pts"},
                {'k': 'WORST WEEK', 'v': f"{min(wk):.1f} pts"},
                {'k': 'POINTS SO FAR', 'v': f"{sum(wk):.1f}"},
                {'k': 'BEST PLAYER', 'v': f"{best['n']} ({best['pos']})"},
            ],
        })
    out.sort(key=lambda x: x['answer'])
    return out


if __name__ == '__main__':
    players = player_puzzles()
    games = game_puzzles()
    managers = manager_puzzles()
    names = sorted({p['answer'] for p in players})
    teams = sorted({m['answer'] for m in managers})
    out = {
        'player': {'pool': players, 'answers': names},
        'game': {'pool': games, 'answers': sorted({g['answer'] for g in games})},
        'manager': {'pool': managers, 'answers': teams},
        'built': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
    json.dump(out, open('site/puzzles.json', 'w'), separators=(',', ':'))
    print(f"wrote site/puzzles.json — {len(players)} player, {len(games)} game, "
          f"{len(managers)} manager puzzles ({os.path.getsize('site/puzzles.json')//1024} KB)")
