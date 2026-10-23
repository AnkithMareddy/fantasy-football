#!/usr/bin/env python3
"""Daily puzzles for the arcade, in two tracks.

  NFL KNOWLEDGE    — Guess the Player, Guess the NFL Game. Things any football fan
                     could get; nothing about this particular league.
  LEAGUE KNOWLEDGE — Guess the Game, Guess the Manager, Guess the Lineup. These only
                     mean anything if you are in ShowMeYourTDs.

Originally all three puzzles leaned on league data, which made the whole page
impenetrable to anyone outside the league. Splitting the tracks keeps the insider
puzzles while giving a visitor something they can actually play.

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
try:
    NFLG = json.load(open('state/nflgames.json'))
except FileNotFoundError:
    NFLG = {}                  # history.py hasn't run since this was added
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


# ---------------------------------------------------------- guess the NFL game (NFL track)
def nfl_game_puzzles():
    """A real NFL result, identified from the score alone. No fantasy knowledge needed."""
    out = []
    for w, games in NFLG.items():
        for g in games:
            h, a = g['home'], g['away']
            if h['score'] is None or a['score'] is None:
                continue
            total = h['score'] + a['score']
            margin = abs(h['score'] - a['score'])
            winner = h if h['score'] >= a['score'] else a
            out.append({
                'answer': f"{a['name']} at {h['name']}",
                'week': int(w),
                'clues': [
                    {'k': 'WEEK', 'v': f"Week {w}"},
                    {'k': 'COMBINED POINTS', 'v': str(total)},
                    {'k': 'MARGIN', 'v': f"{margin} point" + ('s' if margin != 1 else '')},
                    {'k': 'WINNING TEAM', 'v': winner['ab']},
                    {'k': 'FINAL SCORE', 'v': f"{a['score']}-{h['score']}"},
                    {'k': 'ROAD TEAM', 'v': a['name']},
                ],
            })
    out.sort(key=lambda x: (x['week'], x['answer']))
    return out


# ------------------------------------------------------- guess the lineup (league track)
def lineup_puzzles():
    """Nine starters from one team-week. Whose lineup was it?

    The sharpest league-knowledge test on the page: you have to know who actually
    rosters whom, not just who is good.
    """
    out = []
    for w in sorted(FINAL, key=int):
        for team, row in PW.get(str(w), {}).items():
            names = [(P.get(str(pid)) or {}).get('n') for pid in row.get('starters', [])]
            names = [n for n in names if n]
            if len(names) < 6:
                continue
            tot = row.get('total') or 0
            out.append({
                'answer': disp(team),
                'clues': [
                    {'k': 'THREE OF THE NINE', 'v': ', '.join(names[:3])},
                    {'k': 'THREE MORE', 'v': ', '.join(names[3:6])},
                    {'k': 'WEEK', 'v': f"Week {w}"},
                    {'k': 'THEY SCORED', 'v': f"{tot:.1f} pts"},
                    {'k': 'REST OF THE LINEUP', 'v': ', '.join(names[6:]) or 'n/a'},
                ],
            })
    out.sort(key=lambda x: x['answer'])
    return out


if __name__ == '__main__':
    players = player_puzzles()
    games = game_puzzles()
    managers = manager_puzzles()
    nflgames = nfl_game_puzzles()
    lineups = lineup_puzzles()
    teams = sorted({m['answer'] for m in managers})
    # `track` drives the two groups on the page: nfl = playable by any football fan,
    # league = only means something if you're in ShowMeYourTDs.
    out = {
        'player':   {'track': 'nfl',    'label': 'GUESS THE PLAYER',
                     'pool': players, 'answers': sorted({p['answer'] for p in players})},
        'nflgame':  {'track': 'nfl',    'label': 'GUESS THE NFL GAME',
                     'pool': nflgames, 'answers': sorted({g['answer'] for g in nflgames})},
        'game':     {'track': 'league', 'label': 'GUESS THE MATCHUP',
                     'pool': games, 'answers': sorted({g['answer'] for g in games})},
        'manager':  {'track': 'league', 'label': 'GUESS THE MANAGER',
                     'pool': managers, 'answers': teams},
        'lineup':   {'track': 'league', 'label': 'GUESS THE LINEUP',
                     'pool': lineups, 'answers': teams},
        'built': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
    json.dump(out, open('site/puzzles.json', 'w'), separators=(',', ':'))
    kb = os.path.getsize('site/puzzles.json') // 1024
    print(f"wrote site/puzzles.json ({kb} KB)")
    print(f"  NFL track    — {len(players)} player, {len(nflgames)} NFL game")
    print(f"  LEAGUE track — {len(games)} matchup, {len(managers)} manager, {len(lineups)} lineup")
