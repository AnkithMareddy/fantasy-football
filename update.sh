#!/bin/bash
# Refreshes everything the report needs. Output lands in state/latest_*.txt
set -euo pipefail
cd "$(dirname "$0")"
python3 refresh.py        | tee state/latest_refresh.txt
python3 season.py         >     state/latest_season_build.txt
python3 runseason.py      | tee state/latest_odds.txt
python3 league_table.py   | tee state/latest_league.txt
python3 gameday.py        | tee state/latest_games.txt
