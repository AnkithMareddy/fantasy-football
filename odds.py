#!/usr/bin/env python3
"""Pulls this week's Vegas lines from ESPN's public odds feed (DraftKings via ESPN, no auth needed)
and turns them into a per-team weekly game-script multiplier for startsit.py, plus a market-watch
list of real line movement for the report to cite.

Game-script method (deliberately simple and capped, not a full market model):
- implied team total = (over/under + team's signed point margin) / 2, the standard way to split
  a spread+total into each team's expected score.
- baseline = 22.0 (a normal team's implied total in an average game). A team's multiplier starts
  at implied_total / baseline, clipped to [0.85, 1.15] so one lopsided line can't blow up a
  projection.
- a small extra nudge for big spreads only (|spread| >= 7): the favorite gets a touch more on the
  ground (clock-killing game script), the underdog a touch more through the air (garbage time).
  RB and WR/TE get the nudge in opposite directions; QB/K/DEF are untouched by it.

This only ever touches the CURRENT week's start/sit floors, never season.py's season-long ppg —
a Vegas line is a one-week signal, not a true-talent estimate, so it has no business changing the
baseline the 10,000-season simulation runs on.

Market-watch: pulls each game's OPENING line alongside the current one (a separate per-event ESPN
endpoint) and flags real, sizable movement (spread moved 1.5+, total moved 3+) — that's an actual
signal (the market reacting to something, often injury news), not a guess. This script never
recommends a side or predicts a winner; it reports what moved and leaves the "why" and "so what"
to the report-writer, who has the injury/roster context to explain it.

Writes state/lines.json (machine-readable, keyed by team abbreviation) and prints a human-readable
table to stdout — update.sh redirects that to state/latest_lines.txt."""
import json, os, subprocess, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))

BASELINE = 22.0
LO, HI = 0.85, 1.15
BIG_SPREAD = 7.0
SKEW = 0.05   # RB/pass-catcher nudge on a big spread
MOVE_SPREAD = 1.5   # spread movement worth flagging (points)
MOVE_TOTAL = 3.0    # total movement worth flagging (points)

def get(u):
    out = subprocess.run(['curl', '-s', '--max-time', '20', u], capture_output=True, text=True)
    if not out.stdout.strip():
        raise SystemExit(f"FETCH FAILED: {u}")
    return json.loads(out.stdout)

wk = json.load(open('state/week.json'))
week = int(wk.get('nfl_week', 1))

data = get(f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week}')

lines = {}   # team abbr -> dict
rows = []
movers = []
for e in data.get('events', []):
    comp = e['competitions'][0]
    odds_list = comp.get('odds') or []
    if not odds_list:
        continue
    odds = odds_list[0]   # DraftKings, priority 1
    total = odds.get('overUnder')
    spread = odds.get('spread')   # relative to the HOME team, negative = home favored
    if total is None or spread is None:
        continue
    home = next(c for c in comp['competitors'] if c['homeAway'] == 'home')
    away = next(c for c in comp['competitors'] if c['homeAway'] == 'away')
    home_ab = home['team']['abbreviation']
    away_ab = away['team']['abbreviation']
    kickoff = e.get('date')   # ISO 8601 UTC, e.g. "2026-09-18T00:15Z"
    home_spread, away_spread = spread, -spread
    home_implied = (total + (-home_spread)) / 2
    away_implied = (total + (-away_spread)) / 2
    for ab, opp, sp, implied in ((home_ab, away_ab, home_spread, home_implied),
                                  (away_ab, home_ab, away_spread, away_implied)):
        mult = max(LO, min(HI, implied / BASELINE))
        rb_skew = wr_skew = 0.0
        if abs(sp) >= BIG_SPREAD:
            favored = sp < 0
            rb_skew = SKEW if favored else -SKEW
            wr_skew = -SKEW if favored else SKEW
        lines[ab] = {'opp': opp, 'spread': round(sp, 1), 'total': total,
                     'implied': round(implied, 1), 'mult': round(mult, 3),
                     'rb_mult': round(max(LO, min(HI, mult + rb_skew)), 3),
                     'wr_mult': round(max(LO, min(HI, mult + wr_skew)), 3),
                     'home': ab == home_ab, 'kickoff': kickoff}
    fav_ab, dog_ab = (home_ab, away_ab) if home_spread < 0 else (away_ab, home_ab)
    rows.append(f"{away_ab} @ {home_ab}: {fav_ab} -{abs(spread)}, O/U {total} "
                f"(implied {lines[home_ab]['implied']}-{lines[away_ab]['implied']})")

    # line movement — separate per-event call, has both 'open' and 'current' at the top level
    try:
        eid = e['id']
        detail = get(f'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/'
                     f'events/{eid}/competitions/{eid}/odds/100?lang=en&region=us')
        open_pts = detail.get('open', {}).get('total', {}).get('american')
        open_total = float(open_pts) if open_pts else None
        open_home_spread_str = (detail.get('homeTeamOdds', {}).get('open', {}).get('pointSpread') or {}).get('american')
        open_home_spread = float(open_home_spread_str.replace('+', '')) if open_home_spread_str else None

        msgs = []
        if open_home_spread is not None and abs(home_spread - open_home_spread) >= MOVE_SPREAD:
            move = home_spread - open_home_spread   # more negative = moved toward home
            toward = home_ab if move < 0 else away_ab
            msgs.append(f"spread opened {away_ab if open_home_spread > 0 else home_ab} "
                        f"-{abs(open_home_spread):.1f}, now {fav_ab} -{abs(spread):.1f} "
                        f"({abs(move):.1f} pt move toward {toward})")
        if open_total is not None and abs(total - open_total) >= MOVE_TOTAL:
            direction = 'up' if total > open_total else 'down'
            msgs.append(f"total opened {open_total:.1f}, now {total:.1f} ({direction} {abs(total-open_total):.1f})")
        if msgs:
            movers.append(f"{away_ab} @ {home_ab}: " + "; ".join(msgs))
        time.sleep(0.3)   # be polite to ESPN's API between per-event calls
    except Exception:
        pass   # line-movement is a bonus signal; never fail the whole run over it

json.dump(lines, open('state/lines.json', 'w'), indent=1)

print(f"WEEK {week} BETTING LINES (DraftKings via ESPN) - {len(rows)} games with a posted line")
for r in sorted(rows):
    print(f"  {r}")
if not rows:
    print("  No lines posted yet for this week.")

print()
print("LINE MOVEMENT (open -> current, moves of 1.5+ spread pts or 3+ total pts)")
if movers:
    for m in movers:
        print(f"  {m}")
else:
    print("  Nothing moved enough to flag.")
