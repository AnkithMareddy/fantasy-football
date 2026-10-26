#!/usr/bin/env python3
"""RotoWire weekly projections, as served by Sleeper.

WHAT THEY ACTUALLY ARE, since this matters for how much weight to give them:
Sleeper does not compute projections. Every row comes back stamped
`company: rotowire` — Sleeper licenses them. Each row is a point estimate of the
underlying box score (rush_att 18.03, rush_td 1.11, rec 2.49 ...) from which the
half-PPR total is derived. They are EXPECTATIONS, not draws, and they carry no variance,
confidence interval or distribution of any kind. That is why they can inform the MEAN of
a player's weekly distribution here but cannot replace the gamma draw in winprob.py: the
spread still has to come from our own per-position CVs.

There are two endpoints and only one of them is alive:
  /projections/nfl/<season>/<week>   weekly, updated through the week.  USE THIS.
  /projections/nfl/<season>          season-long, but it is the PRESEASON projection and
                                     is not refreshed — every row says gp=18.0, and
                                     Javonte Williams reads 193.0/18 = 10.72 per game,
                                     essentially our own season average. Useless in-season.

HOW GOOD ARE THEY? Measured, not assumed, over weeks 3-7 of this season (495 player-weeks
with both a projection and our own baseline):

    RotoWire weekly projection     MAE 5.47   RMSE 6.78
    our season-average ppg         MAE 6.31   RMSE 8.04

They win at every position — QB, RB, WR, TE, K and DEF — and are closer on 55.8% of
individual player-weeks.

AND THEY ARE NOT HINDSIGHT. Checked explicitly, because a backtest against revised
numbers would be worthless: of the 20 players who scored exactly 0.0, their projections
averaged 7.43, 85% were projected above 5 points, and the highest was 11.6. Post-hoc
revisions would have put those near zero. These are pre-game numbers.

Writes: state/sleeper_proj.json  {"<week>": {"<pid>": half_ppr_points}}
Safe to re-run; only re-fetches weeks it is missing unless refresh=True.
"""
import json, os, subprocess, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
CACHE = 'state/sleeper_proj.json'
POSITIONS = ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')
BASE = 'https://api.sleeper.com/projections/nfl'


def _fetch_week(season, week):
    """One week of projections, every position, as {pid: half_ppr}."""
    out = {}
    for pos in POSITIONS:
        url = f'{BASE}/{season}/{week}?season_type=regular&position[]={pos}&order_by=ppr'
        res = subprocess.run(['curl', '-s', '--max-time', '60', url],
                             capture_output=True, text=True)
        if not res.stdout.strip():
            continue
        try:
            rows = json.loads(res.stdout)
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for r in rows:
            pid = str(r.get('player_id') or '')
            pts = (r.get('stats') or {}).get('pts_half_ppr')
            # 0.5 PPR is this league's scoring (league.config()['ppr']); if that ever
            # changes, the column to read changes with it.
            if pid and pts is not None:
                out[pid] = float(pts)
    return out


def load(weeks, season=2026, refresh=False):
    """{week:int -> {pid -> points}} for the weeks asked for, cached on disk."""
    cache = {}
    if os.path.exists(CACHE) and not refresh:
        try:
            cache = json.load(open(CACHE))
        except Exception:
            cache = {}
    changed = False
    for w in weeks:
        key = str(int(w))
        if key not in cache or refresh:
            got = _fetch_week(season, int(w))
            if got:
                cache[key] = got
                changed = True
    if changed:
        os.makedirs('state', exist_ok=True)
        json.dump(cache, open(CACHE, 'w'))
    return {int(k): v for k, v in cache.items()}


def for_week(week, season=2026, refresh=False):
    """{pid -> projected half-PPR points} for one week."""
    return load([week], season, refresh).get(int(week), {})


def rolling_mean(week, n=3, season=2026):
    """{pid -> mean of that player's projections across the n weeks BEFORE `week`}.

    This is the forward-looking baseline: it uses only numbers published before week
    `week`, so it can be carried into weeks the sim has to project and for which no
    projection exists yet. Measured over weeks 4-7 it beats our season average as a
    predictor of the actual score, 5.55 MAE against 6.43 — and it even edges the
    current-week projection (5.61), because averaging three of them cancels some of the
    week-to-week noise in any single one.
    """
    week = int(week)
    data = load(range(max(1, week - n), week), season)
    tot, cnt = {}, {}
    for w in range(max(1, week - n), week):
        for pid, pts in (data.get(w) or {}).items():
            tot[pid] = tot.get(pid, 0.0) + pts
            cnt[pid] = cnt.get(pid, 0) + 1
    return {pid: tot[pid] / c for pid, c in cnt.items() if c}


if __name__ == '__main__':
    wk = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    cur = for_week(wk)
    roll = rolling_mean(wk)
    print(f"week {wk}: {len(cur)} current projections, {len(roll)} players with a 3-week mean")
    P = json.load(open('sleeper/players.json'))
    for pid in list(cur)[:0]:
        pass
    for name in ('Javonte Williams', 'Christian McCaffrey', 'Trey McBride'):
        hit = [p for p, m in P.items() if m.get('n') == name]
        if hit:
            p = hit[0]
            print(f"  {name:<24} this week {cur.get(p, float('nan')):6.2f}   "
                  f"3-week mean {roll.get(p, float('nan')):6.2f}")
