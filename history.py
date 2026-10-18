#!/usr/bin/env python3
"""Archive per-player weekly scoring + NFL kickoff times, which Sleeper only serves live.

refresh.py keeps team totals (state/actuals.json) but throws away the per-player
breakdown once a week rolls over, so there is nothing to replay a past matchup from.
This pulls /matchups/{w} for every played week and keeps the full picture.

Writes: state/player_weeks.json (per-week, per-team starters + every player's points)
        state/kickoffs.json    (per-week NFL team -> kickoff timestamp, for event ordering)
Safe to re-run; it rewrites both files from scratch."""
import json, os, subprocess
import league
L = league.league_id()          # LEAGUE_ID env var, else this league
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def get(u):
    out = subprocess.run(['curl', '-s', '--max-time', '60', u], capture_output=True, text=True)
    if not out.stdout.strip():
        raise SystemExit(f"FETCH FAILED: {u}")
    return json.loads(out.stdout)


P = json.load(open('sleeper/players.json'))
slot_name = {int(k): v for k, v in json.load(open('sleeper/slot_name.json')).items()}
draft = get(f'https://api.sleeper.app/v1/league/{L}/drafts')[0]
user_slot = {uid: int(s) for uid, s in (draft.get('draft_order') or {}).items()}
rid_team = {}
for r in get(f'https://api.sleeper.app/v1/league/{L}/rosters'):
    slot = user_slot.get(r.get('owner_id'))
    if slot is not None:
        rid_team[r['roster_id']] = slot_name[slot]

cur = int(get('https://api.sleeper.app/v1/state/nfl').get('week') or 1)

# kickoff time per NFL team per week — this is what orders a replay. Two players on the
# same NFL team always score in the same window; a Thursday game resolves before Sunday.
kickoffs = {}
for w in range(1, min(cur, 14) + 1):
    wk = {}
    for e in get(f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/'
                 f'scoreboard?seasontype=2&week={w}').get('events', []):
        comp = e['competitions'][0]
        for c in comp['competitors']:
            ab = {'WSH': 'WAS'}.get(c['team']['abbreviation'], c['team']['abbreviation'])
            wk[ab] = {'kick': e['date'], 'status': comp['status']['type']['name']}
    kickoffs[str(w)] = wk
    print(f"week {w}: {len(wk)} teams scheduled")
json.dump(kickoffs, open('state/kickoffs.json', 'w'), indent=1)

weeks = {}
for w in range(1, min(cur, 14) + 1):
    ms = get(f'https://api.sleeper.app/v1/league/{L}/matchups/{w}')
    # matchup_id pairs the two rosters that played each other that week
    pair = {}
    for m in ms:
        if m['roster_id'] in rid_team:
            pair.setdefault(m.get('matchup_id'), []).append(rid_team[m['roster_id']])
    out = {}
    for m in ms:
        team = rid_team.get(m['roster_id'])
        if not team:
            continue
        sides = pair.get(m.get('matchup_id')) or []
        opp = next((t for t in sides if t != team), None)
        starters = [p for p in (m.get('starters') or []) if p and p != '0']
        sp = m.get('starters_points') or []
        out[team] = {
            'opp': opp,
            'total': round(m.get('points') or 0, 2),
            'starters': starters,
            'starter_pts': [round((sp[i] if i < len(sp) else 0) or 0, 2)
                            for i in range(len(starters))],
            'all_pts': {pid: round(pts or 0, 2)
                        for pid, pts in (m.get('players_points') or {}).items()},
        }
    weeks[str(w)] = out
    scored = sum(1 for t in out.values() if t['total'] > 0)
    print(f"week {w}: {len(out)} teams, {scored} with points")
json.dump(weeks, open('state/player_weeks.json', 'w'), indent=1)
print(f"\nwrote state/player_weeks.json (weeks 1-{min(cur, 14)}) and state/kickoffs.json")
