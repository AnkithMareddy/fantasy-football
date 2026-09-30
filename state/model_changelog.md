# Model changelog
Read this before explaining any change in odds between reports. Newest first.

## 2026-09-29 (2) - Regression Case: an adversarial-to-us sensitivity scenario
- runseason.py gained three more levers (MY_TEAM, MY_CV_MULT, MY_MISTAKE_RATE, RIVAL_LUCK_MULT), all no-ops until MY_TEAM is set (verified baseline still byte-identical). MY_CV_MULT adds extra bust variance to one team only; MY_MISTAKE_RATE gives that team a real weekly chance of starting a worse player than it should (the single best bench option at a random position is deliberately benched, not just variance); RIVAL_LUCK_MULT runs every other team hot.
- sensitivity.py's 4th scenario, "Regression Case," points all three at our own team (bust x1.5, 20%/week mistake chance, opponents scoring x1.08) - directly answers "is the model just assuming we deserve 1st." It isn't: this scenario alone drops us from 73.0% to 45.4% playoff odds and from 1st to 8th of 12 - real downside the baseline doesn't show by itself, because a favorite naturally look strong in a model that assumes everyone plays their projection.
- Read-only, same as the other two scenarios - never overwrites season_out.json or feeds back into the baseline, start/sit, or any other number.

## 2026-09-29 - what-if roster scenarios (runseason.py)
- runseason.py now also accepts a SEASON_INPUT env var (defaults to season_input.json, so the normal pipeline run is unaffected - verified byte-identical output with no override). Lets a one-off question like "what does the rest of the season look like if I add X and drop Y" actually run the real 10,000-sim model against a modified roster copy instead of a guess, without ever touching the baseline season_out.json.
- Used this for a real question: swapping AJ Dillon -> Ollie Gordon II and Travis Kelce -> Kalif Raymond (both free agents in this league, both surfaced as waiver targets after De'Von Achane's Week 3 ACL tear). Baseline vs what-if: playoff 73.0% -> 86.3%, bye 31.7% -> 49.9%, title 14.9% -> 24.9%. Scratch input/output files are gitignored (state/whatif_*.json) - this is a one-off analysis tool, not a standing feature.

## 2026-09-22 - model sensitivity check + rivalry storylines + a real standings bug fix
- runseason.py now accepts CV_MULT, HAZ_MULT and SEASON_OUT env vars (all default to a no-op, so the normal pipeline run is byte-for-byte unaffected - verified). New sensitivity.py uses them to run the season sim twice more: "High Chaos" (weekly scoring variance x1.3) and "Healthy World" (injury hazard x0.4, roughly nobody else getting hurt the rest of the way). Neither touches the baseline season_out.json or feeds back into it - they're a read-only comparison, run alongside the baseline the same way the earlier third-party bias audit was: a check on the model, not a change to it. New "Model Sensitivity" panel on the site shows each team's playoff-odds range across all three, with the baseline marked.
- New "Rivalries" panel: the 14-week schedule is built as three 4-team pods where every team plays every podmate exactly twice (everyone else once) - detected directly from the schedule (a pair that shares 2 meetings, not 1) rather than hardcoded, so it can't drift out of sync with the real schedule. Each pod gets a real narrative (in-group leader, tightest game, biggest blowout, next meeting) plus a small table of in-group record vs. overall playoff odds.
- Found and fixed a real bug surfaced while building the pod records: the site's actual W-L and points-for came from Sleeper's roster.settings (state/standings.json via refresh.py), which lags real per-week matchup results by up to a day around a week boundary - right after MNF locked Week 2, standings.json still only showed each team's Week-1 record. The site's standings (and the new pod records) now compute actual W-L/PF directly from state/actuals.json + the schedule, which has no such lag - verified it matches Sleeper's live matchup points exactly.
- Read-only additions plus one real accuracy fix; no change to the baseline model's own projections.

## 2026-09-21 - week-2 lock fixes on the site
- Found and fixed a real bug: once a week's results lock into actuals, first_sim_week jumps to the next week, but the matchups panel was still indexed off first_sim_week - so right after Monday Night Football finished, the site was showing Week 3's matchups under a "Week 2" header. Now indexed by the displayed week (nfl_week) directly.
- Matchup cards fall back cleanly to a plain final score once a week locks (refresh.py only tracks live per-starter detail for the current in-progress week, so a completed week has none - previously this left a blank live-overlay row instead of just the score).
- Header now reads "final scores" instead of "live Sleeper points" once the week is done, and the win tag says WINNER instead of PROJ. WIN.
- Verified final Week 2 scores against Sleeper directly (matchups/2 endpoint) - all six games match exactly.

