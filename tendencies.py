#!/usr/bin/env python3
"""Team tendency analysis from real play-by-play data (nflverse, via nflreadpy — free, CC-BY-SA 4.0,
attribution: nflverse/nflfastR). Independent of Sleeper/ESPN — this is what actually happened on the
field, not fantasy scoring.

Run inside the project venv: `.venv/bin/python3 tendencies.py` (nflreadpy/polars are venv-only,
not installed system-wide — update.sh does NOT run this automatically yet, run it manually or add
it to update.sh once you're happy with the output).

For each team, over the current season to date:
- pass rate: early downs (1st/2nd) vs overall, and specifically in the red zone
- xpass residual: actual pass rate minus nflverse's own expected-pass-rate model (situation-neutral
  expectation) — positive means more pass-heavy than a neutral team would be in the same spots,
  negative means more run-heavy. This is the standard "predictability" signal serious analysts use,
  not something invented here.
- EPA/play on offense and allowed on defense — the standard advanced efficiency metric (points
  added per play, given down/distance/field position), separates good process from lucky results.
- shotgun rate and no-huddle rate, as pace/aggression signals.

This is observational, not predictive — small samples early in the season (Week 1-2) will be noisy.
Treat anything before ~4-5 weeks of data as provisional, and say so in the report.

Writes state/tendencies.json (machine-readable) and prints a human-readable table to stdout."""
import json, os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    import nflreadpy as nfl
except ImportError:
    print("nflreadpy not installed. Run: source .venv/bin/activate && pip install nflreadpy")
    sys.exit(1)

SEASON = nfl.get_current_season()
pbp = nfl.load_pbp([SEASON])
real = pbp.filter((pbp['rush_attempt'] == 1) | (pbp['pass_attempt'] == 1))
weeks_seen = sorted(real['week'].unique().to_list())

rows = []
teams = sorted(real['posteam'].drop_nulls().unique().to_list())
for team in teams:
    off = real.filter(real['posteam'] == team)
    de = real.filter(real['defteam'] == team)
    if off.height < 10:
        continue
    early = off.filter(off['down'].is_in([1, 2]))
    rz = off.filter(off['yardline_100'] <= 20)
    n = off.height
    row = {
        'team': team,
        'plays': n,
        'pass_rate': round(off['pass_attempt'].mean(), 3),
        'early_down_pass_rate': round(early['pass_attempt'].mean(), 3) if early.height else None,
        'redzone_pass_rate': round(rz['pass_attempt'].mean(), 3) if rz.height >= 5 else None,
        'redzone_plays': rz.height,
        'xpass_residual': round(off['pass_attempt'].mean() - off['xpass'].mean(), 3) if off['xpass'].null_count() < n else None,
        'epa_per_play_off': round(off['epa'].mean(), 3),
        'epa_per_play_def': round(de['epa'].mean(), 3) if de.height else None,
        'shotgun_rate': round(off['shotgun'].mean(), 3),
        'no_huddle_rate': round(off['no_huddle'].mean(), 3),
    }
    rows.append(row)

rows.sort(key=lambda r: -r['epa_per_play_off'])
json.dump({'season': SEASON, 'weeks': weeks_seen, 'teams': rows}, open('state/tendencies.json', 'w'), indent=1)

provisional = len(weeks_seen) < 4
print(f"TEAM TENDENCIES — {SEASON} season, weeks {weeks_seen} ({real.height} plays)")
if provisional:
    print(f"PROVISIONAL: only {len(weeks_seen)} week(s) of data. Small samples — don't overread these yet.")
print()
print(f"{'TEAM':<5}{'EPA/play off':>13}{'EPA/play def':>13}{'Pass rate':>11}{'Early-down pass':>17}{'RZ pass rate':>13}{'xpass +/-':>11}{'Shotgun':>9}{'No-huddle':>11}")
for r in rows:
    rz = f"{r['redzone_pass_rate']:.0%}" if r['redzone_pass_rate'] is not None else "n/a"
    xp = f"{r['xpass_residual']:+.0%}" if r['xpass_residual'] is not None else "n/a"
    print(f"{r['team']:<5}{r['epa_per_play_off']:>13.3f}{(r['epa_per_play_def'] or 0):>13.3f}"
          f"{r['pass_rate']:>11.0%}{(r['early_down_pass_rate'] or 0):>17.0%}{rz:>13}{xp:>11}"
          f"{r['shotgun_rate']:>9.0%}{r['no_huddle_rate']:>11.0%}")

print()
print("xpass +/- : actual pass rate minus nflverse's situation-neutral expected pass rate.")
print("Positive = more pass-heavy than expected given down/distance/score/time. Negative = more run-heavy.")
