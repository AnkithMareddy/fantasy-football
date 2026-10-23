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
import gamelog as GL

os.chdir(os.path.dirname(os.path.abspath(__file__)))
N = int(os.environ.get('DRILL_SIMS', '8000'))

import league
# starting slots come from the league's own settings (roster_positions)
SLOTS = league.config()['roster_slots']
ELIGIBLE = {'QB': {'QB'}, 'RB': {'RB'}, 'WR': {'WR'}, 'TE': {'TE'},
            'FLEX': {'RB', 'WR', 'TE'}, 'K': {'K'}, 'DEF': {'DEF'}}
BANDS = [(0.005, 'green'), (0.02, 'yellow'), (0.05, 'orange')]

PW = json.load(open('state/player_weeks.json'))
# only completed weeks: a live week's "final" score is just a partial total
FINAL_WEEKS = set(json.load(open('state/actuals.json')))
KO = json.load(open('state/kickoffs.json'))
P = json.load(open('sleeper/players.json'))
# Per-week baseline: a week-W drill is graded only on scoring from weeks before W.
# This used to be one season-long PPG for every week, which meant a week-4 call was
# graded with weeks 5-7 in the number — hindsight, despite the docstring above. It also
# hid mid-season role changes. See gamelog.ppg_through.
MIN_PRIOR_WEEKS = 2
_PPG_CACHE = {}


def ppg_for(week):
    w = int(week)
    if w not in _PPG_CACHE:
        _PPG_CACHE[w] = GL.ppg_through(w, PW, KO, P)
    return _PPG_CACHE[w]


def grade(cost):
    for lim, name in BANDS:
        if cost <= lim:
            return name
    return 'red'


def pool(week, team):
    """Every rostered player that week whose NFL team actually had a game."""
    PPG = ppg_for(week)
    wk = PW[str(week)][team]
    games = KO.get(str(week)) or {}
    out = []
    # sorted(): set iteration order follows Python's per-process string hash
    # randomisation, which shifts the random-draw sequence and makes results
    # differ between identical runs. Sorting pins it.
    for pid in sorted(set(list(wk['all_pts']) + wk['starters'])):
        p = P.get(str(pid), {})
        pos, nfl = p.get('p'), p.get('t')
        if not pos or nfl not in games:
            continue          # bye week or unrostered in Sleeper's map — never a legal call
        if str(pid) not in PPG:
            continue          # too few prior games to project from; not a gradeable option
        if PPG[str(pid)][0] <= 0:
            continue          # scored nothing in every prior appearance — not a choice
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
        # Two options is a coin flip dressed as a decision; the user asked for real
        # choices, so a slot needs at least three legal candidates to be drillable.
        if len(cands) < 3:
            continue
        scored = []
        for c in cands:
            # same base + opponent streams for every candidate; only this slot varies
            wins = sum(1 for k in range(N)
                       if base[k] + W.draw(c['ppg'], c['pos']) > opp_tot[k])
            scored.append({**c, 'wp': wins / N})
        scored.sort(key=lambda x: -x['wp'])
        spread = scored[0]['wp'] - scored[-1]['wp']
        # Prefer the slot where the call mattered most, but break near-ties toward the
        # slot offering more options — a wider choice set is a better puzzle.
        key = (round(spread, 3), len(scored))
        if not best or key > (round(best['spread'], 3), len(best['options'])):
            best = {'slot_idx': idx, 'slot': slot, 'spread': spread,
                    'options': scored, 'started': started}

    if not best:
        return None
    top = best['options'][0]
    actual = next(o for o in best['options'] if o['pid'] == best['started']['pid'])
    cost = top['wp'] - actual['wp']
    # Gap to the SECOND-best option is the honest difficulty signal. A wide gap means one
    # option is plainly right; a narrow one means the field is tight and you have to
    # actually know the players. (Below ~0.5pp everything grades green anyway, so those
    # are filler rather than hard.) The run mode orders spots by this.
    runner_up = best['options'][1]['wp'] if len(best['options']) > 1 else 0.0
    gap = top['wp'] - runner_up
    tier = 'easy' if gap >= 0.05 else 'medium' if gap >= 0.02 else \
           'hard' if gap >= 0.005 else 'coinflip'
    a_tot, b_tot = wk['total'], PW[str(week)][opp]['total']
    lineup = []
    for i, pid in enumerate(starters):
        # fall back to the raw player map: a starter can be filtered out of the CANDIDATE
        # pool (too few prior games, or no points yet) and still has to be drawn on the
        # field by name, or the formation renders with "?" holes in it.
        r = roster.get(pid) or {}
        meta = P.get(str(pid), {})
        lineup.append({'slot': SLOTS[i] if i < len(SLOTS) else 'FLEX',
                       'name': r.get('name') or meta.get('n') or '?',
                       'pos': r.get('pos') or meta.get('p'),
                       'nfl': r.get('nfl') or meta.get('t'),
                       'contested': i == best['slot_idx']})
    return {
        'week': int(week), 'team': team, 'opp': opp, 'slot': best['slot'],
        'lineup': lineup,
        'slot_idx': best['slot_idx'], 'spread': round(best['spread'], 4),
        'actual_pid': actual['pid'], 'actual_name': actual['name'],
        'actual_wp': round(actual['wp'], 4),
        'best_pid': top['pid'], 'best_name': top['name'], 'best_wp': round(top['wp'], 4),
        'cost': round(cost, 4), 'grade': grade(cost),
        'gap': round(gap, 4), 'tier': tier,
        # Shuffled, and each option carries recent form instead of being pre-ranked. The
        # options used to be emitted best-first with the projection printed alongside, so
        # the whole game was solved by clicking the first button. Consumers must find the
        # best call via `best_pid`, never by taking options[0]. See gamelog.py.
        'options': [{'pid': o['pid'], 'name': o['name'], 'pos': o['pos'], 'nfl': o['nfl'],
                     'ppg': round(o['ppg'], 1), 'wp': round(o['wp'], 4),
                     'log': GL.game_log(o['pid'], week, PW, KO, P),
                     'pts': o['pts'], 'grade': grade(top['wp'] - o['wp'])}
                    for o in GL.deterministic_shuffle(
                        best['options'], week, team, best['slot'], best['slot_idx'])],
        'result': {'for': a_tot, 'against': b_tot, 'won': a_tot > b_tot},
        'options_caveat': 'no historical weekly injury designations; option set is every '
                          'rostered player whose NFL team played that week',
    }


if __name__ == '__main__':
    weeks = sys.argv[1:] or sorted(PW, key=int)
    out = {}
    for w in weeks:
        # a drill needs at least MIN_PRIOR_WEEKS of completed scoring to project from
        if int(w) <= MIN_PRIOR_WEEKS:
            continue
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
