#!/usr/bin/env python3
"""Refresh live league state from Sleeper. Run before season.py / runseason.py / gameday.py.
Writes: sleeper/rosters.json (live, slot-keyed), state/standings.json, state/actuals.json, state/week.json"""
import json, os, subprocess, time
import league
L = league.league_id()          # LEAGUE_ID env var, else this league
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def get(u):
    out = subprocess.run(['curl', '-s', '--max-time', '60', u], capture_output=True, text=True)
    if not out.stdout.strip():
        raise SystemExit(f"FETCH FAILED: {u}")
    return json.loads(out.stdout)

os.makedirs('state', exist_ok=True)

# player map (carries Sleeper's injury_status). Sleeper asks for roughly one pull a day; 3h keeps
# injury tags reasonably live while still being ~8 pulls/day, far under their rate limit.
PLAYERS_TTL_S = 3 * 3600
pm = 'sleeper/players.json'
if not os.path.exists(pm) or time.time() - os.path.getmtime(pm) > PLAYERS_TTL_S:
    subprocess.run(['curl', '-s', '--max-time', '180', '-o', 'sleeper/players_raw.json',
                    'https://api.sleeper.app/v1/players/nfl'], check=True)
    raw = json.load(open('sleeper/players_raw.json'))
    slim = {}
    for k, v in raw.items():
        nm = v.get('full_name') or ' '.join(x for x in (v.get('first_name'), v.get('last_name')) if x) or k
        slim[k] = {'n': nm, 'p': v.get('position'), 't': v.get('team'),
                   'inj': v.get('injury_status'), 'st': v.get('status'),
                   # clue fields for the daily puzzles (dailygames.py)
                   'num': v.get('number'), 'age': v.get('age'),
                   'exp': v.get('years_exp'), 'col': v.get('college')}
    json.dump(slim, open(pm, 'w'))
P = json.load(open(pm))

state = get('https://api.sleeper.app/v1/state/nfl')
users_raw = get(f'https://api.sleeper.app/v1/league/{L}/users')
users = {u['user_id']: u.get('display_name', '?') for u in users_raw}
draft = get(f'https://api.sleeper.app/v1/league/{L}/drafts')[0]
user_slot = {uid: int(s) for uid, s in (draft.get('draft_order') or {}).items()}   # stable even if names change
slot_name = {int(k): v for k, v in json.load(open('sleeper/slot_name.json')).items()}

# current display info for the site (team name / avatar can change mid-season; the model's
# internal team key above never does — this is purely cosmetic, read by build_site.py)
team_display = {}
for u in users_raw:
    slot = user_slot.get(u['user_id'])
    if slot is None:
        continue
    team = slot_name[slot]
    md = u.get('metadata') or {}
    custom_name = (md.get('team_name') or '').strip()
    avatar_url = md.get('avatar') or (f"https://sleepercdn.com/avatars/{u['avatar']}" if u.get('avatar') else None)
    team_display[team] = {
        'handle': u.get('display_name', team),
        'team_name': custom_name or u.get('display_name', team),
        'avatar': avatar_url,
    }
json.dump(team_display, open('sleeper/team_display.json', 'w'), indent=1)

rid_team, rosters_out, standings = {}, {}, {}
for r in get(f'https://api.sleeper.app/v1/league/{L}/rosters'):
    slot = user_slot.get(r.get('owner_id'))
    if slot is None:
        continue
    team = slot_name[slot]
    rid_team[r['roster_id']] = team
    ir = set(r.get('reserve') or [])
    rosters_out[str(slot)] = [
        {'name': P.get(pid, {}).get('n', pid), 'pos': P.get(pid, {}).get('p'), 'team': P.get(pid, {}).get('t'),
         'pid': pid, 'ir': pid in ir, 'inj': P.get(pid, {}).get('inj')}
        for pid in (r.get('players') or [])]
    s = r.get('settings', {})
    standings[team] = {'w': s.get('wins', 0), 'l': s.get('losses', 0), 't': s.get('ties', 0),
                       'pf': round(s.get('fpts', 0) + s.get('fpts_decimal', 0) / 100, 2),
                       'faab_left': 100 - s.get('waiver_budget_used', 0)}
