#!/usr/bin/env python3
"""Start/sit analysis for the user's team, uaintgotjuicehoeido.
Compares the actual current lineup (from live_detail, i.e. whatever is set on Sleeper right now)
against a conservative-projection optimal lineup, and flags any slot where a bench player
projects higher than the starter in the same slot group.

Conservative projection = season.py's ppg, discounted by half a position's weekly coefficient
of variation (runseason.py's CV), then scaled by this week's Vegas-implied game script from
odds.py's state/lines.json (capped 0.85-1.15, RB/WR skewed opposite ways on a big spread) — so
a player in a high-scoring shootout gets a bump and one in a low-implied-total blowout gets
trimmed, without letting one week's line swing a projection wildly. Already-played games use the
real score, never a projection. Players out this week (bye, injury_overrides return_week, or a
Sleeper OUT/DOUBTFUL/IR/PUP/SUS/NA status) are floored to 0 and flagged as unavailable rather
than benched for underperforming.

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

LINES = {}
if os.path.exists('state/lines.json'):
    LINES = json.load(open('state/lines.json'))

# RotoWire's projection for THIS week, via Sleeper. Measured over weeks 3-7 it predicts a
# player's actual score better than our season average at every position (MAE 5.47 vs
# 6.31), and it is genuinely pre-game, not hindsight — see sleeperproj.py for both checks.
# This is the current week's start/sit only, which is exactly where weekly signals are
# allowed to live; the season-long ppg baseline the Monte Carlo sim runs on is untouched.
PROJ = {}
try:
    import sleeperproj
    PROJ = sleeperproj.for_week(this_week)
except Exception as e:
    print(f"(sleeper projections unavailable, falling back to season ppg: {e})")

def game_script_mult(p):
    line = LINES.get(p.get('tm'))
    if not line:
        return 1.0
    if p['pos'] == 'RB':
        return line['rb_mult']
    if p['pos'] in ('WR', 'TE'):
        return line['wr_mult']
    return line['mult']

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
    # Expectation: RotoWire's number for this week where we have one, else season ppg.
    # When we use RotoWire we deliberately DROP the Vegas game-script multiplier — their
    # projection already prices the opponent and the expected game script, so applying
    # ours on top would adjust for the same matchup twice, in the same direction.
    rw = PROJ.get(str(p.get('pid') or ''))
    if rw is not None and rw > 0:
        mean, tag, script = rw, 'rotowire', 1.0
    else:
        mean, tag, script = p['ppg'], 'proj', game_script_mult(p)
    floor = mean * (1 - BUFFER_K * CV.get(p['pos'], 0.5)) * script
    return round(floor, 2), tag

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
n_rw = sum(1 for p in roster if PROJ.get(str(p.get('pid') or '')))
lines.append(f"START/SIT (Week {this_week}, conservative floor = expectation minus half the "
             f"position's weekly variance, {TEAM})")
lines.append(f"Expectation from RotoWire's week-{this_week} projection where available "
             f"({n_rw} of {len(roster)} rostered), season ppg otherwise.")

n_swaps = 0
if swap_in:
    for inp in sorted(swap_in, key=lambda r: -r['val']):
        # A player who cannot play this week is not an upgrade on anybody. Without this
        # guard, a week where the bench is entirely on bye produces "start Shough (0.0)
        # over Stroud (0.0) — +0.0 pt floor edge": advice-shaped noise sitting exactly
        # where the real finding belongs, which is that the lineup has a hole in it.
        # Those weeks are handled by the LINEUP HOLES section instead.
        if inp['tag'] not in ('proj', 'rotowire', 'actual'):
            continue
        # best matching bench-out candidate: prefer same position, else any unlocked current starter
        cands = [o for o in swap_out_pool if o['pos'] == inp['pos'] and o['tag'] != 'actual']
        if not cands:
            cands = [o for o in swap_out_pool if o['tag'] != 'actual']
        if not cands:
            continue  # everyone who'd be benched already played — can't change it now
        out_p = min(cands, key=lambda r: r['val'])
        gap = inp['val'] - out_p['val']
        if gap < 0.1:
            continue          # a rounding-error edge is not a reason to touch the lineup
        swap_out_pool.remove(out_p)
        in_tag = '' if inp['tag'] == 'proj' else f" [{inp['tag']}]"
        out_tag = '' if out_p['tag'] == 'proj' else f" [{out_p['tag']}]"
        lines.append(f"Start {inp['n']} ({inp['pos']}, {inp['val']:.1f} floor{in_tag}) over "
                     f"{out_p['n']} ({out_p['pos']}, {out_p['val']:.1f} floor{out_tag}) — "
                     f"+{gap:.1f} pt floor edge.")
        n_swaps += 1

if not swap_in:
    lines.append("Current lineup matches the conservative-optimal lineup. No changes recommended.")
elif not n_swaps:
    # The optimal lineup differs on paper, but every difference was a player who can't
    # play or an edge inside rounding error. Say that, rather than reporting a fake swap.
    lines.append("No swap worth making from the bench — every candidate is either out this "
                 "week or inside rounding error of the man already starting.")

locked_conflicts = [r for r in swap_out_pool if r['n'] not in optimal_names and r['tag'] == 'actual']
if locked_conflicts:
    lines.append("(Already locked in and already played, so no change possible there this week: "
                 + ", ".join(f"{r['n']} ({r['val']:.1f} actual)" for r in locked_conflicts) + ".)")

# ---- holes: a starter who cannot play, and nobody on the bench who can -------------
# This is the section week 8 needed and didn't have. A starter floored to 0 isn't a
# start/sit question, it's a roster question, and when the bench is on bye too the answer
# is not on the roster at all — so look outside it.
AVAILABLE_TAGS = ('proj', 'rotowire', 'actual')
holes = [r for r in rows if r['starting'] and r['tag'] not in AVAILABLE_TAGS]
# Sidecar for autoreport.py: the hole, and the best pickup for it. Written as data rather
# than left for something downstream to scrape back out of the printed text.
hole_recs = []
if holes:
    lines.append("")
    lines.append("LINEUP HOLES — starters who will score 0 unless you act:")
    bench_ok = [r for r in rows if not r['starting'] and r['tag'] in AVAILABLE_TAGS]
    try:
        import freeagents
        FA_OK = True
    except Exception as e:
        FA_OK, _fa_err = False, e
    for h in sorted(holes, key=lambda r: -r['ppg']):
        lines.append(f"  {h['n']} ({h['pos']}, {h['tm']}) — {h['tag']}. "
                     f"Normally {h['ppg']:.1f} ppg, so this is roughly what it costs you.")
        # FLEX means an RB/WR/TE hole can be covered by any of the three; QB/K/DEF cannot.
        group = ['RB', 'WR', 'TE'] if h['pos'] in ('RB', 'WR', 'TE') else [h['pos']]
        cover = sorted([b for b in bench_ok if b['pos'] in group], key=lambda r: -r['val'])
        if cover:
            c = cover[0]
            lines.append(f"      -> bench cover: {c['n']} ({c['pos']}, {c['val']:.1f} floor). Start him.")
            continue
        if not FA_OK:
            lines.append(f"      -> no bench cover (free-agent list unavailable: {_fa_err})")
            continue
        fas = freeagents.top(h['pos'], n=3, week=this_week)
        if not fas:
            lines.append("      -> no bench cover, and nothing projectable on the wire either.")
        else:
            lines.append("      -> NO bench cover. Best available on the wire this week:")
            hole_recs.append({'out': h['n'], 'pos': h['pos'], 'lost_ppg': round(h['ppg'], 1),
                              'best': fas[0]['n'], 'best_tm': fas[0]['tm'],
                              'best_proj': fas[0]['proj']})
            for f in fas:
                # Say why, not just how much. For a QB the shape that matters is a high
                # total with his team trailing (volume); for a defence it is the opposite,
                # a favourite in a low-scoring game.
                ln = LINES.get(f['tm']) or {}
                why = ''
                if ln.get('spread') is not None:
                    sp = ln['spread']
                    why = (f"  ({f['tm']} {'-' if sp < 0 else '+'}{abs(sp):g} vs "
                           f"{ln.get('opp')}, O/U {ln.get('total')})")
                lines.append(f"           {f['n']:<24} {f['tm']:<4} {f['proj']:>5.1f} proj{why}")
    faab = None
    try:
        faab = json.load(open('state/waivers.json')).get('faab_left', {}).get(TEAM)
    except Exception:
        pass
    if faab is not None:
        lines.append(f"  (You have ${faab} of FAAB left.)")
    # Adding anybody means dropping somebody, and the cheapest drop is rarely obvious in a
    # week when half the roster reads 0.0 because it is on bye. Rank by season ppg — what
    # the player is worth the rest of the way — not by this week's floor.
    need_adds = sum(1 for h in holes
                    if not [b for b in bench_ok
                            if b['pos'] in (['RB', 'WR', 'TE'] if h['pos'] in ('RB', 'WR', 'TE')
                                            else [h['pos']])])
    if need_adds:
        droppable = sorted((r for r in rows if not r['starting']), key=lambda r: r['ppg'])[:3]
        if droppable:
            lines.append(f"  Room for {need_adds} pickup{'s' if need_adds > 1 else ''} — "
                         "cheapest to drop, by season ppg (not this week's bye-week 0):")
            for d in droppable:
                lines.append(f"      {d['n']:<22} {d['pos']:<4} {d['ppg']:>5.1f} ppg")
        lines.append("  A defence you are streaming anyway is usually a cheaper drop than "
                     "any of these.")

lines.append("")
lines.append("Full bench, ranked by floor:")
bench_rows = sorted([r for r in rows if not r['starting']], key=lambda r: -r['val'])
for r in bench_rows:
    tagstr = 'BYE' if r['tag'] == 'BYE' else (r['tag'] if r['tag'] not in ('proj', 'actual') else '')
    suffix = f" [{tagstr}]" if tagstr else (' [actual]' if r['tag'] == 'actual' else '')
    m = game_script_mult(r) if r['tag'] == 'proj' else None
    if m is not None and abs(m - 1.0) >= 0.03:
        line = LINES.get(r.get('tm'), {})
        suffix += f" (line: {r['tm']} {'fav' if line.get('spread', 0) < 0 else 'dog'} "
        suffix += f"{line.get('spread')}, O/U {line.get('total')}, {'up' if m > 1 else 'down'} {abs(m-1)*100:.0f}%)"
    lines.append(f"  {r['n']:<22} {r['pos']:<4} {r['val']:>5.1f}{suffix}")

lines.append("")
lines.append("Starters with a notably shifted line this week:")
starter_line_notes = []
for r in rows:
    if not r['starting'] or r['tag'] != 'proj':
        continue
    m = game_script_mult(r)
    if abs(m - 1.0) >= 0.03:
        line = LINES.get(r.get('tm'), {})
        starter_line_notes.append(
            f"  {r['n']:<22} {r['pos']:<4} {'fav' if line.get('spread', 0) < 0 else 'dog'} "
            f"{line.get('spread')}, O/U {line.get('total')} -> floor {'up' if m > 1 else 'down'} {abs(m-1)*100:.0f}%")
lines += starter_line_notes if starter_line_notes else ["  None."]

print("\n".join(lines))

# Data sidecar: what the lineup is missing and the best pickup for each gap. autoreport.py
# turns this into "what the moves are worth" rather than re-parsing the text above.
try:
    json.dump({'week': this_week, 'holes': hole_recs},
              open('state/startsit_holes.json', 'w'), indent=1)
except Exception:
    pass          # the printed report is the deliverable; the sidecar is a convenience
