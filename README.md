# ShowMeYourTDs fantasy football

Season model and post-slate reports for my Sleeper league: ShowMeYourTDs, 12 teams, half PPR, redraft. Sleeper league ID `1385346462094741504`, my team is `uaintgotjuicehoeido`.

## How it got here

It began as a draft-night assistant for one league and became a nightly
in-season model. The short version: a scoring-rules read that made rushing
quarterbacks and the tight-end window the whole draft strategy, then a
post-draft rebuild that caught four real defects (frozen rosters, IR players
counted healthy, unrealistically narrow weekly variance, lineups picked in
hindsight), then start/sit, market data, a public dashboard, a self-audit, and
finally four scheduled tasks that run it without being asked.

Full story, with what each change did to the numbers: **[docs/EVOLUTION.md](docs/EVOLUTION.md)**.
Earlier versions of the simulator are frozen in [`archive/prototype-sept-2026/`](archive/prototype-sept-2026).

## What it does

- Pulls live rosters, standings, results, and the in-progress week from the Sleeper and ESPN public APIs.
- Simulates the rest of the season 10,000 times:
  - completed weeks use real scores
  - the current week uses points already scored
  - injured players return on researched dates, with a harsh injury model on top
- Produces playoff, bye, #1 seed, finals, and title odds for all 12 teams.
- Pulls real NFL play-by-play (nflverse) for team tendencies — EPA/play, pass rate, xpass residual — independent of fantasy scoring.
- Texts a written report through Messages after each NFL slate.
- Publishes a public dashboard (standings, matchups, tendencies, market watch, highlights) to a real site, refreshed automatically each run: **https://ankithmareddy.github.io/fantasy-football-hub/**

## Running it

```bash
./update.sh
```

Runs the whole pipeline and writes results to `state/latest_*.txt`. To text a report:

```bash
./send_text.sh reports/<file>.txt
```

## Files

