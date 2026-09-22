#!/usr/bin/env python3
"""Consolidates model state into one JSON blob for the public site (site/data.json).
Read-only: never edits state, never fetches anything — run this after update.sh.
Run tendencies.py separately first (venv-only) if you want fresh tendency data;
this script just reads state/tendencies.json if it exists, and skips that section if not."""
import json, os, glob, re, time
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

# Index by the week the site is actually labeled with (nfl_week), not first_sim_week -
# once this week's results lock into actuals, first_sim_week jumps to next week, and
# indexing by that would silently show next week's matchups under this week's header.
w_idx = nfl_week - 1

def norm(x):
    x = (x or '').lower().replace('.', '').replace("'", '').replace('-', ' ')
    x = re.sub(r'\b(jr|sr|ii|iii|iv)\b', '', x); return ' '.join(x.split())

BAD_STATUS = {'Out', 'Doubtful', 'Questionable', 'IR', 'PUP', 'Sus', 'SUS', 'NA', 'Injured Reserve', 'Day-To-Day'}
live_pts = (week.get('live') or {}).get(str(nfl_week)) or {}
live_detail = week.get('live_detail') or {}
espn_inj = {norm(i['player']): i for i in gameday.get('injuries', [])}

def side(team):
    # only the currently in-progress week has per-starter detail (refresh.py only tracks
    # `cur`, the week not yet locked into actuals); a completed week has none, so the card
    # falls back to a plain final score instead of a stale or empty live overlay.
    if not live_detail.get(team):
        return None
    lineup = []
    for st in live_detail.get(team, []):
        e = espn_inj.get(norm(st['name']))
        status = (e or {}).get('status') or st.get('inj')
        lineup.append({'pid': st['pid'], 'name': st['name'], 'pos': st['pos'], 'nfl': st['nfl'],
                       'pts': round(float(st.get('pts') or 0), 2), 'state': st.get('state', 'todo'),
                       'inj': status if status in BAD_STATUS else None,
                       'inj_type': (e or {}).get('type')})
    states = [l['state'] for l in lineup]
    return {'live': live_pts.get(team), 'lineup': lineup,
            'done': states.count('final'), 'in_play': states.count('live'), 'to_play': states.count('todo'),
            'alerts': [l for l in lineup if l['inj']]}

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
                     'b': o, 'b_winpct': round(b['winpct'] * 100), 'b_pts': round(b['mean'], 1),
                     'a_side': side(t), 'b_side': side(o)})

performers = [{'name': r['name'], 'team': r['team'], 'pts': r['fp'], 'owner': r['own']}
              for r in gameday.get('players', [])[:12]]
owner_by_name = {norm(p['n']): t for t, roster in season_in['teams'].items() for p in roster}
all_inj = [dict(i, owner=owner_by_name.get(norm(i['player']))) for i in gameday.get('injuries', [])]
injuries = sorted(all_inj, key=lambda i: i['owner'] is None)[:20]

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
    'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'live_fetched_at': week.get('fetched_at'),
    'live_games': {'final': week.get('final_teams', []), 'live': week.get('live_teams', [])},
    'week_final': nfl_week < meta['first_sim_week'],
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