## 2026-09-20 (2) - collapsible long lists on the site
- Waiver Wire (8 shown), Injury Report (6), Injury Predictions (6), Top Performers (6), Team Tendencies (top 10 by offensive EPA) and per-team Highlights (6) now show the first few rows with a "Show N more" toggle. Display only; no data or projection changes.

## 2026-09-20 - live Sleeper points and injuries on the matchup cards
- Matchup cards now show Sleeper's current live points (projected final underneath), how many of each team's starters are done / live / still to play (from ESPN game status), and injury chips for starters (Sleeper injury_status, plus ESPN game-report injuries). Each card has a per-team lineup drop-down with every starter's points and game state.
- refresh.py now records per-starter game state, injury status, and a fetch timestamp in state/week.json. Sleeper's player file (the source of injury_status) is now re-pulled every 3 hours instead of every 20 (still far below Sleeper's rate limit, but more than their once-a-day guidance).
- Injury Report now lists league-rostered players first with their fantasy owner.
- Fixed a misleading "UPDATED" stamp: the page used the viewer's own clock, so it always read "now". It now shows when the data was actually generated and when Sleeper was last pulled. The site is a static snapshot refreshed when the pipeline runs, not a live feed.
- Read-only display change; no projection numbers moved.

## 2026-09-17 - injury predictions on the site + a gameday-file bug fix
- New "Injury Predictions" panel on the site: the harsh injury model's expected-games-missed per player (season_out.json's `games_missed`, already computed by runseason.py every run) enriched with researched return weeks/notes/sources from state/injury_overrides.json where we have them, and a "MODEL EST." tag when we don't (pure hazard-rate risk, no specific known injury). Read-only — this surfaces a number the sim already produces, it doesn't change any projection.
- Fixed a real bug in build_site.py: its gameday-file glob (`state/week*.json`) also matched `state/weekly_awards.json`, and that sorted alphabetically *after* `state/week2.json` — so "Top Performers" and "Injury Report" were silently reading the wrong file (weekly_awards.json, which has neither key) and showing empty every run once weekly_awards.py existed. Fixed to match `state/week[0-9]*.json` only, sorted by actual week number (so it won't break again at week 10+ once weeks stop sorting alphabetically the same as numerically).

## 2026-09-16 - league-wide waiver wire + FAAB tracking
- New waivers.py pulls Sleeper's real transactions feed for every team (not just ours) — every completed waiver claim (with its actual $ bid) and free-agent pickup, plus every team's remaining FAAB out of $100 (from roster settings, already tracked by refresh.py). Keeps a bookmark (state/waivers_seen.json) so each run only reports what cleared since the last one, not the whole season's history.
- Site: new "Waiver Wire" / "FAAB Remaining" panels under Week Awards — league-wide moves with add/drop and bid amount, plus a FAAB leaderboard bar chart.
- Report: the personal WAIVERS section now reads state/latest_waivers.txt so our own claim advice accounts for what rivals just spent and how much budget they have left, not just our own bids in isolation.
- Read-only: doesn't touch the season sim, injury/role overrides, or any projection number. Pure context addition.

## 2026-09-15 - weekly awards (Sleeper-report style)
- New weekly_awards.py targets the most recently completed week and pulls that week's real matchup data straight from Sleeper (starters/starters_points/players_points, already under our league's actual scoring). Computes: best/worst team, highest points in a loss, lowest points in a win, players of the week and benchwarmers of the week by position (league-wide, with real player headshots via sleepercdn.com), and lineup efficiency (actual starters' points / the best possible lineup from that team's full roster, computed post-hoc the same way startsit.py projects pre-hoc).
- Validated directly against the user's own Sleeper app screenshots — every number matched exactly once "players of the week" was corrected to only consider started players (not bench).
- Read-only: doesn't touch the season simulation, injury/role overrides, or any other model number. Pure recap/content addition.

## 2026-09-14 (3) - real team names/avatars + a highlights section on the site
- refresh.py now also writes sleeper/team_display.json: each team's actual current Sleeper team_name (e.g. "ALO 5's" for uaintgotjuicehoeido, "we all we got" for kisiluv) and avatar image, pulled from user metadata. Purely cosmetic for the site — every other file in this project still keys off the stable internal team name (the Sleeper username / draft slot), which never changes even if a manager renames their team mid-season.
- New highlights.py pulls real per-play highlight clips and recap articles from ESPN's public summary endpoint. Never clips or hosts video ourselves — every card links out to ESPN's own page. Tags each clip with any rostered player named in its headline and their fantasy owner, so the site can filter by team without a play-by-play parser.
- Site now shows avatars + real team names everywhere (standings, matchups, performers, injuries, storylines, ticker) instead of raw Sleeper usernames, and has a Highlights panel with team-filter buttons plus a recap-article strip per game.
- No effect on any model number — cosmetic/content additions only.

