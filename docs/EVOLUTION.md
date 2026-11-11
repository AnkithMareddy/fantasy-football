# How this project evolved

It started as a draft-night assistant and turned into something that runs every
night of the week without being asked. The useful through-line is that almost
every change came from catching something wrong, not from adding a feature.

---

## Phase 0 — Before the draft (Sept 3-6)

The league's scoring, not generic fantasy advice, set the strategy.

- **0.5 PPR, 4-point passing TDs, -2 per interception.** Working through the
  math, a rushing yard is worth **2.5x** a passing yard and a rushing TD 1.5x a
  passing one. That makes a running quarterback the only real separator at the
  position, and compresses pocket passers toward the waiver wire.
- **Projections were rescored from scratch** under those exact rules rather than
  trusted as published, then compared against ADP from ~2,900 half-PPR 12-team
  mock drafts to find where the market disagreed with the format.
- **Five years of league history** (`sleeper/history.json`, 840 picks) became
  per-manager tendencies in `sleeper/habits.json` — who reaches for tight ends,
  who takes a defense early, who always opens running back. That history was
  what flagged three managers who draft a tight end in the first three rounds,
  which is why the tight end window was called at pick 21 and not 28.
- The draft was then **simulated from pick 1.04** against those tendencies to
  answer one question per pick: who will still be here when my turn comes back?

**Artifact:** `archive/prototype-sept-2026/draft_board_scored.json` — 155
players scored under league rules with ADP and value over replacement. It is the
direct ancestor of `board.json`.

## Phase 1 — Draft night (Sept 6)

Live, pick by pick, read straight from the Sleeper draft API rather than from
screenshots. The format was deliberately terse: the pick, a confidence number,
two or three reasons, next targets, and who to let fall.

What actually happened at 1.04: both cliff running backs went 1-2, Ja'Marr Chase
went 3rd, so the pick was Christian McCaffrey. Trey McBride at 2.09 came out of
the tight-end-window read. The final roster is in
[`reports/2026-09-10-week1-thu-night.txt`](../reports).

## Phase 2 — The rebuild that changed the numbers (Sept 10-11)

The first post-slate report exposed four real defects in the model, and fixing
them mattered more than anything added since:

| Defect | Effect |
|---|---|
| Rosters were frozen at draft day | Three teams that drafted no kicker were scoring **zero** in that slot every simulated week, making rivals look weak |
| Players on IR counted as healthy | Five injured players, including Brock Bowers, were projected as if playing |
| Weekly variance far too narrow | Team scores swung ~11 points when real swings are ~18-20, which made favorites look like locks |
| Lineups chosen after seeing scores | A hindsight bias worth **+3-4 points a week**, biggest for deep benches |

Our own playoff odds went **75% → 64% → 61%** across those fixes. None of that
was new information about football; it was the model getting less wrong.

The four-version lineage of the simulator through this period is preserved in
[`archive/prototype-sept-2026/`](../archive/prototype-sept-2026).

## Phase 3 — From draft tool to in-season assistant (Sept 12-24)

The repo's own commit history covers this stretch. In order of what it added:

- **start/sit** (`startsit.py`) — a conservative-floor lineup call for one team
- **Vegas lines** (`odds.py`) — game-script context, capped so one lopsided line
  can't dominate, and deliberately **never allowed to move the season baseline**
- **real play-by-play tendencies** (`tendencies.py`) — EPA, pass rate, xpass
  residual from nflverse, independent of fantasy scoring entirely
- **a public dashboard** (`build_site.py`, `site/`) — moved off an Artifact to a
  real GitHub Pages site
- **weekly awards, waiver/FAAB tracking, highlights, injury predictions**

Three real bugs were found and fixed in this stretch: a glob that silently read
the wrong file for Top Performers, a matchup panel showing next week's schedule
the moment a week locked, and standings lagging a day because they came from
Sleeper's roster settings instead of actual per-week results.

## Phase 4 — Auditing the model against itself (Sept 22-29)

Rather than trusting the baseline, `sensitivity.py` re-runs the season under
hostile assumptions and reports the spread, never feeding back into the real
numbers:

- **High Chaos** — weekly variance x1.3
- **Healthy World** — injury hazard x0.4
- **Regression Case** — our own team gets extra bust variance, a 20%-per-week
  chance of actually starting the wrong player, and every rival runs hot

That last one exists to answer "is the model just assuming we're good?" It isn't:
the Regression Case alone drops us from **73% to 45%** playoff odds and from 1st
to 8th. A favorite always looks strong in a model where everyone plays to
projection, and this is what that assumption is worth.

## Phase 5 — It runs itself (Sept 24 - today)

Four scheduled tasks, covering every night of the week:

| Task | When | What |
|---|---|---|
| Per-manager report | Sun 8 AM, plus Thu/Sun/Mon 11 PM | Research, model re-run, start/sit, waivers; texted |
| League recap | Tue 9:30 AM | League-wide recap and a draft thread, **never auto-posted** |
| Nightly site refresh | Tue/Wed/Fri/Sat 11 PM | Checks for news, re-runs, redeploys; silent if nothing changed |

