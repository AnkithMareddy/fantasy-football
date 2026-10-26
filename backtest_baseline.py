#!/usr/bin/env python3
"""Re-test, every week, whether a different season baseline would beat the current one.

WHY THIS EXISTS
On 2026-10-25 we nearly swapped the season-long baseline the Monte Carlo runs on for a
rolling mean of RotoWire's weekly projections, on the strength of a backtest. The
backtest was measured on the wrong population — players RotoWire actively projects —
and reported 5.55 MAE against 6.43. Measured against what season.py ACTUALLY feeds the
sim (a preseason projection board divided by 17) across the full roster, the same idea
came out at 6.49 against 6.35: worse. The best gated version improved MAE by 1.4% at
0.94 standard errors, which is noise.

Had we shipped it, every playoff and title number on the site would have moved on the
basis of a population artifact. So this file is the guard: it runs the comparison the
same way every week, on the full population, against the real baseline, and reports the
paired significance rather than a bare MAE. A change to the season baseline should wait
until this says it is significant.

CANDIDATES
  board        the preseason projection board / 17 — what the sim uses today
  rolling      mean of a player's RotoWire projections over the prior 3 weeks
  gated        rolling where RotoWire covered all 3 prior weeks, board otherwise
  blend50      half board, half rolling

Run:  python3 backtest_baseline.py          (wired into update.sh; writes state/latest_baseline.txt)
"""
import json, os, statistics, sys
from math import sqrt

os.chdir(os.path.dirname(os.path.abspath(__file__)))
import sleeperproj
import winprob as W

MIN_WEEK = 4          # need 3 prior weeks of projections to form a rolling mean
COVERAGE = 3          # weeks of coverage required for the gated candidate


def gather():
    PW = json.load(open('state/player_weeks.json'))
    KO = json.load(open('state/kickoffs.json'))
    P = json.load(open('sleeper/players.json'))
    board = W.ppg_index()
    rows = []
    for w in sorted(PW, key=int):
        wi = int(w)
        if wi < MIN_WEEK:
            continue
        games = KO.get(w) or {}
        data = sleeperproj.load(range(max(1, wi - 3), wi))
        tot, cnt = {}, {}
        for k in range(max(1, wi - 3), wi):
            for pid, pts in (data.get(k) or {}).items():
                tot[pid] = tot.get(pid, 0.0) + pts
                cnt[pid] = cnt.get(pid, 0) + 1
        seen = set()
        for row in PW[w].values():
            for pid, actual in row['all_pts'].items():
                pid = str(pid)
                if pid in seen:
                    continue
                # a bye is not a data point about how good a player is
                if (P.get(pid) or {}).get('t') not in games:
                    continue
                bd = board.get(pid)
                if not bd or not bd[0]:
                    continue
                seen.add(pid)
                c = cnt.get(pid, 0)
                rows.append({'week': wi, 'actual': actual, 'board': bd[0],
                             'roll': (tot[pid] / c) if c else None, 'cover': c})
    return rows


CANDIDATES = {
    'board':   lambda r: r['board'],
    'rolling': lambda r: r['roll'] if r['roll'] is not None else r['board'],
    'gated':   lambda r: r['roll'] if (r['cover'] >= COVERAGE and r['roll'] is not None) else r['board'],
    'blend50': lambda r: (0.5 * r['roll'] + 0.5 * r['board']) if r['roll'] is not None else r['board'],
}


def main():
    rows = gather()
    if len(rows) < 50:
        print(f"baseline backtest: only {len(rows)} player-weeks, too few to say anything")
        return
    errs = {k: [abs(r['actual'] - f(r)) for r in rows] for k, f in CANDIDATES.items()}
    base = errs['board']
    out = []
    out.append(f"SEASON BASELINE BACKTEST — {len(rows)} player-weeks, weeks {MIN_WEEK}+")
    out.append("Candidate vs the baseline the sim actually uses (preseason board / 17).")
    out.append(f"{'candidate':<10}{'MAE':>8}{'RMSE':>8}{'vs board':>10}{'paired SE':>11}{'verdict':>18}")
    for k in ('board', 'rolling', 'gated', 'blend50'):
        e = errs[k]
        mae = statistics.mean(e)
        rmse = (sum(x * x for x in e) / len(e)) ** 0.5
        if k == 'board':
            out.append(f"{k:<10}{mae:>8.3f}{rmse:>8.3f}{'—':>10}{'—':>11}{'(current)':>18}")
            continue
        d = [b - x for b, x in zip(base, e)]
        se = statistics.stdev(d) / sqrt(len(d)) if len(d) > 1 else float('inf')
        z = (statistics.mean(d) / se) if se else 0.0
        verdict = 'ADOPT (sig.)' if z > 1.96 else ('worse' if z < -1.96 else 'not significant')
        out.append(f"{k:<10}{mae:>8.3f}{rmse:>8.3f}{statistics.mean(d):>+10.3f}{se:>11.3f}{verdict:>18}")
    out.append("")
    out.append("A candidate needs z > 1.96 (95%) before it should replace the season baseline.")
    out.append("Until then season.py and runseason.py stay on the board; weekly projections")
    out.append("are used in startsit.py only, where weekly signals are allowed.")
    text = "\n".join(out)
    print(text)
    return text


if __name__ == '__main__':
    main()
