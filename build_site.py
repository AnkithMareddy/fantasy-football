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
weekly_awards = json.load(open('state/weekly_awards.json')) if os.path.exists('state/weekly_awards.json') else None
waivers = json.load(open('state/waivers.json')) if os.path.exists('state/waivers.json') else None
injury_overrides = {k: v for k, v in json.load(open('state/injury_overrides.json')).items() if not k.startswith('_')} \
    if os.path.exists('state/injury_overrides.json') else {}

nfl_week = week.get('nfl_week', 1)
gameday_files = sorted(glob.glob('state/week[0-9]*.json'),
                       key=lambda f: int(os.path.basename(f)[4:-5]))
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

# injury predictions: the harsh-model's expected games missed (season_out['games_missed'],
# key "Name | FantasyTeam") enriched with researched return weeks/notes where we have them.
player_info = {}
for t, roster in season_in['teams'].items():
    for p in roster:
        player_info[(p['n'], t)] = p

games_missed = season_out.get('games_missed', {})
predictions = {}
for key, g in games_missed.items():
    name, team = key.rsplit(' | ', 1)
    info = player_info.get((name, team), {})
    ovr = injury_overrides.get(name)
    predictions[name] = {
        'name': name, 'team': team, 'pos': info.get('pos'), 'nfl_team': info.get('tm'),
        'pid': info.get('pid'), 'current_status': info.get('inj'),
        'expected_games_missed': round(g, 1),
        'return_week': ovr.get('return_week') if ovr else None,
        'note': ovr.get('note') if ovr else None, 'source': ovr.get('source') if ovr else None,
    }
for name, ovr in injury_overrides.items():
    if name in predictions:
        continue
    hit = next(((t, p) for (n, t), p in player_info.items() if n == name), None)
    if not hit:
        continue
    t, info = hit
    predictions[name] = {
        'name': name, 'team': t, 'pos': info.get('pos'), 'nfl_team': info.get('tm'),
        'pid': info.get('pid'), 'current_status': info.get('inj'), 'expected_games_missed': 0,
        'return_week': ovr.get('return_week'), 'note': ovr.get('note'), 'source': ovr.get('source'),
    }
injury_predictions = sorted(predictions.values(), key=lambda r: -r['expected_games_missed'])[:20]

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
    'weekly_awards': weekly_awards,
    'waivers': waivers,
    'injury_predictions': injury_predictions,
}

os.makedirs('site', exist_ok=True)
json.dump(data, open('site/data.json', 'w'), indent=1)
print(f"site/data.json written — week {nfl_week}, {len(odds_table)} teams, {len(matchups)} matchups, "
     f"{len(performers)} performers, {len(data['highlights'])} highlights, "
     f"{len(waivers['moves']) if waivers else 0} waiver moves, tendencies: {'yes' if tendencies else 'no'}")
