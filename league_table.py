#!/usr/bin/env python3
"""Phone-friendly plain-text league projections for the text report."""
import json, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open('season_out.json')); SCHED = json.load(open('season_input.json'))['sched']
ME = 'uaintgotjuicehoeido'
seas = S['season']; meta = S['meta']
rows = sorted(seas.items(), key=lambda kv: (-kv[1]['po'], -kv[1]['title']))
print(f"LEAGUE PROJECTIONS ({meta['sims']:,} sims)")
print("Team: proj record | playoffs | bye | title")
for i, (t, v) in enumerate(rows, 1):
    me = "  <- you" if t == ME else ""
    print(f"{i}. {t}: {v['w']:.1f}-{14 - v['w']:.1f} | {v['po'] * 100:.0f}% | {v['bye'] * 100:.0f}% | {v['title'] * 100:.0f}%{me}")
w = meta['first_sim_week']
if w <= 14:
    tag = " (live points included)" if meta.get('live_week_used') else ""
    print(f"\nWEEK {w} MATCHUPS, win chance{tag}")
    seen = set()
    for t in SCHED:
        o = SCHED[t][w - 1]
        if (o, t) in seen: continue
        seen.add((t, o))
        a = S['weekly'][t][w - 1]; b = S['weekly'][o][w - 1]
        print(f"{t} {a['winpct'] * 100:.0f}% ({a['mean']:.0f}) vs {o} {b['winpct'] * 100:.0f}% ({b['mean']:.0f})")
