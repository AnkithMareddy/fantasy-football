# ShowMeYourTDs

A fantasy football model for one 12-team Sleeper league that grew into three
things: a draft-night assistant, a nightly in-season advisor that texts itself,
and an arcade my league can actually play.

**Live dashboard:** https://ankithmareddy.github.io/fantasy-football-hub/

It has run unattended, every day, since September — and the interesting part of
this repo is not the simulation. It is the record of being wrong. Nearly every
change here came from catching a defect, and the ones that mattered most were
all cases where the model looked confident and was quietly cheating.

## The three acts

**1. Draft strategy (Sept 3-6).** The league's exact scoring, not generic
advice, set the plan. Under 0.5 PPR with 4-point passing TDs and -2 per
interception, a rushing yard is worth **2.5x** a passing yard — which makes a
running quarterback the only real separator at the position. Five years of
league history (840 picks) became per-manager draft tendencies, which is what
called the tight-end window at pick 21 instead of 28.

**2. Live advice (Sept 10 onward).** A 10,000-season Monte Carlo for playoff and
title odds, a conservative-floor start/sit call, Vegas game-script context, real
play-by-play tendencies from nflverse, waivers and FAAB for all 12 teams — texted
after every slate and published to a public dashboard.

**3. Games (Oct onward).** Scrubbable matchup replays with a live win% curve,
a decision drill graded on win-chance rather than outcome, comeback mode, daily
puzzles in two separate tracks, and an original play-calling football game
driven by the league's real rosters.

**The full story, with what each change did to the numbers, is in
[docs/EVOLUTION.md](docs/EVOLUTION.md)** — including the three things that went
wrong badly enough to be worth writing down:

- The model was **picking lineups in hindsight**, worth +3-4 points a week. Our
  own playoff odds fell 75% → 64% → 61% as that and three sibling defects were
  fixed. None of it was new information about football.
- The decision drill was **100% solvable** by one rule, and then, after that was
  fixed, was found to be **grading week-4 calls with week-17 knowledge** under a
  banner reading "No hindsight."
- A projection source nearly replaced the season baseline on the strength of a
  backtest that had been **measured on the wrong population**. It was 1.4%
  better at 0.94 standard errors — noise. `backtest_baseline.py` now re-runs
  that comparison weekly and reports paired significance, so the next candidate
  has to clear a real bar.

## What it does

- Pulls live rosters, standings, results and the in-progress week from the
  Sleeper and ESPN public APIs.
- Simulates the rest of the season 10,000 times: completed weeks use real
  scores, the current week uses points already scored, injured players return on
  researched dates.
- Produces playoff, bye, #1 seed, finals and title odds for all 12 teams.
- Calls start/sit on a conservative floor — and when a starter cannot play and
  the bench cannot cover him, looks **off the roster** at the wire and prices
  what the pickup is worth in win probability.
- Scans every rostered player for injury and practice-participation changes on
  each refresh, and reports the diff.
- Texts a written report through Messages after each slate.
- Publishes the dashboard and the arcade, refreshed automatically twice a day.

## The arcade

Two tracks, because they reward different knowledge:

| Track | Needs | Games |
|---|---|---|
| **NFL knowledge** | Any football fan | Guess the Player, Guess the NFL Game |
| **League knowledge** | Only someone in *this* league | Guess the Matchup, Guess the Manager, Guess the Lineup |

