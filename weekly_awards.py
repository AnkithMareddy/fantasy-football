#!/usr/bin/env python3
"""League-wide weekly awards, Sleeper-report style: best/worst team, players of the week,
benchwarmers of the week (best player NOT started, by position), and lineup efficiency
(actual starters' points / the best possible lineup from that team's full roster that week).

Uses Sleeper's own scoring for the target week (points/starters_points/players_points come
straight from our league's matchup endpoint, so this is already under our real scoring rules).

Targets the most recently COMPLETED week (max key in state/actuals.json). Writes
state/weekly_awards.json. Read-only: never edits state, never affects the season model."""
import json, os, subprocess
os.chdir(os.path.dirname(os.path.abspath(__file__)))
L = "1385346462094741504"

def get(u):
    out = subprocess.run(['curl', '-s', '--max-time', '30', u], capture_output=True, text=True)
    return json.loads(out.stdout)

actuals = json.load(open('state/actuals.json'))
if not actuals:
    print("No completed weeks yet — nothing to award.")
    json.dump({'week': None}, open('state/weekly_awards.json', 'w'))
    raise SystemExit(0)
WEEK = max(int(k) for k in actuals)

slot_name = {int(k): v for k, v in json.load(open('sleeper/slot_name.json')).items()}
draft = get(f'https://api.sleeper.app/v1/league/{L}/drafts')[0]
user_slot = {uid: int(s) for uid, s in (draft.get('draft_order') or {}).items()}
rosters_raw = get(f'https://api.sleeper.app/v1/league/{L}/rosters')
rid_team = {}
for r in rosters_raw:
    slot = user_slot.get(r.get('owner_id'))
    if slot is not None:
        rid_team[r['roster_id']] = slot_name[slot]

P = json.load(open('sleeper/players.json'))
CV = {'QB': 0.40, 'RB': 0.60, 'WR': 0.65, 'TE': 0.75, 'K': 0.50, 'DEF': 0.85}  # unused here, kept for reference

def pinfo(pid):
    p = P.get(pid, {})
    return p.get('n', pid), p.get('p'), p.get('t')

def best_lineup(players):
    """players: list of {pid,pos,pts}. Returns max possible starting-lineup total."""
    used = set()
    total = 0.0
    for pos, n in [('QB', 1), ('RB', 2), ('WR', 2), ('TE', 1)]:
        cands = sorted([p for p in players if p['pos'] == pos and p['pid'] not in used], key=lambda p: -p['pts'])[:n]
        total += sum(p['pts'] for p in cands)
        used |= {p['pid'] for p in cands}
    flex = sorted([p for p in players if p['pos'] in ('RB', 'WR', 'TE') and p['pid'] not in used], key=lambda p: -p['pts'])[:1]
    total += sum(p['pts'] for p in flex)
    used |= {p['pid'] for p in flex}
    for pos, n in [('K', 1), ('DEF', 1)]:
        cands = sorted([p for p in players if p['pos'] == pos and p['pid'] not in used], key=lambda p: -p['pts'])[:n]
        total += sum(p['pts'] for p in cands)
        used |= {p['pid'] for p in cands}
    return round(total, 2)

matchups = get(f'https://api.sleeper.app/v1/league/{L}/matchups/{WEEK}')

teams = {}
all_players = []      # {team, pid, name, pos, nfl, pts, started}
for m in matchups:
    team = rid_team.get(m['roster_id'])
    if not team:
        continue
    starters = set(m.get('starters') or [])
    pp = m.get('players_points') or {}
    roster_players = []
    for pid, pts in pp.items():
        name, pos, nfl = pinfo(pid)
        started = pid in starters
        roster_players.append({'pid': pid, 'pos': pos, 'pts': pts or 0.0})
        all_players.append({'team': team, 'pid': pid, 'name': name, 'pos': pos, 'nfl': nfl,
                            'pts': round(pts or 0.0, 2), 'started': started})
    actual = round(m.get('points') or sum(m.get('starters_points') or []), 2)
    max_pts = best_lineup(roster_players)
    teams[team] = {'actual': actual, 'max': max_pts,
                   'efficiency': round(100 * actual / max_pts, 1) if max_pts else None,
                   'matchup_id': m.get('matchup_id')}

