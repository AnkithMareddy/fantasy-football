#!/usr/bin/env python3
"""League-wide waiver/free-agent activity, with FAAB context, for every team (not just ours).
Reads Sleeper's transactions feed. state/waivers.json always holds the full season-to-date
move list (for the site — a persistent wire, not a rolling window). stdout / state/latest_waivers.txt
only lists what's new since the last run (state/waivers_seen.json bookmark) — that's what the
text report should read, so it doesn't repeat old news to the user every run.
Doesn't touch the season sim or any projection number."""
import json, os, subprocess
os.chdir(os.path.dirname(os.path.abspath(__file__)))
L = "1385346462094741504"
MAX_MOVES_STORED = 60  # site display cap, newest first

def get(u):
    out = subprocess.run(['curl', '-s', '--max-time', '30', u], capture_output=True, text=True)
    if not out.stdout.strip():
        raise SystemExit(f"FETCH FAILED: {u}")
    return json.loads(out.stdout)

P = json.load(open('sleeper/players.json'))
week = json.load(open('state/week.json'))
nfl_week = week.get('nfl_week', 1)
standings = json.load(open('state/standings.json'))

draft = get(f'https://api.sleeper.app/v1/league/{L}/drafts')[0]
user_slot = {uid: int(s) for uid, s in (draft.get('draft_order') or {}).items()}
slot_name = {int(k): v for k, v in json.load(open('sleeper/slot_name.json')).items()}
rid_team = {}
for r in get(f'https://api.sleeper.app/v1/league/{L}/rosters'):
    slot = user_slot.get(r.get('owner_id'))
    if slot is not None:
        rid_team[r['roster_id']] = slot_name[slot]

def pname(pid):
    p = P.get(pid)
    return (p['n'], p['p']) if p else (pid, '?')

seen_file = 'state/waivers_seen.json'
last_seen = json.load(open(seen_file)).get('last_seen', 0) if os.path.exists(seen_file) else 0

all_moves = []
for leg in range(1, nfl_week + 1):
    for t in get(f'https://api.sleeper.app/v1/league/{L}/transactions/{leg}'):
        if t['status'] != 'complete' or t['type'] not in ('waiver', 'free_agent'):
            continue
        team = rid_team.get((t.get('roster_ids') or [None])[0])
        if not team:
            continue
        added = [{'name': n, 'pos': p} for n, p in (pname(pid) for pid in (t.get('adds') or {}))]
        dropped = [{'name': n, 'pos': p} for n, p in (pname(pid) for pid in (t.get('drops') or {}))]
        faab = (t.get('settings') or {}).get('waiver_bid') or 0
        all_moves.append({'team': team, 'added': added, 'dropped': dropped, 'faab': faab,
                          'type': t['type'], 'created': t['created']})

all_moves.sort(key=lambda m: -m['created'])
max_created = max((m['created'] for m in all_moves), default=last_seen)
new_moves = [m for m in all_moves if m['created'] > last_seen]
faab_left = {t: standings.get(t, {}).get('faab_left', 100) for t in slot_name.values()}

json.dump({'as_of_week': nfl_week, 'moves': all_moves[:MAX_MOVES_STORED], 'faab_left': faab_left},
         open('state/waivers.json', 'w'), indent=1)
json.dump({'last_seen': max_created}, open(seen_file, 'w'))

if not new_moves:
    print("LEAGUE WAIVER WIRE — no moves cleared since the last check")
else:
    print(f"LEAGUE WAIVER WIRE — {len(new_moves)} move(s) since the last check")
    for m in new_moves:
        add_s = ', '.join(f"{a['name']} ({a['pos']})" for a in m['added']) or '(nothing)'
        drop_s = ', '.join(f"{d['name']} ({d['pos']})" for d in m['dropped']) or '(nothing)'
        bid_s = f"${m['faab']} FAAB" if m['type'] == 'waiver' else "free agent, no bid"
        print(f"  {m['team']:<22} +{add_s}  -{drop_s}  [{bid_s}]")

print("\nFAAB REMAINING (of $100)")
for t, v in sorted(faab_left.items(), key=lambda kv: -kv[1]):
    print(f"  {t:<22}{v:>4}")