| File | Purpose |
|---|---|
| `league.py` | derives league id, team keys, starting slots, scoring and the full schedule from Sleeper — the groundwork for running on any league (`LEAGUE_ID` env var) |
| `refresh.py` | live league data from Sleeper and ESPN |
| `season.py` | builds the model input from rosters, projections, and role overrides |
| `runseason.py` | season simulation |
| `league_table.py` | phone-friendly league odds and this week's matchups |
| `gameday.py` | box scores under league scoring, injuries, free agents who produced |
| `startsit.py` | conservative-floor start/sit call for the user's own lineup |
| `odds.py` | this week's Vegas lines (ESPN/DraftKings) and line movement, feeds startsit.py's game-script multiplier |
| `tendencies.py` | real play-by-play tendencies (nflverse) — venv-only, see Setup below |
| `highlights.py` | ESPN highlight clips + recap articles, tagged to rostered players/owners — links out only, never hosts video |
| `weekly_awards.py` | Sleeper-report-style weekly awards: best/worst team, players/benchwarmers of the week, lineup efficiency |
| `waivers.py` | league-wide waiver/free-agent activity since the last run, every team's remaining FAAB — read-only context for waiver strategy |
| `sensitivity.py` | re-runs the season sim twice more under different assumptions (higher weekly variance, lighter injury hazard) to show how much of the baseline playoff odds depend on those choices — never replaces or feeds back into the baseline model |
| `history.py` | archives per-player weekly scoring + NFL kickoff times — Sleeper only serves these live, and `state/actuals.json` keeps team totals only |
| `winprob.py` | win probability for one matchup with partial information; shares runseason.py's gamma draws so odds can't disagree between the two |
| `playback.py` | scrubbable matchup replays with a win% curve, one step per kickoff window |
| `drill.py` | the Key Decision drill: finds the slot where the call mattered most each team-week and grades every option on win chance, ex-ante |
| `comeback.py` | Comeback spots: rewinds a lost matchup to the latest window a single legal swap could still have flipped it |
| `build_arcade.py` | consolidates the three above into `site/arcade.json` |
| `build_site.py` | consolidates state into `site/data.json` for the public dashboard |
| `site/index.html` | the public dashboard page (an unwrapped HTML fragment — see deploy_site.sh) |
| `site/arcade.html` | the arcade page: REPLAY, THE DRILL, COMEBACK (standalone, reads `arcade.json`) |
| `dailygames.py` | daily puzzle pool — guess the player, the game, the manager — written to `site/puzzles.json` |
| `site/daily.html` | the daily puzzle page (standalone, reads `puzzles.json`) |
| `build_game.py` | exports each manager's squad + per-position ratings to `site/teams.json` for the playable game |
| `site/gridiron.html` | Gridiron — original play-calling football game using the league's real rosters |
| `deploy_site.sh` | wraps site/index.html + data.json and pushes them to the public fantasy-football-hub repo (GitHub Pages) |
| `sleeper/team_display.json` | current Sleeper team name + avatar per team, cosmetic only (the model's internal team key never changes) |
| `state/scouting_notes.md` | durable team/coach patterns noticed across weeks, maintained by the report run |
| `board.json` | preseason projections |
| `state/injury_overrides.json` | researched injury return weeks, maintained by the report run |
| `state/role_overrides.json` | evidenced role changes, maintained by the report run |
| `state/model_changelog.md` | every model change; read before explaining an odds move |
| `recipients.txt` | phone numbers for the text report (gitignored) |
| `docs/EVOLUTION.md` | how the project evolved from draft tool to in-season assistant |
| `archive/prototype-sept-2026/` | frozen earlier versions of the simulator and the draft board (not imported by anything) |

## Schedule

**Consolidating:** [docs/SCHEDULED_TASK.md](docs/SCHEDULED_TASK.md) has a single task prompt that replaces all of the tasks below. Until it's set up, the four tasks below are what run.

Two Claude scheduled tasks:

- **Fantasy report text (ShowMeYourTDs)** — two scheduled tasks sharing the same per-manager report logic, four runs a week: Sunday 8 AM (before that day's early kickoffs — START/SIT leads, the one that actually matters for lineup decisions), then Thursday, Sunday, and Monday at 11 PM (right after each slate finishes — mostly recap, since that week's roster is already locked or played by then). Every run researches injuries and news, updates the override files, re-runs the model, lists league-wide waiver pickups and FAAB for all 12 teams, includes a start/sit call, fact-checks, then texts the user and their roommate/co-manager.
- **Fantasy league recap (forward to group chat)** — Tuesday at 9:30 AM, after Monday Night Football wraps up. Re-runs the model (no new research), deploys the public site, and writes a league-wide recap — all 6 matchups, standings, top performers, and updated playoff/title odds for all 12 teams — plus a draft X thread. Both are saved as local files for the user to copy and send themselves; this task never texts or posts anything automatically. Texting is reserved for the per-manager report above.
- **Fantasy nightly site refresh** — Tuesday, Wednesday, Friday, and Saturday at 11 PM — the four nights none of the above tasks run. Light touch: checks for real injury/status news (especially any injury_overrides.json entry whose return_week has arrived), updates the override files if warranted, re-runs the model, and deploys the site. No text, no report file, and no notification at all unless something actually changed. Between this and the other three tasks, the site gets checked for new news every night of the week.

Both need the Claude app open and the Mac awake. `sudo pmset -a disablesleep 1` and `sudo pmset -a displaysleep 0` keep it from idle-sleeping, but a MacBook with the lid closed and no external display still force-sleeps regardless — leave the lid open (or attach an external display while on power) for these to fire reliably.

The Sunday/Tuesday/Friday task also redeploys the public site (`deploy_site.sh`) as its last step. Live at https://ankithmareddy.github.io/fantasy-football-hub/, source at [AnkithMareddy/fantasy-football-hub](https://github.com/AnkithMareddy/fantasy-football-hub) (public — built site only, no model code or rosters beyond what's already shown on the page).

## Setup: tendencies.py

`tendencies.py` needs `nflreadpy` (nflverse data, `polars`-based) in a venv — this project's Python 3.14 environment couldn't build the older `nfl_data_py`'s pinned numpy from source, so `nflreadpy` is the one that's actually installed:

```bash
python3 -m venv .venv
.venv/bin/pip install nflreadpy
```

update.sh runs it automatically if `.venv/` exists, and skips it quietly (with a note) if it doesn't.
