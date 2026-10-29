#!/usr/bin/env python3
"""Who is actually available to pick up this week, ranked by RotoWire's projection.

WHY THIS EXISTS
Week 8 showed the hole: seven of this roster's fourteen players were on bye at once,
including the starting QB and the starting DEF, and every single bench player was on bye
too. startsit.py correctly floored all of them to 0 — and then had nothing useful to say,
because it only ever compares a roster against itself. Its advice came out as "start
Shough (0.0) over Stroud (0.0), +0.0 pt floor edge", which is worse than silence: two
automatic zeros in the lineup and a recommendation that reads like a real one.

The fix a human would reach for is not on the roster at all. So this looks outside it:
every player nobody in the league has rostered, whose NFL team actually plays this week,
who is not hurt, ranked by what RotoWire expects him to score.

Sleeper has no "free agents" endpoint — it is a subtraction. The full player map is ~11k
entries, the league rosters ~177, so anyone not in the second set and carrying a real
projection in the first is pickup-eligible.

Usage:  python3 freeagents.py [POS ...]        default: QB RB WR TE K DEF
        import freeagents; freeagents.top('QB', n=5, week=8)
"""
import json, os, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# a designation that means he will not help you this week
BLOCKED = {'OUT', 'DOUBTFUL', 'IR', 'PUP', 'SUS', 'NA', 'COV'}
POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']


def rostered_pids():
    try:
        rost = json.load(open('sleeper/rosters.json'))
    except Exception:
        return set()
    return {str(p['pid']) for players in rost.values() for p in players if p.get('pid')}


def available(week=None, pos=None):
    """Unrostered players whose team plays this week, with a projection. Best first."""
    P = json.load(open('sleeper/players.json'))
    week = week or int(json.load(open('state/week.json')).get('nfl_week', 1))
    playing = set(json.load(open('state/kickoffs.json')).get(str(week)) or {})
    taken = rostered_pids()

    import sleeperproj
    proj = sleeperproj.for_week(week)

    out = []
    for pid, m in P.items():
        if pid in taken:
            continue
        p = m.get('p')
        if p not in POSITIONS or (pos and p != pos):
            continue
        tm = m.get('t')
        if not tm or tm not in playing:        # no team, or on bye — no help this week
            continue
        if (m.get('inj') or '').upper() in BLOCKED:
            continue
        pts = proj.get(str(pid))
        if not pts or pts <= 0:                # RotoWire isn't projecting him: not startable
            continue
        out.append({'pid': pid, 'n': m['n'], 'pos': p, 'tm': tm, 'proj': round(pts, 1)})
    out.sort(key=lambda r: -r['proj'])
    return out


def top(pos, n=5, week=None):
    return available(week=week, pos=pos)[:n]


def main(argv):
    want = [a.upper() for a in argv if a.upper() in POSITIONS] or POSITIONS
    week = int(json.load(open('state/week.json')).get('nfl_week', 1))
    rows = available(week=week)
    print(f"FREE AGENTS — week {week}, unrostered in this league, RotoWire projection")
    for pos in want:
        hits = [r for r in rows if r['pos'] == pos][:6]
        if not hits:
            continue
        print(f"\n  {pos}")
        for r in hits:
            print(f"    {r['n']:<24} {r['tm']:<4} {r['proj']:>5.1f}")


if __name__ == '__main__':
    main(sys.argv[1:])