## 2026-09-14 (2) - real NFL tendencies + a public dashboard
- New tendencies.py pulls actual play-by-play (nflverse, via nflreadpy — free, CC-BY-SA 4.0) and computes real per-team tendencies: EPA/play on offense and defense, pass rate, xpass residual (actual vs. situation-neutral expected pass rate — the standard "predictability" signal), red zone pass rate, shotgun/no-huddle rate. Entirely independent of fantasy scoring — this is what actually happened on the field. Venv-only (nflreadpy needs polars, not installed system-wide); update.sh runs it automatically if .venv/ exists, skips quietly otherwise. Provisional under ~4 weeks of data — small samples, don't overread early.
- New build_site.py consolidates standings/odds/matchups/tendencies/market lines/top performers/injuries into site/data.json.
- New public dashboard at site/index.html, published as a Claude Artifact (URL in state/site_url.txt). Republished automatically as the last step of the Sun/Tue/Fri report — the page's design is static, only the data refreshes.
- Doesn't touch the season simulation or any odds/projection number — this is a new, separate read-only view, not a model change to the numbers themselves.

## 2026-09-14 - betting lines feed into start/sit, plus a scouting-notes system
- New odds.py, run by update.sh, pulls this week's spread/total/moneyline from ESPN's public odds feed (DraftKings, no auth) and writes state/lines.json + state/latest_lines.txt. Only covers games that still have a posted line at refresh time — completed games lose their line, next week's often aren't posted yet, so most weeks this covers a handful of games, not all of them.
- startsit.py now scales each not-yet-played player's floor by their team's Vegas-implied total (total ± spread, split per team), capped to 0.85-1.15x so one lopsided line can't dominate a call. On spreads of 7+ there's also a small (±5%) RB-vs-WR/TE skew in opposite directions — clock-killing game script favors the favorite's rushing, garbage time favors the underdog's passing. This only touches the current week's start/sit floor, never season.py's season-long ppg baseline — a Vegas line is a one-week signal, not a true-talent read, so it has no business moving the number the 10,000-season sim runs on.
- New state/scouting_notes.md: durable, cross-week observations (real coaching tendencies, offensive identities, role changes) that the per-manager report reads before researching and can append to — not a place for single-game stats or routine injury news. Starts empty; one week of data isn't enough to write anything real yet.
- Attempted to add X/Twitter as a research source for injury-alert accounts (e.g. UnderdogNFL). Direct fetches of individual X post URLs return HTTP 402 (paywalled) — this isn't just the existing login wall, X blocks it outright now. WebSearch can sometimes surface indexed post text but it's inconsistent; documented as best-effort only, not a real monitoring source.

## 2026-09-12 - added start/sit analysis
- New startsit.py, run by update.sh, writes state/latest_startsit.txt.
- Compares the live current lineup (Sleeper's starters right now) against a conservative-floor-optimal lineup for the user's own team only. Floor = season.py's ppg discounted by half of runseason.py's weekly CV per position (e.g. a WR's floor is ppg*0.675, an RB's is ppg*0.70) — a deliberate buffer against boom/bust, not a median or ceiling number.
- Players out this week (bye, an injury_overrides return_week beyond the current week, or a Sleeper OUT/DOUBTFUL/IR/PUP/SUS/NA status) are floored to 0 and labeled unavailable rather than penalized as a bad start.
- A player whose NFL game has already been played uses the real score (from Sleeper's starters_points for starters, players_points for bench — refresh.py now captures both), never a projection, and is never flagged as swappable.
- Doesn't touch odds/projections for other teams or the season sim — this is lineup advice only, no effect on playoff/title numbers.

## 2026-09-10 (Thu night) - model rebuild
- Rosters pulled live from Sleeper every run (was: draft-day rosters). Three teams that drafted no kicker (kisiluv, joshsandorra, Gujju8) now have one. This was the main cause of this team's drop from the preseason 75% playoff odds to 64%.
- Players on IR, Out, PUP, suspended or NA now start the simulation unavailable. Researched return weeks in state/injury_overrides.json override the generic rule (4 weeks for IR-type statuses, 1 week for Out or Doubtful).
- Weekly scoring variance raised to realistic levels: a team's weekly score now swings ~18-20 pts (was ~11). This pulls extreme odds toward the middle.
- Lineups are chosen by projection before games, not after seeing scores. This removed a hindsight bias worth +3-4 pts/week.
- The in-progress week uses real points already scored, plus the best lineup from players who haven't played.
- Simulations raised from 4,000 to 10,000 seasons.
- Net for uaintgotjuicehoeido: 4th / 64% playoffs / 10% title in the Thu 11 PM text (old model) became 3rd / 61% / 11% (new model). That change came from these model fixes, not sampling noise.
