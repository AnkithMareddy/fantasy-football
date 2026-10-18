#!/usr/bin/env python3
"""League configuration, derived from Sleeper instead of hardcoded.

The pipeline grew up around one league, so its shape is written into the source: the
league id sits in refresh.py, the 14-week schedule is a literal string in season.py, the
starting slots are a list in startsit.py, and 0.5 PPR is baked into the projections. None
of that has to be hardcoded — Sleeper serves all of it, including future weeks' matchups,
so the schedule can be read rather than typed.

This module derives a full config from a league id and caches it. Run it directly to see
the derived config and, for the original league, a check that it reproduces what the code
currently hardcodes — that equivalence is the whole argument that this is safe to adopt.

Usage:
    LEAGUE_ID=123... python3 league.py            # derive + print
    from league import config; cfg = config()     # in the pipeline
"""
import json, os, subprocess, sys

DEFAULT_LEAGUE = "1385346462094741504"
CACHE = 'state/league_config.json'


def get(u):
    out = subprocess.run(['curl', '-s', '--max-time', '60', u], capture_output=True, text=True)
    if not out.stdout.strip():
        raise SystemExit(f"FETCH FAILED: {u}")
    return json.loads(out.stdout)


def league_id():
    return os.environ.get('LEAGUE_ID') or DEFAULT_LEAGUE


class UnknownLeague(Exception):
    """The id doesn't resolve to a Sleeper league."""


def derive(lid):
    # Sleeper answers an unknown league with a bare `null`, so this has to be checked
    # explicitly — otherwise it surfaces later as a confusing TypeError. People will
    # paste wrong ids, and they deserve to be told what went wrong.
    info = get(f'https://api.sleeper.app/v1/league/{lid}')
    if not isinstance(info, dict) or not info.get('league_id'):
        raise UnknownLeague(
            f"No Sleeper league with id {lid!r}. Copy it from the league URL in the "
            f"Sleeper app or website: sleeper.com/leagues/<this part>/...")
    users = {u['user_id']: u for u in get(f'https://api.sleeper.app/v1/league/{lid}/users')}
    rosters = get(f'https://api.sleeper.app/v1/league/{lid}/rosters')
    settings = info.get('settings') or {}
    scoring = info.get('scoring_settings') or {}

    # Team keys. The original league pins names via a draft-order map so a mid-season
    # rename can't shift the model's internal keys; any other league just uses the
    # handle, which is stable enough and always present.
    slot_name = {}
    if lid == DEFAULT_LEAGUE and os.path.exists('sleeper/slot_name.json'):
        drafts = get(f'https://api.sleeper.app/v1/league/{lid}/drafts')
        order = {uid: int(s) for uid, s in ((drafts[0].get('draft_order') or {}) if drafts else {}).items()}
        names = {int(k): v for k, v in json.load(open('sleeper/slot_name.json')).items()}
        slot_name = {uid: names[s] for uid, s in order.items() if s in names}

    rid_team, team_rid = {}, {}
    for r in rosters:
        uid = r.get('owner_id')
        key = slot_name.get(uid) or (users.get(uid, {}).get('display_name')) or f"roster{r['roster_id']}"
        rid_team[r['roster_id']] = key
        team_rid[key] = r['roster_id']

    slots = [p for p in (info.get('roster_positions') or []) if p != 'BN']
    playoff_start = settings.get('playoff_week_start') or 15
    last_regular = max(1, playoff_start - 1)

    # Schedule straight from the matchup pairings, including weeks not yet played.
    sched = {t: [] for t in team_rid}
    for w in range(1, last_regular + 1):
        pair = {}
        for m in get(f'https://api.sleeper.app/v1/league/{lid}/matchups/{w}'):
            if m.get('matchup_id') is not None and m['roster_id'] in rid_team:
                pair.setdefault(m['matchup_id'], []).append(rid_team[m['roster_id']])
        seen = set()
        for sides in pair.values():
            if len(sides) == 2:
                a, b = sides
                sched[a].append(b); sched[b].append(a)
                seen.update(sides)
        for t in sched:                     # bye or missing pairing keeps the weeks aligned
            if t not in seen:
                sched[t].append(None)

    return {
        'league_id': lid,
        'name': info.get('name'),
        'teams': sorted(team_rid),
        'rid_team': {str(k): v for k, v in rid_team.items()},
        'roster_slots': slots,
        'total_rosters': info.get('total_rosters'),
        'playoff_teams': settings.get('playoff_teams'),
        'playoff_week_start': playoff_start,
        'last_regular_week': last_regular,
        'ppr': scoring.get('rec', 0.0),
        'pass_td': scoring.get('pass_td'),
        'te_premium': scoring.get('bonus_rec_te') or 0.0,
        'schedule': sched,
    }


