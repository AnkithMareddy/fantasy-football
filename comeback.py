#!/usr/bin/env python3
"""COMEBACK mode — drop into a lost matchup at the moment it slipped away and try to flip it.

nfl2mindrill puts you in a real late-game spot and lets you call the rest of the drive.
The fantasy version of "the rest of the drive" is the slots that hadn't locked yet: at any
kickoff window, every starter whose game hasn't begun is still legally swappable, and so is
every bench player in the same boat. That's a real decision a manager could have made, not
a hypothetical.

For each matchup we find the window where the loser's win probability fell hardest, rewind
to just before it, and enumerate every single-player swap that was still legal there. Each
swap gets two numbers:
  - did it flip the result, computed from REAL final scores (total - starter + replacement)
  - what it was worth at the time, as win% simulated forward from that moment

Those are deliberately separate. A swap can flip the game on hindsight points while having
been a bad call at the time, and the UI shows both so the two never get confused.

One swap only. Allowing several at once turns a clean decision into a combinatorial search
and stops being a game.

Writes: state/comebacks.json
"""
import json, os
import winprob as W

os.chdir(os.path.dirname(os.path.abspath(__file__)))
N = int(os.environ.get('COMEBACK_SIMS', '6000'))

import league
# starting slots come from the league's own settings (roster_positions)
SLOTS = league.config()['roster_slots']
ELIGIBLE = {'QB': {'QB'}, 'RB': {'RB'}, 'WR': {'WR'}, 'TE': {'TE'},
            'FLEX': {'RB', 'WR', 'TE'}, 'K': {'K'}, 'DEF': {'DEF'}}

PW = json.load(open('state/player_weeks.json'))
# only completed weeks: a live week's "final" score is just a partial total
FINAL_WEEKS = set(json.load(open('state/actuals.json')))
KO = json.load(open('state/kickoffs.json'))
PB = json.load(open('state/playback.json'))
P = json.load(open('sleeper/players.json'))
PPG = W.blended_ppg(W.ppg_index(), PW, KO, P)
try:
    TD = json.load(open('sleeper/team_display.json'))
except FileNotFoundError:
    TD = {}


def disp(t):
    return (TD.get(t) or {}).get('team_name') or t


def info(pid, week):
    p = P.get(str(pid), {})
    nfl = p.get('t')
    g = (KO.get(str(week)) or {}).get(nfl or '')
    return {'pid': str(pid), 'name': p.get('n', str(pid)), 'pos': p.get('p'), 'nfl': nfl,
            'kick': (g or {}).get('kick'),
            'ppg': round(PPG.get(str(pid), (0.0, p.get('p')))[0], 1)}


