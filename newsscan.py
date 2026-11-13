#!/usr/bin/env python3
"""Detect what CHANGED for league-rostered players since the last run.

The nightly site refresh runs without a model in the path, which is what makes it
reliable — but it meant nothing was watching for news. The Claude routine did that, and
it has frozen on a permission prompt twice. So this does the part that needs no
judgement: it snapshots every rostered player's status each run and reports the diff.

What it can see, because Sleeper carries it and refresh.py was discarding it:
  injury_status          OUT / DOUBTFUL / QUESTIONABLE / IR / PUP / SUS / NA
  injury_body_part       "Groin", "Hamstring", ...
  practice_participation DNP / Limited / Full
  status                 Active / Inactive / Injured Reserve ...
  news_updated           epoch ms of the last news item Sleeper attached to the player

What it cannot do, and does not pretend to: read a beat writer, weigh whether a coach is
being cagey, or decide what a designation means for Sunday. That is the Claude routine's
job. This is the tripwire, not the analyst.

A change is only reported for players on a roster in THIS league — the full Sleeper map
is ~11k players and almost none of them matter here.

Writes: state/news_snapshot.json  (the current state, for next run to diff against)
        state/news_changes.json   (what changed, for the report to pick up)
Run with --quiet to suppress the printed report.
"""
import json, os, subprocess, sys, time

os.chdir(os.path.dirname(os.path.abspath(__file__)))
SNAP = 'state/news_snapshot.json'
CHANGES = 'state/news_changes.json'

# Ordered worst-to-best so a move between them can be called a downgrade or an upgrade
# rather than just "changed".
SEVERITY = ['IR', 'PUP', 'SUS', 'NA', 'OUT', 'DOUBTFUL', 'QUESTIONABLE', None]


def sev(status):
    # Sleeper sends these title-cased ("Doubtful"), so compare upper-cased. Without the
    # .upper() every real designation landed in the ValueError branch and scored the same
    # as "no designation", which meant EVERY change was labelled an upgrade and sorted to
    # the bottom: on 2026-11-11 a Questionable -> Doubtful read as "[better]". A downgrade
    # being reported as good news is the one thing this scan must never do.
    if status is None:
        return len(SEVERITY) - 1
    try:
        return SEVERITY.index(str(status).upper())
    except ValueError:
        return len(SEVERITY) - 1


def rostered():
    """pid -> team key, for every player on a roster in this league."""
    try:
        rost = json.load(open('sleeper/rosters.json'))
        slot_name = {int(k): v for k, v in json.load(open('sleeper/slot_name.json')).items()}
    except Exception:
        return {}
    out = {}
    for slot, players in rost.items():
        team = slot_name.get(int(slot), f'slot{slot}')
        for p in players:
            if p.get('pid'):
                out[str(p['pid'])] = team
    return out


def snapshot(owners):
    raw = json.load(open('sleeper/players_raw.json'))
    snap = {}
    for pid, team in owners.items():
        v = raw.get(pid)
        if not v:
            continue
        snap[pid] = {
            'name': v.get('full_name') or pid,
            'pos': v.get('position'),
            'nfl': v.get('team'),
            'owner': team,
            'inj': v.get('injury_status'),
            'part': v.get('injury_body_part'),
            'status': v.get('status'),
            'practice': v.get('practice_participation'),
            'news': v.get('news_updated'),
        }
    return snap


def diff(old, new):
    events = []
    for pid, cur in new.items():
        prev = old.get(pid)
        if not prev:
            continue                      # first time we've seen him; not news
        # injury designation
        if cur['inj'] != prev['inj']:
            a, b = prev['inj'], cur['inj']
            if b is None:
                kind, text = 'cleared', f"designation lifted (was {a})"
            elif a is None:
                kind, text = 'new', f"now {b}" + (f" ({cur['part']})" if cur.get('part') else '')
            elif sev(b) < sev(a):
                kind, text = 'worse', f"{a} -> {b}"
            else:
                kind, text = 'better', f"{a} -> {b}"
            events.append({'pid': pid, 'kind': kind, 'text': text, **cur})
        # roster status (Active / Inactive / Injured Reserve)
        elif cur['status'] != prev['status']:
            events.append({'pid': pid, 'kind': 'status',
                           'text': f"{prev['status']} -> {cur['status']}", **cur})
        # practice participation moves are the earliest signal there is
        elif cur['practice'] != prev['practice'] and cur['practice']:
            events.append({'pid': pid, 'kind': 'practice',
                           'text': f"practice: {prev['practice'] or 'n/a'} -> {cur['practice']}", **cur})
    order = {'worse': 0, 'new': 1, 'status': 2, 'better': 3, 'cleared': 4, 'practice': 5}
    events.sort(key=lambda e: (order.get(e['kind'], 9), e['owner'], e['name']))
    return events


def trending(kind='add', hours=24, limit=10):
    url = (f'https://api.sleeper.app/v1/players/nfl/trending/{kind}'
           f'?lookback_hours={hours}&limit={limit}')
    res = subprocess.run(['curl', '-s', '--max-time', '45', url],
                         capture_output=True, text=True)
    try:
        return json.loads(res.stdout) or []
    except Exception:
        return []


def main(quiet=False):
    owners = rostered()
    if not owners:
        print("newsscan: no rosters on disk yet (run refresh.py first)")
        return
    new = snapshot(owners)
    old = {}
    if os.path.exists(SNAP):
        try:
            old = json.load(open(SNAP))
        except Exception:
            old = {}

    events = diff(old, new) if old else []
    json.dump(new, open(SNAP, 'w'))
    json.dump({'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'events': events}, open(CHANGES, 'w'), indent=1)

    if quiet:
        return
    if not old:
        print(f"newsscan: first run, snapshotted {len(new)} rostered players (nothing to diff yet)")
        return
    print(f"NEWS SCAN — {len(new)} rostered players checked")
    if not events:
        print("  no status changes since the last run")
    else:
        for e in events:
            print(f"  [{e['kind']:<8}] {e['name']} ({e['pos']}, {e['nfl']}) — {e['text']}  [{e['owner']}]")

    # Trending adds are the league-independent signal that something happened to someone.
    P = json.load(open('sleeper/players.json'))
    adds = trending('add')
    if adds:
        named = []
        for pid in adds[:8]:
            m = P.get(str(pid)) or {}
            if m.get('n'):
                own = owners.get(str(pid))
                named.append(f"{m['n']} ({m.get('p')}, {m.get('t')})" + (f" [rostered: {own}]" if own else " [FA]"))
        if named:
            print("\n  most-added across Sleeper, last 24h:")
            for n in named:
                print(f"    {n}")


if __name__ == '__main__':
    main(quiet='--quiet' in sys.argv)
