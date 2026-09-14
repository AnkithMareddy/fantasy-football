# Model changelog
Read this before explaining any change in odds between reports. Newest first.

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