Standing rules that shaped the architecture:

- **Weekly signals never touch the season baseline.** Vegas lines, tendencies and
  waiver context may move the current week's start/sit floor only. A one-week
  signal is not a true-talent read.
- **Nothing is sent or posted automatically on anyone's behalf** except the
  per-manager text to the two managers who asked for it.
- **Every odds move gets a named cause.** Sampling error at 10,000 seasons is
  about half a point, so a 2-point move always has a real reason, recorded in
  `state/model_changelog.md`.

## Phase 6 — Games the league can actually play (Oct 1-20)

The model knew more about the league than anyone in it, and all of that was
locked inside a nightly text. This phase turned the archive into things people
could play, built on data the pipeline already produced.

Everything here is split across **two tracks on purpose**, because they reward
different knowledge:

| Track | Needs | Games |
|---|---|---|
| **NFL knowledge** | Any football fan could get it | Guess the Player (144), Guess the NFL Game (136) |
| **League knowledge** | Only someone in *this* league could | Guess the Matchup (44), Guess the Manager (12), Guess the Lineup (108) |

And three things built on real history rather than trivia:

- **Matchup replays** (`playback.py`) — scrub any matchup of the season with a
  live win-probability curve. A step is one NFL kickoff window, so every starter
  whose game begins at the same time resolves together, the way the day actually
  felt.
- **The Key Decision drill** (`drill.py`) — dropped into a real lineup call from
  a real week. Every alternative is simulated, so the call is graded on the
  win-chance it bought, not on whether it happened to work. The idea is borrowed
  from nfl2mindrill; the fantasy application is ours.
- **Comeback mode** (`comeback.py`) — dropped into a matchup at the moment it
  slipped away, with only the slots that hadn't locked yet available to change.

**Gridiron** (`site/gridiron.html`, `build_game.py`) is a playable football game
driven by the league's own rosters. The engine, art and play calls are original;
the only imported things are each manager's real lineup and season average.

### The drill was broken, and reframing could not fix it

First version: **72 out of 72 spots solvable** by one rule — pick the highest
projected points. That is not a game, it is a quiz with the answer printed on it.

Two leaks caused it. Options were sorted best-first, and each option displayed
its own projection. Before fixing it the obvious way, the question worth asking
was whether *any* framing of that data made a real decision — so the generator
was re-run looking for spots where the naive rule lost. Out of **1,849**
candidate spots, it lost in **0**. Win probability is monotonic in projected
points, so no presentation of the same numbers could have made it interesting.
The fix had to remove information, not rearrange it: shuffle the options, hide
the projections.

### The drill was also cheating

Worse, and found later: grading used each player's **whole-season** average,
including games that hadn't been played yet at the time of the call. A week-4
decision was being graded with week-17 knowledge, under a banner that said "No
hindsight."

`gamelog.py`'s `ppg_through(week)` now builds expectations from **prior weeks
only**, with a two-game minimum. That is the same discipline Phase 2 imposed on
the simulator, applied to the games — and it was violated for about three weeks
before anyone noticed, which is why it is written down here.

## Phase 7 — Surviving its own automation (Oct 18-28)

The scheduled Claude routine froze on its **first Bash call**, waiting for a
human to click Approve, on **Oct 18, Oct 23, and Oct 26**. Each time it sat for
days, and because the scheduler will not start a run while one is in flight, it
also swallowed every run queued behind it — including the Sunday-morning
start/sit, the one text that has to beat kickoff.

Three occurrences of the same cause is a design problem, not bad luck. The
response was to take the model out of the critical path entirely:

| Piece | Why it exists |
|---|---|
| `autorefresh.sh` + two **launchd** agents | Refresh and deploy on a clock with no session involved. launchd starts with a near-empty environment, so `PATH` is set explicitly and the whole thing is tested under `env -i`. |
| `autoreport.py` | Writes the report from pipeline output alone — no model, no prompts, nothing that can be asked a question. |
| `textreport.sh` | Builds and sends, and **refuses to send** if `update.sh` failed or the report came out under 200 bytes. A missing text is recoverable; stale numbers presented as current are not. |
| `lock.sh` | One pipeline at a time. macOS has no `flock`, so the lock is a directory (`mkdir` is atomic) holding the owner's PID, which lets a later run reclaim a lock whose holder died. |

This is explicitly a **floor, not a ceiling**. The researched report is better
when the routine runs; this guarantees that something correct goes out when it
doesn't. Bugs found in building it, all of them silent:

- `cmd | tail` masked a failing `deploy_site.sh`, so the log said "pushed" while
  nothing was published. A pipeline's exit status is the **last** command's.
- `pgrep -f "autorefresh.sh"` matched the watcher's own command line.
- The odds parser read column 5 (bye-week odds) as playoff odds, reporting one
  manager at 49% instead of 89.1%.
