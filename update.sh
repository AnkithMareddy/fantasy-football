#!/bin/bash
# Refreshes everything the report needs. Output lands in state/latest_*.txt
set -euo pipefail
cd "$(dirname "$0")"
python3 refresh.py        | tee state/latest_refresh.txt
python3 season.py         >     state/latest_season_build.txt
python3 runseason.py      | tee state/latest_odds.txt
python3 league_table.py   | tee state/latest_league.txt
python3 gameday.py        | tee state/latest_games.txt
python3 highlights.py     | tee state/latest_highlights.txt
python3 odds.py           | tee state/latest_lines.txt
python3 startsit.py       > state/latest_startsit.txt
python3 weekly_awards.py  | tee state/latest_awards.txt

# tendencies.py needs the venv (nflreadpy/polars) — skip quietly if it hasn't been set up
if [ -x .venv/bin/python3 ]; then
  .venv/bin/python3 tendencies.py > state/latest_tendencies.txt
else
  echo "skipping tendencies.py: .venv not found (run: python3 -m venv .venv && .venv/bin/pip install nflreadpy)"
fi

python3 build_site.py