Plus three built on real league history: **Replay** (scrub any matchup with a
win% curve), **The Drill** (a real lineup call, every alternative simulated and
graded ex-ante), and **Comeback** (rewind a lost matchup to the last moment a
legal swap could still have flipped it). **Gridiron** is an original
play-calling game using each manager's real squad.

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
| `update.sh` | runs the whole pipeline in order; everything downstream reads its output |
| `autorefresh.sh` | what launchd calls — `update.sh` then `deploy_site.sh`, with an explicit `PATH` because launchd starts with a near-empty environment |
| `textreport.sh` | builds a report and optionally texts it; refuses to send if `update.sh` failed or the report came out under 200 bytes |
| `autoreport.py` | writes the report from pipeline output alone — no model, no prompts, so it cannot be blocked by a permission request |
| `lock.sh` | one pipeline at a time; a PID-bearing lock *directory* (`mkdir` is atomic, macOS has no `flock`) so a dead holder's lock can be reclaimed |
| `send_text.sh` | sends a report file through macOS Messages to each number in `recipients.txt`, masking numbers to the last four digits in its log |
| `newsscan.py` | diffs every rostered player's injury status, body part, practice participation and roster status against the last run — a tripwire, not an analyst |
| `sleeperproj.py` | Sleeper's weekly projections (licensed from RotoWire) with the measurement showing they beat our season average, used in start/sit only |
| `freeagents.py` | who is actually available to pick up this week, by subtraction (the full player map minus every league roster), ranked by projection |
| `backtest_baseline.py` | weekly guard: re-tests whether a different season baseline would beat the current one, reporting paired significance rather than a bare MAE |
| `gamelog.py` | per-player game log with `ppg_through(week)` — expectations built from prior weeks only, which is what stopped the drill grading calls in hindsight |
| `nflcolors.py` | team colours for the site and the arcade |
| `launchd/` | reference copies of both LaunchAgents, the reload commands, and the Weekday-convention trap |
| `docs/EVOLUTION.md` | how the project evolved from draft tool to in-season assistant |
| `archive/prototype-sept-2026/` | frozen earlier versions of the simulator and the draft board (not imported by anything) |

## Schedule

Two **launchd** agents do the work that must not fail, with no model in the path
and nothing that can stall on a prompt. See [launchd/README.md](launchd/README.md).

| Agent | Runs | Does |
|---|---|---|
| `com.showmeyourtds.refresh` | daily 05:00, 14:00 | `autorefresh.sh` — full pipeline, then deploy. No text. |
| `com.showmeyourtds.text` | Sun 08:00, Sun 22:30, Mon 22:30, Thu 17:30 | `textreport.sh auto --send` |

`auto` picks preview vs recap by whether a kickoff is still ahead of you: Sunday
before noon and Thursday before 8 PM are previews, everything else is a recap.

One **Claude scheduled task** still runs on top of this and writes the better
report when it can — it researches injuries and news, and explains what a result
means, which `autoreport.py` cannot. It is the ceiling; the launchd pair is the
floor. The floor exists because that task froze on a permission prompt three
times (Oct 18, 23, 26), and a frozen run blocks every run queued behind it.
See [docs/SCHEDULED_TASK.md](docs/SCHEDULED_TASK.md).

Neither agent runs while the Mac is asleep, and launchd does not catch up a
missed calendar run on wake.

## Running it on another league

`league.py` derives the league id, team keys, starting slots, scoring and the
full schedule from Sleeper, so most of the pipeline is not hard-wired to this
league:

```bash
LEAGUE_ID=<your sleeper league id> ./update.sh
```

What *is* specific to this league and would need changing: `TEAM` in
`startsit.py`, the preseason board in `board.json`, and the researched override
files in `state/`. The texting path needs `recipients.txt` (gitignored) and
macOS Messages.

## What is deliberately not in this repo

`recipients.txt` (phone numbers), `reports/` (full rosters and league members'
names) and the `state/*.log` run logs are gitignored and stay local. No phone
number, API key, token or `.env` file has ever been committed — the history has
been checked for all four.

## Setup: tendencies.py

`tendencies.py` needs `nflreadpy` (nflverse data, `polars`-based) in a venv — this project's Python 3.14 environment couldn't build the older `nfl_data_py`'s pinned numpy from source, so `nflreadpy` is the one that's actually installed:

```bash
python3 -m venv .venv
.venv/bin/pip install nflreadpy
```

update.sh runs it automatically if `.venv/` exists, and skips it quietly (with a note) if it doesn't.
