#!/usr/bin/env python3
"""Start/sit analysis for the user's team, uaintgotjuicehoeido.
Compares the actual current lineup (from live_detail, i.e. whatever is set on Sleeper right now)
against a conservative-projection optimal lineup, and flags any slot where a bench player
projects higher than the starter in the same slot group.

Conservative projection = season.py's ppg, discounted by half a position's weekly coefficient
of variation (runseason.py's CV), so a boom-or-bust player has to clear a real bar before we'd
bench a steadier one for them. Already-played games use the real score, never a projection.
Players out this week (bye, injury_overrides return_week, or a Sleeper OUT/DOUBTFUL/IR/PUP/SUS/NA
status) are floored to 0 and flagged as unavailable rather than benched for underperforming.

Prints to stdout — update.sh redirects that to state/latest_startsit.txt.
Read-only otherwise: never edits the roster or the live Sleeper lineup."""
import json, os, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))

TEAM = 'uaintgotjuicehoeido'
CV = {'QB': 0.40, 'RB': 0.60, 'WR': 0.65, 'TE': 0.75, 'K': 0.50, 'DEF': 0.85}
BUFFER_K = 0.5   # how hard we discount toward the floor; 0 = mean, 1 = full CV below mean
SLOT_ORDER = ['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'K', 'DEF']

def norm(x):
    x = (x or '').lower().replace('.', '').replace("'", '').replace('-', ' ')
    x = re.sub(r'\b(jr|sr|ii|iii|iv)\b', '', x); return ' '.join(x.split())

season_input = json.load(open('season_input.json'))
roster = season_input['teams'][TEAM]
wj = json.load(open('state/week.json'))
this_week = int(wj.get('nfl_week', 1))
played_teams = set(wj.get('played_teams', []))
live = wj.get('live_detail', {}).get(TEAM, [])
bench_actual = wj.get('bench_points', {}).get(TEAM, {})

OVR = {}
if os.path.exists('state/injury_overrides.json'):
    OVR = {norm(k): v for k, v in json.load(open('state/injury_overrides.json')).items() if not k.startswith('_')}

by_pid = {p['pid']: p for p in roster if p.get('pid')}
current_starter_pids = {row['pid'] for row in live}

def unavailable_reason(p):
    if p.get('bye') == this_week:
        return 'BYE'
    o = OVR.get(norm(p['n']))
    if o and 'return_week' in o and int(o['return_week']) > this_week:
        return f"out (back wk{o['return_week']})"
    st = (p.get('inj') or '').upper()
    if p.get('ir') or st in ('IR', 'PUP', 'SUS', 'NA', 'COV'):
        return f"out ({st or 'IR'})"
    if st in ('OUT', 'DOUBTFUL'):
        return f"out ({st.title()})"
    return None

def value_for(p):
    """Returns (points, tag) — tag is 'actual', 'proj', or the unavailable reason."""
    reason = unavailable_reason(p)
    nfl_played = p.get('tm') in played_teams
    if nfl_played:
        pid = p.get('pid')
        row = next((r for r in live if r['pid'] == pid), None)
        if row and row.get('played'):
            return row['pts'], 'actual'
        if pid in bench_actual:
            return bench_actual[pid], 'actual'
        # played but no data surfaced (bye/inactive that week) — treat as 0 actual
        return 0.0, 'actual'
    if reason:
        return 0.0, reason
    floor = p['ppg'] * (1 - BUFFER_K * CV.get(p['pos'], 0.5))
    return round(floor, 2), 'proj'

rows = []
for p in roster:
    pts, tag = value_for(p)
    rows.append({**p, 'val': pts, 'tag': tag, 'starting': p.get('pid') in current_starter_pids})

def best(pos_list, pool, exclude):
    cands = [r for r in pool if r['pos'] in pos_list and r['n'] not in exclude]
    cands.sort(key=lambda r: -r['val'])
    return cands

used = set()
optimal = {}
for pos, n in [('QB', 1), ('RB', 2), ('WR', 2), ('TE', 1)]:
    picks = best([pos], rows, used)[:n]
    optimal[pos] = picks
    used |= {p['n'] for p in picks}
flex_pick = best(['RB', 'WR', 'TE'], rows, used)[:1]
optimal['FLEX'] = flex_pick
used |= {p['n'] for p in flex_pick}
for pos, n in [('K', 1), ('DEF', 1)]:
    picks = best([pos], rows, used)[:n]
    optimal[pos] = picks
    used |= {p['n'] for p in picks}

optimal_names = set()
for grp in optimal.values():
    optimal_names |= {p['n'] for p in grp}

current_names = {r['n'] for r in rows if r['starting']}

# swaps: names in optimal but not currently starting, paired against a name that IS
# currently starting at the same position group but not in optimal, and hasn't played yet (locked = can't swap)
swap_in = [r for r in rows if r['n'] in optimal_names and r['n'] not in current_names]
swap_out_pool = [r for r in rows if r['n'] in current_names and r['n'] not in optimal_names]

lines = []
lines.append(f"START/SIT (Week {this_week}, conservative floor = ppg minus half the position's weekly variance, {TEAM})")

if not swap_in:
    lines.append("Current lineup matches the conservative-optimal lineup. No changes recommended.")
else:
    for inp in sorted(swap_in, key=lambda r: -r['val']):
        # best matching bench-out candidate: prefer same position, else any unlocked current starter
        cands = [o for o in swap_out_pool if o['pos'] == inp['pos'] and o['tag'] != 'actual']
        if not cands:
            cands = [o for o in swap_out_pool if o['tag'] != 'actual']
        if not cands:
            continue  # everyone who'd be benched already played — can't change it now
        out_p = min(cands, key=lambda r: r['val'])
        swap_out_pool.remove(out_p)
        gap = inp['val'] - out_p['val']
        in_tag = '' if inp['tag'] == 'proj' else f" [{inp['tag']}]"
        out_tag = '' if out_p['tag'] == 'proj' else f" [{out_p['tag']}]"
        lines.append(f"Start {inp['n']} ({inp['pos']}, {inp['val']:.1f} floor{in_tag}) over "
                     f"{out_p['n']} ({out_p['pos']}, {out_p['val']:.1f} floor{out_tag}) — "
                     f"+{gap:.1f} pt floor edge.")

locked_conflicts = [r for r in swap_out_pool if r['n'] not in optimal_names and r['tag'] == 'actual']
if locked_conflicts:
    lines.append("(Already locked in and already played, so no change possible there this week: "
                 + ", ".join(f"{r['n']} ({r['val']:.1f} actual)" for r in locked_conflicts) + ".)")

lines.append("")
lines.append("Full bench, ranked by floor:")
bench_rows = sorted([r for r in rows if not r['starting']], key=lambda r: -r['val'])
for r in bench_rows:
    tagstr = 'BYE' if r['tag'] == 'BYE' else (r['tag'] if r['tag'] not in ('proj', 'actual') else '')
    suffix = f" [{tagstr}]" if tagstr else (' [actual]' if r['tag'] == 'actual' else '')
    lines.append(f"  {r['n']:<22} {r['pos']:<4} {r['val']:>5.1f}{suffix}")

print("\n".join(lines))