def config(refresh=False):
    """Derived config, cached. Pass refresh=True to re-pull from Sleeper."""
    lid = league_id()
    if not refresh and os.path.exists(CACHE):
        try:
            c = json.load(open(CACHE))
            if c.get('league_id') == lid:
                return c
        except Exception:
            pass
    c = derive(lid)
    os.makedirs('state', exist_ok=True)
    json.dump(c, open(CACHE, 'w'), indent=1)
    return c


# ----- the equivalence check: does the derived config match what's hardcoded today? -----
HARDCODED_SLOTS = ['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'K', 'DEF']


def check(cfg):
    ok = True
    print("\nEquivalence check against the hardcoded values:")

    same = cfg['roster_slots'] == HARDCODED_SLOTS
    ok &= same
    print(f"  roster slots      {'MATCH' if same else 'DIFFER'}  {cfg['roster_slots']}")

    try:
        import re
        src = open('season.py').read()
        raw = src.split('SCHED_RAW="""', 1)[1].split('"""', 1)[0].strip()
        hard = {}
        for line in raw.splitlines():
            t, opps = line.split('|', 1)
            hard[t.strip()] = [x.strip() for x in opps.split(',')]
        drift = []
        for t, opps in hard.items():
            got = cfg['schedule'].get(t, [])[:len(opps)]
            if got != opps:
                drift.append((t, [(i + 1, a, b) for i, (a, b) in enumerate(zip(opps, got)) if a != b]))
        ok &= not drift
        if drift:
            print(f"  schedule          DIFFERS for {len(drift)} team(s)")
            for t, ds in drift[:3]:
                print(f"      {t}: {ds[:4]}")
        else:
            print(f"  schedule          MATCH  ({len(hard)} teams x {len(next(iter(hard.values())))} weeks)")
    except Exception as e:
        print(f"  schedule          could not compare ({e})")
        ok = False

    try:
        names = set(json.load(open('sleeper/slot_name.json')).values())
        same = set(cfg['teams']) == names
        ok &= same
        print(f"  team keys         {'MATCH' if same else 'DIFFER'}  ({len(cfg['teams'])} teams)")
    except Exception:
        pass

    print(f"\n  {'derived config reproduces the hardcoded league exactly' if ok else 'MISMATCH — do not adopt yet'}")
    return ok


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    try:
        cfg = config(refresh=True)
    except UnknownLeague as e:
        print(f"error: {e}")
        sys.exit(2)
    print(f"league {cfg['league_id']} — {cfg['name']}")
    print(f"  teams              {cfg['total_rosters']}")
    print(f"  starting slots     {' '.join(cfg['roster_slots'])}")
    print(f"  scoring            {cfg['ppr']} PPR, {cfg['pass_td']} pass TD, "
          f"TE premium {cfg['te_premium']}")
    print(f"  playoffs           {cfg['playoff_teams']} teams, from week {cfg['playoff_week_start']}")
    print(f"  regular season     weeks 1-{cfg['last_regular_week']}")
    if cfg['league_id'] == DEFAULT_LEAGUE:
        sys.exit(0 if check(cfg) else 1)