# win/loss per team, by matchup_id pairing
by_matchup = {}
for team, t in teams.items():
    by_matchup.setdefault(t['matchup_id'], []).append(team)
for mid, pair in by_matchup.items():
    if len(pair) != 2:
        continue
    a, b = pair
    winner = a if teams[a]['actual'] >= teams[b]['actual'] else b
    loser = b if winner == a else a
    teams[winner]['result'] = 'W'
    teams[loser]['result'] = 'L'

best_team = max(teams.items(), key=lambda kv: kv[1]['actual'])
worst_team = min(teams.items(), key=lambda kv: kv[1]['actual'])
losses = [(t, v) for t, v in teams.items() if v.get('result') == 'L']
wins = [(t, v) for t, v in teams.items() if v.get('result') == 'W']
highest_in_loss = max(losses, key=lambda kv: kv[1]['actual']) if losses else None
lowest_in_win = min(wins, key=lambda kv: kv[1]['actual']) if wins else None
most_efficient = max(teams.items(), key=lambda kv: kv[1]['efficiency'] or 0)
least_efficient = min(teams.items(), key=lambda kv: kv[1]['efficiency'] or 999)

POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
players_of_week = {}
benchwarmers_of_week = {}
for pos in POSITIONS:
    pool = [p for p in all_players if p['pos'] == pos]
    started_pool = [p for p in pool if p['started']]
    if started_pool:
        players_of_week[pos] = max(started_pool, key=lambda p: p['pts'])
    bench_pool = [p for p in pool if not p['started']]
    if bench_pool:
        benchwarmers_of_week[pos] = max(bench_pool, key=lambda p: p['pts'])

efficiency_rank = sorted(teams.items(), key=lambda kv: -(kv[1]['efficiency'] or 0))

out = {
    'week': WEEK,
    'best_team': {'team': best_team[0], **best_team[1]},
    'worst_team': {'team': worst_team[0], **worst_team[1]},
    'highest_pts_in_loss': {'team': highest_in_loss[0], **highest_in_loss[1]} if highest_in_loss else None,
    'lowest_pts_in_win': {'team': lowest_in_win[0], **lowest_in_win[1]} if lowest_in_win else None,
    'most_efficient': {'team': most_efficient[0], **most_efficient[1]},
    'least_efficient': {'team': least_efficient[0], **least_efficient[1]},
    'efficiency_rank': [{'team': t, **v} for t, v in efficiency_rank],
    'players_of_week': players_of_week,
    'benchwarmers_of_week': benchwarmers_of_week,
}
json.dump(out, open('state/weekly_awards.json', 'w'), indent=1)

print(f"WEEK {WEEK} AWARDS")
print(f"Best team: {best_team[0]} ({best_team[1]['actual']})   Worst team: {worst_team[0]} ({worst_team[1]['actual']})")
print(f"Most efficient: {most_efficient[0]} ({most_efficient[1]['efficiency']}%)   "
     f"Least efficient: {least_efficient[0]} ({least_efficient[1]['efficiency']}%)")
if highest_in_loss:
    print(f"Highest pts in a loss: {highest_in_loss[0]} ({highest_in_loss[1]['actual']})")
if lowest_in_win:
    print(f"Lowest pts in a win: {lowest_in_win[0]} ({lowest_in_win[1]['actual']})")
print("Players of the week:", {k: f"{v['name']} ({v['pts']}, {v['team']})" for k, v in players_of_week.items()})
print("Benchwarmers of the week:", {k: f"{v['name']} ({v['pts']}, {v['team']})" for k, v in benchwarmers_of_week.items()})
