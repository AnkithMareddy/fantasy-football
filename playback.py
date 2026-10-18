#!/usr/bin/env python3
"""Build scrubbable matchup replays with a live win% curve.

For every week and every matchup, produces an ordered list of steps. A step is one NFL
kickoff window: every starter whose game kicks off at that time resolves together, the
running score updates, and win% is recomputed treating resolved players as certainties
and everyone still to play as a gamma draw.

Granularity note, on purpose: Sleeper gives per-player WEEK totals, not per-play scoring,
so a replay advances by kickoff window (Thu night, Sun early, Sun late, SNF, MNF) rather
than play by play. Nothing here invents intra-game timing it doesn't have. Simulated
playback for an UPCOMING week (sim_week) is free to be finer-grained, because there the
timeline is drawn rather than reported.

Writes: state/playback.json
"""
import json, os, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import winprob as W

os.chdir(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo('America/New_York')
SIMS = int(os.environ.get('PLAYBACK_SIMS', '4000'))

PW = json.load(open('state/player_weeks.json'))
KO = json.load(open('state/kickoffs.json'))
P = json.load(open('sleeper/players.json'))
PPG = W.ppg_index()


def label_for(iso):
    """'Thu 8:20p' — football-natural, in ET, which is how everyone talks about kickoffs."""
    t = datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(ET)
    h = t.strftime('%I').lstrip('0') or '12'
    return f"{t.strftime('%a')} {h}:{t.strftime('%M')}{'a' if t.hour < 12 else 'p'}"


def meta(pid):
    p = P.get(str(pid), {})
    return p.get('n', str(pid)), p.get('p'), p.get('t')


def side_rows(week, team):
    """Each starter with the kickoff that resolves them. kick=None -> bye/no game."""
    wk = PW[str(week)][team]
    rows = []
    for i, pid in enumerate(wk['starters']):
        name, pos, nfl = meta(pid)
        pts = wk['starter_pts'][i] if i < len(wk['starter_pts']) else 0.0
        g = (KO.get(str(week)) or {}).get(nfl or '')
        ppg = PPG.get(str(pid), (0.0, pos))[0]
        rows.append({'pid': str(pid), 'name': name, 'pos': pos, 'nfl': nfl,
                     'pts': pts, 'kick': (g or {}).get('kick'), 'ppg': ppg})
    return rows


def build_matchup(week, a, b):
    ra, rb = side_rows(week, a), side_rows(week, b)
    kicks = sorted({r['kick'] for r in ra + rb if r['kick']})

    def todo(rows, after_idx):
        """Players not yet resolved -> (ppg, pos) draws."""
        done = set(kicks[:after_idx])
        return [(r['ppg'], r['pos']) for r in rows
                if r['kick'] and r['kick'] not in done]

    def locked(rows, after_idx):
        done = set(kicks[:after_idx])
        # byes / no-game players are settled from the start at whatever they scored (usually 0)
        return round(sum(r['pts'] for r in rows
                         if not r['kick'] or r['kick'] in done), 2)

    steps = []
    wp = W.win_prob(locked(ra, 0), todo(ra, 0), locked(rb, 0), todo(rb, 0), SIMS)
    steps.append({'label': 'pregame', 'iso': None, 'a': locked(ra, 0), 'b': locked(rb, 0),
                  'wp': round(wp, 4), 'revealed': []})
    for i, k in enumerate(kicks, start=1):
        revealed = [{'side': s, 'name': r['name'], 'pos': r['pos'], 'nfl': r['nfl'],
                     'pts': r['pts'], 'ppg': round(r['ppg'], 1)}
                    for s, rows in (('a', ra), ('b', rb)) for r in rows if r['kick'] == k]
        revealed.sort(key=lambda x: -x['pts'])
        wp = W.win_prob(locked(ra, i), todo(ra, i), locked(rb, i), todo(rb, i), SIMS)
        steps.append({'label': label_for(k), 'iso': k, 'a': locked(ra, i), 'b': locked(rb, i),
                      'wp': round(wp, 4), 'revealed': revealed})

    # the key moment: biggest single-window swing in win%, which is what the drill zooms in on
    swings = [(abs(steps[i]['wp'] - steps[i - 1]['wp']), i) for i in range(1, len(steps))]
    key_swing, key_step = max(swings) if swings else (0.0, 0)
    return {'a': a, 'b': b,
            'a_total': PW[str(week)][a]['total'], 'b_total': PW[str(week)][b]['total'],
            'steps': steps, 'key_step': key_step, 'key_swing': round(key_swing, 4)}


def build_week(week):
    teams = PW[str(week)]
    seen, out = set(), []
    for t, row in teams.items():
        opp = row.get('opp')
        if not opp or t in seen or opp in seen:
            continue
        seen.add(t); seen.add(opp)
        out.append(build_matchup(week, t, opp))
    return out


if __name__ == '__main__':
    weeks = sys.argv[1:] or sorted(PW, key=int)
    out = {}
    for w in weeks:
        if str(w) not in PW:
            print(f"week {w}: no data, skipped"); continue
        out[str(w)] = build_week(w)
        big = max(out[str(w)], key=lambda m: m['key_swing'])
        print(f"week {w}: {len(out[str(w)])} matchups | biggest swing "
              f"{big['key_swing']*100:.0f}% in {big['a']} vs {big['b']} "
              f"at {big['steps'][big['key_step']]['label']}")
    json.dump(out, open('state/playback.json', 'w'), indent=1)
    print(f"\nwrote state/playback.json ({SIMS} sims/step)")