json.dump(rosters_out, open('sleeper/rosters.json', 'w'), indent=1)
json.dump(standings, open('state/standings.json', 'w'), indent=1)

def week_final(w):
    ev = get(f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={w}').get('events', [])
    return bool(ev) and all(e['competitions'][0]['status']['type']['name'] == 'STATUS_FINAL' for e in ev)

cur = int(state.get('week') or 1)
actuals, live = {}, {}
for w in range(1, min(cur, 14) + 1):
    pts = {rid_team[m['roster_id']]: round(m.get('points') or 0, 2)
           for m in get(f'https://api.sleeper.app/v1/league/{L}/matchups/{w}') if m['roster_id'] in rid_team}
    (actuals if (w < cur or week_final(w)) else live)[w] = pts
json.dump(actuals, open('state/actuals.json', 'w'), indent=1)
# in-progress week: which starters already played, and their real points
live_detail = {}
played = set()
week_teams, final_teams, live_teams = set(), set(), set()
bench_points = {}
if cur not in actuals and cur <= 14:
    for e in get(f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={cur}').get('events', []):
        status = e['competitions'][0]['status']['type']['name']
        for c in e['competitions'][0]['competitors']:
            ab = {'WSH': 'WAS'}.get(c['team']['abbreviation'], c['team']['abbreviation'])
            week_teams.add(ab)
            if status != 'STATUS_SCHEDULED':
                played.add(ab)
                (final_teams if status == 'STATUS_FINAL' else live_teams).add(ab)
    for m in get(f'https://api.sleeper.app/v1/league/{L}/matchups/{cur}'):
        team = rid_team.get(m['roster_id'])
        if not team: continue
        sp = m.get('starters_points') or []
        starter_ids = set(m.get('starters') or [])
        live_detail[team] = [
            {'pid': pid, 'name': P.get(pid, {}).get('n', pid), 'pos': P.get(pid, {}).get('p'),
             'nfl': P.get(pid, {}).get('t'), 'pts': (sp[i] if i < len(sp) else 0) or 0,
             'played': P.get(pid, {}).get('t') in played, 'slot': i,
             'inj': P.get(pid, {}).get('inj'),
             'state': ('final' if P.get(pid, {}).get('t') in final_teams else 'live' if P.get(pid, {}).get('t') in live_teams
                       else 'todo' if P.get(pid, {}).get('t') in week_teams else 'bye')}
            for i, pid in enumerate(m.get('starters') or []) if pid and pid != '0']
        # bench players' actual points this week too, so start/sit can see what a benched player scored
        pp = m.get('players_points') or {}
        bench_points[team] = {
            pid: round(pts or 0, 2) for pid, pts in pp.items()
            if pid not in starter_ids and P.get(pid, {}).get('t') in played}
json.dump({'nfl_week': cur, 'live': live, 'live_detail': live_detail,
           'bench_points': bench_points, 'played_teams': sorted(played),
           'final_teams': sorted(final_teams), 'live_teams': sorted(live_teams),
           'fetched_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
          open('state/week.json', 'w'), indent=1)

print(f"NFL week {cur} | final fantasy weeks locked in: {sorted(actuals) or 'none yet'}")
print(f"{'TEAM':<22}{'W-L':>7}{'PF':>9}{'FAAB':>6}")
for t, s in sorted(standings.items(), key=lambda kv: (-kv[1]['w'], -kv[1]['pf'])):
    print(f"{t:<22}{s['w']:>3}-{s['l']:<3}{s['pf']:>9.1f}{s['faab_left']:>6}")
if live:
    print("live/partial this week:", {t: p for t, p in live[max(live)].items()})
