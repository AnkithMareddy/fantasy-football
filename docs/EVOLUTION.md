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

---

## Where the pieces live

| Era | Still in use | Frozen |
|---|---|---|
| Draft | `board.json`, `adp_halfppr_12team.csv`, `sleeper/history.json`, `sleeper/habits.json` | `archive/prototype-sept-2026/draft_board_scored.json` |
| Early model | `runseason.py`, `season.py`, `refresh.py` | `archive/prototype-sept-2026/runseason_v1-v3.py`, `refresh_v1.py` |
| In-season | `startsit.py`, `odds.py`, `waivers.py`, `weekly_awards.py`, `highlights.py`, `tendencies.py`, `sensitivity.py` | — |
| Publishing | `build_site.py`, `site/`, `deploy_site.sh` | — |

Reports (`reports/`) and phone numbers stay local and gitignored — they carry
full rosters and league members' names.

The public dashboard is a separate repo on purpose
([fantasy-football-hub](https://github.com/AnkithMareddy/fantasy-football-hub)):
it holds built output only, so model code and rosters never land on a public
page. That split is deliberate and should stay.
