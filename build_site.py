#!/usr/bin/env python3
"""Consolidates model state into one JSON blob for the public site (site/data.json).
Read-only: never edits state, never fetches anything — run this after update.sh.
Run tendencies.py separately first (venv-only) if you want fresh tendency data;
this script just reads state/tendencies.json if it exists, and skips that section if not."""
import json, os, glob
os.chdir(os.path.dirname(os.path.abspath(__file__)))

ME = 'uaintgotjuicehoeido'

season_out = json.load(open('season_out.json'))
season_in = json.load(open('season_input.json'))
standings = json.load(open('state/standings.json'))
week = json.load(open('state/week.json'))
lines = json.load(open('state/lines.json')) if os.path.exists('state/lines.json') else {}
tendencies = json.load(open('state/tendencies.json')) if os.path.exists('state/tendencies.json') else None
team_display = json.load(open('sleeper/team_display.json')) if os.path.exists('sleeper/team_display.json') else {}
highlights_state = json.load(open('state/highlights.json')) if os.path.exists('state/highlights.json') else {'highlights': [], 'recaps': []}

nfl_week = week.get('nfl_week', 1)
gameday_files = sorted(glob.glob('state/week*.json'))
gameday_files = [f for f in gameday_files if f != 'state/week.json']
gameday = json.load(open(gameday_files[-1])) if gameday_files else {'players': [], 'injuries': []}

seas = season_out['season']
meta = season_out['meta']
sched = season_in['sched']

standings_rows = sorted(seas.items(), key=lambda kv: (-kv[1]['po'], -kv[1]['title']))
odds_table = [{
    'team': t, 'rank': i,
    'proj_w': round(v['w'], 1), 'proj_l': round(14 - v['w'], 1),
    'playoff_pct': round(v['po'] * 100, 1), 'bye_pct': round(v['bye'] * 100, 1),
    'title_pct': round(v['title'] * 100, 1), 'is_user': t == ME,
    'actual_w': standings.get(t, {}).get('w', 0), 'actual_l': standings.get(t, {}).get('l', 0),
    'pf': round(standings.get(t, {}).get('pf', 0), 1), 'faab': standings.get(t, {}).get('faab_left', 100),
} for i, (t, v) in enumerate(standings_rows, 1)]

w_idx = meta['first_sim_week'] - 1
matchups = []
seen = set()
for t in sched:
    o = sched[t][w_idx]
    if (o, t) in seen:
        continue
    seen.add((t, o))
    a = season_out['weekly'][t][w_idx]
    b = season_out['weekly'][o][w_idx]
    matchups.append({'a': t, 'a_winpct': round(a['winpct'] * 100), 'a_pts': round(a['mean'], 1),
                     'b': o, 'b_winpct': round(b['winpct'] * 100), 'b_pts': round(b['mean'], 1)})

performers = [{'name': r['name'], 'team': r['team'], 'pts': r['fp'], 'owner': r['own']}
              for r in gameday.get('players', [])[:12]]
injuries = gameday.get('injuries', [])[:15]

market = {'lines': lines, 'week': nfl_week}

data = {
    'league': 'ShowMeYourTDs', 'season': 2026, 'week': nfl_week,
    'sims': meta['sims'], 'user_team': ME,
    'generated_note': 'Regenerated from live Sleeper/ESPN/DraftKings/nflverse data each pipeline run.',
    'teams': team_display,
    'standings': odds_table,
    'matchups': matchups,
    'top_performers': performers,
    'injuries': injuries,
    'market': market,
    'tendencies': tendencies,
    'highlights': highlights_state.get('highlights', []),
    'recaps': highlights_state.get('recaps', []),
}

os.makedirs('site', exist_ok=True)
json.dump(data, open('site/data.json', 'w'), indent=1)
print(f"site/data.json written — week {nfl_week}, {len(odds_table)} teams, {len(matchups)} matchups, "
     f"{len(performers)} performers, {len(data['highlights'])} highlights, tendencies: {'yes' if tendencies else 'no'}")
