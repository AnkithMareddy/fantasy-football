#!/usr/bin/env python3
"""Win probability for a single matchup with partial information.

Imported by playback.py and drill.py. Uses the SAME gamma draw and per-position CVs as
runseason.py, so a win% here and a playoff odd there can't disagree about how a player
scores. Points already on the board are certainties; players who haven't played are draws.

The baseline is always season ppg (season_input.json). Weekly signals like Vegas lines
stay out of this on purpose — they move the current week's start/sit floor (startsit.py)
and nothing else, so one week's line can't bend the season-long model.
"""
import json, os, random

CV = {'QB': 0.40, 'RB': 0.60, 'WR': 0.65, 'TE': 0.75, 'K': 0.50, 'DEF': 0.85}
_rnd = random.Random(20261018)
gamma = _rnd.gammavariate


def draw(ppg, pos):
    """One week's score for a player. Gamma: never negative, mean preserved, right-skewed."""
    if ppg <= 0:
        return 0.0
    cv = CV.get(pos, 0.65)
    return gamma(1.0 / (cv * cv), ppg * cv * cv)


def ppg_index(path='season_input.json'):
    """pid -> (ppg, pos) for every rostered player."""
    d = json.load(open(path))
    idx = {}
    for roster in d['teams'].values():
        for p in roster:
            if p.get('pid'):
                idx[str(p['pid'])] = (p.get('ppg') or 0.0, p.get('pos'))
    return idx


def win_prob(a_locked, a_todo, b_locked, b_todo, n=20000):
    """P(team A beats team B).

    a_locked/b_locked: points already scored (float).
    a_todo/b_todo:     [(ppg, pos), ...] for starters who haven't played yet.
    Ties count as half a win, which is how Sleeper's median-free H2H actually resolves
    a dead heat often enough to matter at this sample size.
    """
    if not a_todo and not b_todo:
        return 1.0 if a_locked > b_locked else (0.0 if a_locked < b_locked else 0.5)
    wins = 0.0
    for _ in range(n):
        a = a_locked + sum(draw(p, s) for p, s in a_todo)
        b = b_locked + sum(draw(p, s) for p, s in b_todo)
        wins += 1.0 if a > b else (0.5 if a == b else 0.0)
    return wins / n


def expected(todo):
    """Mean remaining points — the gamma's mean is just ppg, so this is a plain sum."""
    return sum(p for p, _ in todo)