def build(week, m):
    a, b = m['a'], m['b']
    loser, winner = (a, b) if m['a_total'] < m['b_total'] else (b, a)
    lo_tot = m['a_total'] if loser == a else m['b_total']
    wn_tot = m['b_total'] if loser == a else m['a_total']
    if lo_tot >= wn_tot:
        return None                       # tie, nothing to flip

    steps = m['steps']
    lw, ww = PW[str(week)][loser], PW[str(week)][winner]
    starters = [info(p, week) for p in lw['starters']]
    for i, s in enumerate(starters):
        s['slot'] = SLOTS[i] if i < len(SLOTS) else 'FLEX'
        s['pts'] = lw['starter_pts'][i] if i < len(lw['starter_pts']) else 0.0
    bench = []
    for pid in sorted(lw['all_pts']):
        if str(pid) in {str(x) for x in lw['starters']}:
            continue
        r = info(pid, week)
        r['pts'] = lw['all_pts'].get(str(pid), 0.0)
        bench.append(r)

    def legal(entry):
        """Starters and bench still unlocked at `entry`, plus the swaps allowed there."""
        isos = {steps[j]['iso'] for j in range(entry, len(steps)) if steps[j]['iso']}
        os_ = [s for s in starters if s['kick'] in isos]
        ob = [r for r in bench if r['kick'] in isos and r['pos']]
        pairs = [(s, r) for s in os_ for r in ob
                 if r['pos'] in ELIGIBLE.get(s['slot'], set())]
        return isos, os_, ob, pairs

    # Enter as LATE as the game still allows a flip. Taking the biggest win% drop instead
    # lands on the final window almost every time, where nothing is left to swap and the
    # spot is unwinnable by construction — 25 of 26 were, before this.
    entry = None
    for cand in range(len(steps) - 1, 0, -1):
        _, _, _, pairs = legal(cand)
        if any(lo_tot - s['pts'] + r['pts'] > wn_tot for s, r in pairs):
            entry = cand
            break
    if entry is None:
        entry = 1                       # unwinnable: open at pregame and say so
    open_isos, open_starters, open_bench, _ = legal(entry)
    if not open_starters or not open_bench:
        return None
    before = steps[entry - 1]
    lo_locked = before['a'] if loser == a else before['b']
    wn_locked = before['b'] if loser == a else before['a']

    # everyone still to play, for the forward simulation
    lo_todo = [(s['ppg'], s['pos']) for s in open_starters]
    wn_todo = [(info(p, week)['ppg'], info(p, week)['pos'])
               for i, p in enumerate(ww['starters'])
               if info(p, week)['kick'] in open_isos]

    swaps = []
    for s in open_starters:
        for r in open_bench:
            if r['pos'] not in ELIGIBLE.get(s['slot'], set()):
                continue
            new_total = round(lo_tot - s['pts'] + r['pts'], 2)
            todo = [t for t in lo_todo]
            todo.remove((s['ppg'], s['pos']))
            todo.append((r['ppg'], r['pos']))
            wp = W.win_prob(lo_locked, todo, wn_locked, wn_todo, N)
            swaps.append({
                'out_pid': s['pid'], 'out': s['name'], 'out_pts': s['pts'], 'slot': s['slot'],
                'in_pid': r['pid'], 'in': r['name'], 'in_pos': r['pos'], 'in_nfl': r['nfl'],
                'in_ppg': r['ppg'], 'in_pts': r['pts'],
                'new_total': new_total, 'flips': new_total > wn_tot,
                'wp': round(wp, 4),
            })
    if len(swaps) < 3:
        return None          # one or two options isn't a decision, it's a reveal
    swaps.sort(key=lambda x: (-x['new_total'], -x['wp']))
    base_wp = W.win_prob(lo_locked, lo_todo, wn_locked, wn_todo, N)
    return {
        'week': int(week), 'loser': loser, 'winner': winner,
        'loser_name': disp(loser), 'winner_name': disp(winner),
        'entry_step': entry, 'entry_label': steps[entry]['label'],
        'state_label': before['label'],
        'lo_locked': lo_locked, 'wn_locked': wn_locked,
        'final_for': lo_tot, 'final_against': wn_tot,
        'margin': round(wn_tot - lo_tot, 2),
        'base_wp': round(base_wp, 4),
        'held': [{'name': s['name'], 'pos': s['pos'], 'nfl': s['nfl'], 'ppg': s['ppg'],
                  'slot': s['slot'], 'pts': s['pts']} for s in open_starters],
        'lineup': [{'slot': s['slot'], 'name': s['name'], 'pos': s['pos'], 'nfl': s['nfl'],
                    'ppg': s['ppg'], 'locked': s['kick'] not in open_isos} for s in starters],
        'opp_left': len(wn_todo),
        'swaps': swaps,
        'winnable': any(s['flips'] for s in swaps),
    }


if __name__ == '__main__':
    out, n_win = {}, 0
    for w, matchups in PB.items():
        if str(w) not in FINAL_WEEKS:
            continue
        rows = [c for c in (build(w, m) for m in matchups) if c]
        out[str(w)] = rows
        for c in rows:
            if c['winnable']:
                n_win += 1
                best = c['swaps'][0]
                print(f"week {w}: {c['loser']} lost by {c['margin']} — could have flipped it "
                      f"at {c['state_label']} by starting {best['in']} over {best['out']} "
                      f"({best['new_total']} vs {c['final_against']})")
    json.dump(out, open('state/comebacks.json', 'w'), indent=1)
    total = sum(len(v) for v in out.values())
    print(f"\nwrote state/comebacks.json — {total} spots, {n_win} actually winnable")
