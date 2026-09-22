#!/usr/bin/env python3
"""Consolidates model state into one JSON blob for the public site (site/data.json).
Read-only: never edits state, never fetches anything — run this after update.sh.
Run tendencies.py separately first (venv-only) if you want fresh tendency data;
this script just reads state/tendencies.json if it exists, and skips that section if not."""
import json, os, glob, re, time
from collections import defaultdict
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
sensitivity = json.load(open('state/sensitivity.json')) if os.path.exists('state/sensitivity.json') else None
actuals = {int(k): v for k, v in json.load(open('state/actuals.json')).items()} if os.path.exists('state/actuals.json') else {}

nfl_week = week.get('nfl_week', 1)
gameday_files = sorted(glob.glob('state/week[0-9]*.json'),
                       key=lambda f: int(os.path.basename(f)[4:-5]))
gameday = json.load(open(gameday_files[-1])) if gameday_files else {'players': [], 'injuries': []}

seas = season_out['season']
meta = season_out['meta']
sched = season_in['sched']

standings_rows = sorted(seas.items(), key=lambda kv: (-kv[1]['po'], -kv[1]['title']))

# Sleeper's roster.settings.wins/losses/fpts (state/standings.json, via refresh.py) lags the
# real per-week matchup results by up to a day around a week boundary - e.g. right after
# Monday Night Football locks a week, settings can still reflect only last week's record for
# several hours. actuals.json (this week's real matchup points) has no such lag, so the
# actual record/points-for shown on the site are computed from it directly instead.
def real_record(team):
    w = l = tie = 0; pf = 0.0
    for wk, scores in sorted(actuals.items()):
        if team not in scores:
            continue
        pf += scores[team]
        opp = sched[team][wk - 1] if wk - 1 < len(sched[team]) else None
        if opp in scores:
            if scores[team] > scores[opp]: w += 1
            elif scores[team] < scores[opp]: l += 1
            else: tie += 1
    return w, l, pf

odds_table = []
for i, (t, v) in enumerate(standings_rows, 1):
    w, l, pf = real_record(t)
    odds_table.append({
        'team': t, 'rank': i,
        'proj_w': round(v['w'], 1), 'proj_l': round(14 - v['w'], 1),
        'playoff_pct': round(v['po'] * 100, 1), 'bye_pct': round(v['bye'] * 100, 1),
        'title_pct': round(v['title'] * 100, 1), 'is_user': t == ME,
        'actual_w': w, 'actual_l': l,
        'pf': round(pf, 1), 'faab': standings.get(t, {}).get('faab_left', 100),
    })

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

# rivalry pods: the schedule is built as three 4-team pods where every team plays every
# podmate exactly twice (all other opponents once) - detect that structure directly from
# the schedule rather than hardcoding it, so it stays correct if the schedule ever changes.
# each true 2-meeting rivalry is counted from both teams' own opponent lists, so it
# reaches 4 (2 meetings x 2 directions); a normal 1-meeting pairing only reaches 2.
pair_count = defaultdict(int)
for t, opps in sched.items():
    for o in opps:
        pair_count[frozenset((t, o))] += 1
rival_of = defaultdict(set)
for pair, n in pair_count.items():
    if n >= 4 and len(pair) == 2:
        a, b = tuple(pair)
        rival_of[a].add(b); rival_of[b].add(a)

pod_seen = set(); pods = []
for t in sched:
    if t in pod_seen:
        continue
    pod, frontier = {t}, [t]
    while frontier:
        x = frontier.pop()
        for y in rival_of[x]:
            if y not in pod:
                pod.add(y); frontier.append(y)
    pods.append(sorted(pod)); pod_seen |= pod

def pod_record(team, podmates):
    w = l = margins = 0
    biggest = None
    for wk, scores in sorted(actuals.items()):
        opp = sched[team][wk - 1] if wk - 1 < len(sched[team]) else None
        if opp not in podmates or team not in scores or opp not in scores:
            continue
        diff = scores[team] - scores[opp]
        if diff > 0: w += 1
        elif diff < 0: l += 1
        if biggest is None or abs(diff) > abs(biggest[2]):
            biggest = (team, opp, diff, wk)
    return w, l, biggest

rivalries = []
for pod in pods:
    members = []
    closest, blowout = None, None
    for t in pod:
        w, l, big = pod_record(t, set(pod) - {t})
        row = seas.get(t, {})
        members.append({'team': t, 'pod_w': w, 'pod_l': l,
                        'playoff_pct': round(row.get('po', 0) * 100, 1),
                        'title_pct': round(row.get('title', 0) * 100, 1),
                        'actual_w': standings.get(t, {}).get('w', 0),
                        'actual_l': standings.get(t, {}).get('l', 0)})
        if big:
            a, b, diff, wk = big
            if closest is None or abs(diff) < abs(closest[2]): closest = big
            if blowout is None or abs(diff) > abs(blowout[2]): blowout = big
    members.sort(key=lambda m: (-m['pod_w'], m['pod_l'], -m['playoff_pct']))
    next_game = None
    for wk in range(nfl_week, 15):
        for t in pod:
            o = sched[t][wk - 1] if wk - 1 < len(sched[t]) else None
            if o in pod and wk not in actuals:
                next_game = {'week': wk, 'a': t, 'b': o}; break
        if next_game:
            break
    rivalries.append({
        'members': members,
        'leader': members[0]['team'] if members else None,
        'closest_game': {'a': closest[0], 'b': closest[1], 'margin': round(abs(closest[2]), 1), 'week': closest[3]} if closest else None,
        'biggest_blowout': {'a': blowout[0], 'b': blowout[1], 'margin': round(abs(blowout[2]), 1), 'week': blowout[3]} if blowout else None,
        'next_game': next_game,
    })
rivalries.sort(key=lambda r: ME in [m['team'] for m in r['members']], reverse=True)

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
    'sensitivity': sensitivity,
    'rivalries': rivalries,
}

os.makedirs('site', exist_ok=True)
json.dump(data, open('site/data.json', 'w'), indent=1)
print(f"site/data.json written — week {nfl_week}, {len(odds_table)} teams, {len(matchups)} matchups, "
     f"{len(performers)} performers, {len(data['highlights'])} highlights, "
     f"{len(waivers['moves']) if waivers else 0} waiver moves, tendencies: {'yes' if tendencies else 'no'}")
