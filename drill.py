#!/usr/bin/env python3
"""The Key Decision drill — nfl2mindrill's idea, applied to fantasy.

That game drops you into a real late-game spot, you make the call, and every alternative
is simulated so your call can be graded on win-chance rather than on whether it happened
to work. The fantasy equivalent of a play call is a LINEUP call, and the only moment a
manager actually controls anything is before kickoff — so that's the spot we rebuild.

For each team-week we find the slot where the choice mattered most (the widest win%
spread between the best and worst legal option), then grade every option ex-ante:
simulate the whole matchup from pregame with that player in the slot, using season ppg
only. No hindsight. A correct call that busted still grades green, which is the point.

Grade bands follow the reference game: green within 0.5pp of the best call, yellow 2pp,
orange 5pp, red beyond that.

Honest limitation, recorded in the output as `options_caveat`: we have no historical
weekly injury designations, so the option set is every rostered player whose NFL team
had a game that week. A player who was quietly inactive can therefore appear as an
option. Grading is ex-ante so this never corrupts a grade, but the reveal can show a
"best call" that scored zero.

Writes: state/drills.json
"""
import json, os, sys
import winprob as W

os.chdir(os.path.dirname(os.path.abspath(__file__)))
N = int(os.environ.get('DRILL_SIMS', '8000'))

SLOTS = ['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'K', 'DEF']
ELIGIBLE = {'QB': {'QB'}, 'RB': {'RB'}, 'WR': {'WR'}, 'TE': {'TE'},
            'FLEX': {'RB', 'WR', 'TE'}, 'K': {'K'}, 'DEF': {'DEF'}}
BANDS = [(0.005, 'green'), (0.02, 'yellow'), (0.05, 'orange')]

PW = json.load(open('state/player_weeks.json'))
# only completed weeks: a live week's "final" score is just a partial total
FINAL_WEEKS = set(json.load(open('state/actuals.json')))
KO = json.load(open('state/kickoffs.json'))
P = json.load(open('sleeper/players.json'))
PPG = W.ppg_index()


def grade(cost):
    for lim, name in BANDS:
        if cost <= lim:
            return name
    return 'red'


def pool(week, team):
    """Every rostered player that week whose NFL team actually had a game."""
    wk = PW[str(week)][team]
    games = KO.get(str(week)) or {}
    out = []
    for pid in set(list(wk['all_pts']) + wk['starters']):
        p = P.get(str(pid), {})
        pos, nfl = p.get('p'), p.get('t')
        if not pos or nfl not in games:
            continue          # bye week or unrostered in Sleeper's map — never a legal call
        out.append({'pid': str(pid), 'name': p.get('n', str(pid)), 'pos': pos, 'nfl': nfl,
                    'ppg': PPG.get(str(pid), (0.0, pos))[0],
                    'pts': wk['all_pts'].get(str(pid), 0.0)})
    return out


def samples(rows, n):
    """n sampled totals for a set of players — one draw stream, reused across options.

    Reusing the same stream for every candidate is deliberate (common random numbers):
    it strips sampling noise out of the COMPARISON between two calls, which is the only
    number the drill reports.
    """
    return [sum(W.draw(r['ppg'], r['pos']) for r in rows) for _ in range(n)]


def build(week, team):
    wk = PW[str(week)][team]
    opp = wk.get('opp')
    if not opp:
        return None
    roster = {r['pid']: r for r in pool(week, team)}
    starters = [str(p) for p in wk['starters']]
    opp_rows = [r for r in pool(week, opp) if r['pid'] in
                {str(p) for p in PW[str(week)][opp]['starters']}]
    if not opp_rows or len(starters) != len(SLOTS):
        return None

    opp_tot = samples(opp_rows, N)
    best = None
    for idx, slot in enumerate(SLOTS):
        started = roster.get(starters[idx])
        if not started:
            continue
        others = [roster[p] for p in starters if p != starters[idx] and p in roster]
        base = samples(others, N)
        cands = [r for r in roster.values()
                 if r['pos'] in ELIGIBLE[slot] and (r['pid'] == started['pid']
                                                    or r['pid'] not in starters)]
        if len(cands) < 2:
            continue
        scored = []
        for c in cands:
            # same base + opponent streams for every candidate; only this slot varies
            wins = sum(1 for k in range(N)
                       if base[k] + W.draw(c['ppg'], c['pos']) > opp_tot[k])
            scored.append({**c, 'wp': wins / N})
        scored.sort(key=lambda x: -x['wp'])
        spread = scored[0]['wp'] - scored[-1]['wp']
        if not best or spread > best['spread']:
            best = {'slot_idx': idx, 'slot': slot, 'spread': spread,
                    'options': scored, 'started': started}

    if not best:
        return None
    top = best['options'][0]
    actual = next(o for o in best['options'] if o['pid'] == best['started']['pid'])
    cost = top['wp'] - actual['wp']
    a_tot, b_tot = wk['total'], PW[str(week)][opp]['total']
    return {
        'week': int(week), 'team': team, 'opp': opp, 'slot': best['slot'],
        'slot_idx': best['slot_idx'], 'spread': round(best['spread'], 4),
        'actual_pid': actual['pid'], 'actual_name': actual['name'],
        'actual_wp': round(actual['wp'], 4),
        'best_pid': top['pid'], 'best_name': top['name'], 'best_wp': round(top['wp'], 4),
        'cost': round(cost, 4), 'grade': grade(cost),
        'options': [{'pid': o['pid'], 'name': o['name'], 'pos': o['pos'], 'nfl': o['nfl'],
                     'ppg': round(o['ppg'], 1), 'wp': round(o['wp'], 4),
                     'pts': o['pts'], 'grade': grade(top['wp'] - o['wp'])}
                    for o in best['options']],
        'result': {'for': a_tot, 'against': b_tot, 'won': a_tot > b_tot},
        'options_caveat': 'no historical weekly injury designations; option set is every '
                          'rostered player whose NFL team played that week',
    }


if __name__ == '__main__':
    weeks = sys.argv[1:] or sorted(PW, key=int)
    out = {}
    for w in weeks:
        if str(w) not in PW or str(w) not in FINAL_WEEKS:
            continue
        rows = [d for d in (build(w, t) for t in PW[str(w)]) if d]
        rows.sort(key=lambda d: -d['cost'])
        out[str(w)] = rows
        if rows:
            d = rows[0]
            print(f"week {w}: {len(rows)} drills | costliest call {d['team']} {d['slot']}: "
                  f"started {d['actual_name']} over {d['best_name']} "
                  f"(-{d['cost']*100:.1f}pp win%, {d['grade']})")
    json.dump(out, open('state/drills.json', 'w'), indent=1)
    print(f"\nwrote state/drills.json ({N} sims/option)")
