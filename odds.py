#!/usr/bin/env python3
"""Pulls this week's Vegas lines from ESPN's public odds feed (DraftKings via ESPN, no auth needed)
and turns them into a per-team weekly game-script multiplier for startsit.py.

Method (deliberately simple and capped, not a full market model):
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

Writes state/lines.json (machine-readable, keyed by team abbreviation) and prints a human-readable
table to stdout — update.sh redirects that to state/latest_lines.txt."""
import json, os, subprocess
os.chdir(os.path.dirname(os.path.abspath(__file__)))

BASELINE = 22.0
LO, HI = 0.85, 1.15
BIG_SPREAD = 7.0
SKEW = 0.05   # RB/pass-catcher nudge on a big spread

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
for e in data.get('events', []):
    comp = e['competitions'][0]
    odds_list = comp.get('odds') or []
    if not odds_list:
        continue
    odds = odds_list[0]   # DraftKings, priority 1
    total = odds.get('overUnder')
    if total is None:
        continue
    home = next(c for c in comp['competitors'] if c['homeAway'] == 'home')
    away = next(c for c in comp['competitors'] if c['homeAway'] == 'away')
    home_ab = home['team']['abbreviation']
    away_ab = away['team']['abbreviation']
    home_odds = odds.get('homeTeamOdds', {})
    spread = odds.get('spread')   # spread is relative to the HOME team, negative = home favored
    if spread is None:
        continue
    home_spread = spread
    away_spread = -spread
    home_implied = (total + (-home_spread)) / 2   # favorite (negative spread) gets more than half
    away_implied = (total + (-away_spread)) / 2
    for ab, opp, sp, implied, is_home in (
        (home_ab, away_ab, home_spread, home_implied, True),
        (away_ab, home_ab, away_spread, away_implied, False)):
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
                     'home': is_home}
    fav_ab, dog_ab = (home_ab, away_ab) if home_spread < 0 else (away_ab, home_ab)
    rows.append(f"{away_ab} @ {home_ab}: {fav_ab} -{abs(spread)}, O/U {total} "
                f"(implied {lines[home_ab]['implied']}-{lines[away_ab]['implied']})")

json.dump(lines, open('state/lines.json', 'w'), indent=1)

print(f"WEEK {week} BETTING LINES (DraftKings via ESPN) - {len(rows)} games with a posted line")
for r in sorted(rows):
    print(f"  {r}")
if not rows:
    print("  No lines posted yet for this week.")
