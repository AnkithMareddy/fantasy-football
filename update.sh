#!/bin/bash
# Refreshes everything the report needs. Output lands in state/latest_*.txt
set -euo pipefail
cd "$(dirname "$0")"

# Serialise against the other thing that refreshes this league. autorefresh.sh (launchd)
# already holds this lock when it calls us, so this is a no-op there; it matters when the
# Claude routine runs update.sh directly a few minutes after the launchd job started.
. ./lock.sh
trap 'release_pipeline_lock' EXIT
acquire_pipeline_lock || exit 1

python3 refresh.py        | tee state/latest_refresh.txt
python3 season.py         >     state/latest_season_build.txt
python3 runseason.py      | tee state/latest_odds.txt
python3 sensitivity.py    | tee state/latest_sensitivity.txt
python3 league_table.py   | tee state/latest_league.txt
python3 gameday.py        | tee state/latest_games.txt
python3 highlights.py     | tee state/latest_highlights.txt
python3 odds.py           | tee state/latest_lines.txt
python3 startsit.py       > state/latest_startsit.txt
python3 weekly_awards.py  | tee state/latest_awards.txt
python3 waivers.py        | tee state/latest_waivers.txt

# tendencies.py needs the venv (nflreadpy/polars) — skip quietly if it hasn't been set up
if [ -x .venv/bin/python3 ]; then
  .venv/bin/python3 tendencies.py > state/latest_tendencies.txt
else
  echo "skipping tendencies.py: .venv not found (run: python3 -m venv .venv && .venv/bin/pip install nflreadpy)"
fi

# Weekly guard: re-test whether a different season baseline would beat the current one.
# Read-only — it never changes the model, it only reports whether a change is justified
# yet. See backtest_baseline.py for why this exists.
python3 backtest_baseline.py | tee state/latest_baseline.txt

python3 build_site.py

# Arcade: per-player weekly history -> replays -> drills -> comeback spots. history.py
# must run first; the other three read what it archives. This runs last and every step
# sits inside the `if`, so under `set -e` a failure here leaves the previous arcade data
# in place and still can't take the report or the site build down with it.
# drill.py (~40s) and comeback.py (~35s) are the slow ones.
if python3 history.py      > state/latest_history.txt \
   && python3 playback.py  > state/latest_playback.txt \
   && python3 drill.py     > state/latest_drills.txt \
   && python3 comeback.py  > state/latest_comebacks.txt \
   && python3 build_arcade.py > state/latest_arcade.txt \
   && python3 dailygames.py   > state/latest_puzzles.txt \
   && python3 build_game.py   > state/latest_game.txt; then
  cat state/latest_arcade.txt state/latest_puzzles.txt state/latest_game.txt
else
  echo "arcade regeneration failed — previous site/arcade.json left in place"
fi
