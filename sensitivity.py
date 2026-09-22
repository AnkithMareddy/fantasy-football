#!/usr/bin/env python3
"""Runs the season sim twice more under different assumptions, to show how sensitive the
playoff/title odds are to modeling choices rather than treating the baseline as gospel:
  - "High Chaos"   : weekly scoring variance x1.3 (more upset-prone, boom/bust weeks)
  - "Healthy World": injury hazard x0.4 (roughly what the league would look like if nobody
                     else got hurt the rest of the way either - isolates how much of the
                     baseline odds are the harsh injury model doing the work)
Both are read-only "what if" comparisons against the just-computed baseline (season_out.json) -
neither ever overwrites it, and nothing here feeds back into the main sim, start/sit, or any
other projection. Writes state/sensitivity.json."""
import json, os, subprocess, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

SIMS = os.environ.get('SIMS', '10000')
SCENARIOS = [
    ('high_chaos', 'High Chaos', {'CV_MULT': '1.3'}, 'Weekly scoring variance up 30% - a more upset-prone season.'),
    ('healthy_world', 'Healthy World', {'HAZ_MULT': '0.4'}, "Injury hazard down 60% - roughly nobody else getting hurt the rest of the way."),
]

baseline = json.load(open('season_out.json'))

runs = {'baseline': {'label': 'Baseline', 'note': 'The actual model every other report uses.', 'season': baseline['season']}}
for key, label, env, note in SCENARIOS:
    out_path = f'state/sensitivity_{key}.json'
    run_env = {**os.environ, 'SIMS': SIMS, 'SEASON_OUT': out_path, **env}
    r = subprocess.run(['python3', 'runseason.py'], env=run_env, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"SCENARIO {label} FAILED:\n{r.stderr}", file=sys.stderr)
        continue
    runs[key] = {'label': label, 'note': note, 'season': json.load(open(out_path))['season']}

teams = sorted(baseline['season'], key=lambda t: -baseline['season'][t]['po'])
rows = []
for t in teams:
    po = {k: round(v['season'][t]['po'] * 100, 1) for k, v in runs.items()}
    title = {k: round(v['season'][t]['title'] * 100, 1) for k, v in runs.items()}
    po_vals = list(po.values()); title_vals = list(title.values())
    rows.append({'team': t, 'playoff_pct': po, 'title_pct': title,
                'playoff_spread': round(max(po_vals) - min(po_vals), 1),
                'title_spread': round(max(title_vals) - min(title_vals), 1)})

scenarios_meta = [{'key': 'baseline', 'label': 'Baseline', 'note': 'The actual model every other report uses.'}] + \
    [{'key': k, 'label': l, 'note': n} for k, l, _, n in SCENARIOS]
json.dump({'scenarios': scenarios_meta, 'teams': rows}, open('state/sensitivity.json', 'w'), indent=1)

print(f"MODEL SENSITIVITY ({SIMS} sims/scenario)")
print(f"{'TEAM':<22}" + "".join(f"{s['label'] + ' PO%':>16}" for s in scenarios_meta) + f"{'SPREAD':>9}")
for r in sorted(rows, key=lambda r: -r['playoff_spread']):
    print(f"{r['team']:<22}" + "".join(f"{r['playoff_pct'][s['key']]:>16.1f}" for s in scenarios_meta) + f"{r['playoff_spread']:>9.1f}")