- An orphaned lock with no recorded owner blocked both scheduled jobs.

## Phase 8 — Daily news, and looking off the roster (Oct 26 - Nov)

Taking the model out of the refresh is what made it reliable — but the model was
also the only thing watching for injury news. So `newsscan.py` does the part
that needs no judgement: it snapshots every league-rostered player each run and
reports the **diff**, using fields `refresh.py` was already downloading and
throwing away (`injury_status`, `injury_body_part`, `practice_participation`,
`status`). Changes are classified new / worse / better / cleared / status /
practice, downgrades first. It is a **tripwire, not an analyst** — it cannot read
a beat writer or weigh whether a coach is being cagey.

**RotoWire projections, adopted in exactly one place.** Sleeper's weekly
projections turn out to be licensed from RotoWire (`company: rotowire`). Measured
over weeks 3-7 they beat our season average at every position (MAE 5.47 vs
6.31), so they became the start/sit expectation — and the Vegas game-script
multiplier was **dropped** where they are used, because their projection already
prices the matchup and applying ours on top would adjust for it twice.

**The change we did not make.** The same idea was nearly applied to the
season-long baseline the Monte Carlo runs on, on the strength of a backtest
showing 5.55 MAE against 6.43. That number did not survive. It had been measured
on the wrong population — only players RotoWire actively projects — and against
the wrong baseline. Measured against what `season.py` actually feeds the sim,
across the full roster, the same idea came out **worse**: 6.49 against 6.35. Had
it shipped, every playoff and title number on the public site would have moved
because of a population artifact. `backtest_baseline.py` now re-runs that
comparison every refresh and reports **paired significance**, not a bare MAE; a
candidate needs z > 1.96 before it may replace the baseline. None has yet.

**Start/sit learned to look outside the roster.** Week 8 put seven of fourteen
players on bye at once — including the starting QB and DEF, with a bench that was
*also* entirely on bye. `startsit.py` floored them all to 0 correctly, then had
nothing useful to say, because it only ever compared the roster against itself.
Its actual output was `Start Tyler Shough (0.0) over C.J. Stroud (0.0) — +0.0 pt
floor edge`: advice-shaped noise sitting exactly where the real finding belonged.

Now a starter who cannot play is reported as a **lineup hole** — what he normally
scores, whether the bench can cover him at all, and when it cannot, the best
pickups on the wire with the market's read on their game attached.
`freeagents.py` derives availability by subtraction, since Sleeper has no
free-agents endpoint. And the report **prices the fix** instead of only reporting
the damage: 14.3% to win as the lineup sat, 56.7% with the two slots filled.

A season-long bug surfaced on the way: ESPN calls Washington `WSH`, Sleeper calls
them `WAS`, and `odds.py` wrote the ESPN spelling into `state/lines.json` while
every lookup used the Sleeper one. `LINES.get('WAS')` had returned `None` since
week 1, so Washington players were the one team in the league getting no Vegas
adjustment at all.

---

## Where the pieces live

| Era | Still in use | Frozen |
|---|---|---|
| Draft | `board.json`, `adp_halfppr_12team.csv`, `sleeper/history.json`, `sleeper/habits.json` | `archive/prototype-sept-2026/draft_board_scored.json` |
| Early model | `runseason.py`, `season.py`, `refresh.py` | `archive/prototype-sept-2026/runseason_v1-v3.py`, `refresh_v1.py` |
| In-season | `startsit.py`, `odds.py`, `waivers.py`, `weekly_awards.py`, `highlights.py`, `tendencies.py`, `sensitivity.py` | — |
| Publishing | `build_site.py`, `site/`, `deploy_site.sh` | — |
| Games | `playback.py`, `drill.py`, `comeback.py`, `dailygames.py`, `build_arcade.py`, `build_game.py`, `gamelog.py`, `history.py` | — |
| Unattended | `autorefresh.sh`, `textreport.sh`, `autoreport.py`, `lock.sh`, `newsscan.py`, `launchd/` | — |
| Validation | `backtest_baseline.py`, `sleeperproj.py`, `freeagents.py` | — |

Reports (`reports/`) and phone numbers stay local and gitignored — they carry
full rosters and league members' names.

The public dashboard stays a separate repo
([fantasy-football-hub](https://github.com/AnkithMareddy/fantasy-football-hub)),
but the reason has changed. It was originally split so that model code and
rosters would never land on a public page. This repo is now public itself, so
that is no longer the reason — the split survives because the hub holds **built
output only** and is overwritten by `deploy_site.sh` on every refresh. It is a
deploy target, not a project: nothing should ever be authored there, and its
history is machine-generated.

What stays local and gitignored is narrower, and still matters: `recipients.txt`
(phone numbers), `reports/` (full rosters and league members' names), and the
`state/*.log` run logs. The repository has been checked for these: no phone
number, API key, token or `.env` file has ever been committed.
